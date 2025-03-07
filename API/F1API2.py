from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pydantic import BaseModel
import jwt
import datetime
import os
from dotenv import load_dotenv
import mysql.connector
from pymongo import MongoClient

# Chargement des variables d'environnement
load_dotenv()

# Configuration
class Settings:
    USER_MYSQL = os.getenv("USER_MYSQL")
    PASSWORD_MYSQL = os.getenv("PASSWORD_MYSQL")
    SECRET_KEY = os.getenv("SECRET_KEY")
    API_PASSWORD = os.getenv("API_PASSWORD")
    MONGO_URI = os.getenv("MONGO_URI")

settings = Settings()

# Configuration FastAPI
app = FastAPI(
    title="F1 API",
    description="API pour accéder aux données F1",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Système d'authentification
security = HTTPBearer()

class TokenRequest(BaseModel):
    password: str
    duration: Optional[int] = 3600

def create_jwt(duration: int) -> str:
    expiration = datetime.datetime.utcnow() + datetime.timedelta(seconds=duration)
    return jwt.encode(
        {"exp": expiration},
        settings.SECRET_KEY,
        algorithm="HS256"
    )

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
        return credentials.credentials
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

# Connexions aux bases de données
def get_mysql_connection():
    try:
        return mysql.connector.connect(
            host="localhost",
            user=settings.USER_MYSQL,
            password=settings.PASSWORD_MYSQL,
            database="f1_database"
        )
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection error: {str(e)}"
        )

def get_mongo_connection():
    try:
        client = MongoClient(settings.MONGO_URI)
        return client.F1.f1_performance_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MongoDB connection error: {str(e)}"
        )

# Routes API
@app.get("/")
async def root():
    return {"message": "F1 API is running"}

@app.post("/token")
async def generate_token(request: TokenRequest):
    if request.password != settings.API_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )
    token = create_jwt(request.duration)
    return {"token": token}

@app.get("/races/{year}")
async def get_races(
    year: int,
    circuit: Optional[str] = None,
    token: str = Depends(verify_token)
):
    connection = None
    cursor = None
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)

        query = "SELECT * FROM races WHERE year = %s"
        params = [year]

        if circuit:
            query += " AND circuit = %s"
            params.append(circuit)

        cursor.execute(query, params)
        results = cursor.fetchall()

        if not results:
            return {"message": f"No races found for year {year}"}
        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.get("/driver/{driver_name}")
async def get_driver_stats(
    driver_name: str,
    year: Optional[int] = None,
    token: str = Depends(verify_token)
):
    connection = None
    cursor = None
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT 
            r.year,
            COUNT(*) as races,
            SUM(rr.points) as total_points,
            SUM(CASE WHEN rr.position = 1 THEN 1 ELSE 0 END) as wins
        FROM race_results rr
        JOIN races r ON rr.race_id = r.id
        WHERE rr.driver = %s
        """
        params = [driver_name]

        if year:
            query += " AND r.year = %s"
            params.append(year)

        query += " GROUP BY r.year ORDER BY r.year"

        cursor.execute(query, params)
        results = cursor.fetchall()

        if not results:
            return {"message": f"No statistics found for driver {driver_name}"}
        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.get("/performance/{circuit}")
async def get_circuit_performance(
    circuit: str,
    year: Optional[int] = None,
    token: str = Depends(verify_token)
):
    try:
        collection = get_mongo_connection()

        match_stage = {"circuit": circuit}
        if year:
            match_stage["year"] = year

        pipeline = [
            {"$match": match_stage},
            {
                "$group": {
                    "_id": {
                        "year": "$year",
                        "race_name": "$race_name"
                    },
                    "avg_speed": {"$avg": "$performance.speeds.avg"},
                    "max_speed": {"$max": "$performance.speeds.max"}
                }
            },
            {"$sort": {"_id.year": 1}}
        ]

        results = list(collection.aggregate(pipeline))

        if not results:
            return {"message": f"No performance data found for circuit {circuit}"}
        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)