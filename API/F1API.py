import os
import jwt
import datetime
from fastapi import FastAPI, Query, Depends, HTTPException, Header
from fastapi.responses import HTMLResponse
import mysql.connector
from pymongo import MongoClient
from typing import Optional, List
from pydantic import BaseModel
from dotenv import load_dotenv

# Chargement et vérification des variables d'environnement
print("===== Débogage =====")
load_dotenv()

# Affichage des variables d'environnement pour débogage
print("USER_MYSQL:", os.getenv("USER_MYSQL"))
print("API_PASSWORD:", os.getenv("API_PASSWORD"))
print("SECRET_KEY:", os.getenv("SECRET_KEY"))
print("===================")

# Configuration
USER = os.getenv("USER_MYSQL")
PASSWORD = os.getenv("PASSWORD_MYSQL")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSWORD = os.getenv("API_PASSWORD")
MONGO_URI = os.getenv("MONGO_URI")

app = FastAPI(
    title="F1 API",
    description="API pour accéder aux données F1",
    version="1.0.0"
)

# Modèles Pydantic
class TokenRequest(BaseModel):
    password: str
    duration: Optional[int] = 3600

# Fonctions utilitaires
def create_jwt(duration: int):
    """Génère un token JWT"""
    expiration = datetime.datetime.now() + datetime.timedelta(seconds=duration)
    payload = {"exp": expiration}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_token(authorization: Optional[str] = Header(None)):
    """Vérifie la validité du token JWT"""
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    
    token = authorization.split("Bearer ")[1]
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Connexions aux bases de données
def get_mysql_connection():
    """Établit une connexion à la base de données MySQL"""
    return mysql.connector.connect(
        host="localhost",
        user=USER,
        password=PASSWORD,
        database="f1_database"
    )

def get_mongo_connection():
    """Établit une connexion à la base de données MongoDB"""
    client = MongoClient(MONGO_URI)
    return client.F1.f1_performance_data

# Routes API
@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head>
            <title>F1 API Documentation</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    line-height: 1.6;
                }
                code {
                    background-color: #f4f4f4;
                    padding: 2px 5px;
                    border-radius: 3px;
                }
                .endpoint {
                    margin-bottom: 20px;
                    padding: 10px;
                    border-left: 3px solid #007bff;
                    background-color: #f8f9fa;
                }
            </style>
        </head>
        <body>
            <h1>F1 API Documentation</h1>
            
            <h2>Documentation Interactive</h2>
            <p>Accédez à la documentation interactive Swagger UI : <a href="/docs">/docs</a></p>
            
            <h2>Endpoints Disponibles</h2>
            
            <div class="endpoint">
                <h3>POST /token</h3>
                <p>Obtenir un token d'authentification</p>
                <code>
                POST /token<br>
                Body: {"password": "votre_password", "duration": 3600}
                </code>
            </div>

            <div class="endpoint">
                <h3>GET /races/{year}</h3>
                <p>Obtenir les courses d'une année spécifique</p>
            </div>

            <div class="endpoint">
                <h3>GET /driver/{driver_name}</h3>
                <p>Obtenir les statistiques d'un pilote</p>
            </div>

            <div class="endpoint">
                <h3>GET /performance/{circuit}</h3>
                <p>Obtenir les données de performance pour un circuit</p>
            </div>

            <div class="endpoint">
                <h3>GET /weather-impact</h3>
                <p>Analyser l'impact de la météo sur les performances</p>
            </div>
        </body>
    </html>
    """

@app.post("/token")
def generate_token(request: TokenRequest):
    """Génère un token d'authentification"""
    print("===== Débogage Token =====")
    print("Password reçu:", request.password)
    print("Password attendu:", API_PASSWORD)
    print("Type password reçu:", type(request.password))
    print("Type password attendu:", type(API_PASSWORD))
    print("=========================")
    
    if request.password != API_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    token = create_jwt(request.duration)
    return {"token": token}

@app.get("/races/{year}", dependencies=[Depends(verify_token)])
def get_races(year: int, circuit: Optional[str] = None):
    """Obtient les courses d'une année spécifique"""
    connection = get_mysql_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        query = "SELECT * FROM races WHERE year = %s"
        params = [year]
        
        if circuit:
            query += " AND circuit = %s"
            params.append(circuit)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        return results
    finally:
        cursor.close()
        connection.close()

@app.get("/driver/{driver_name}", dependencies=[Depends(verify_token)])
def get_driver_stats(driver_name: str, year: Optional[int] = None):
    """Obtient les statistiques d'un pilote"""
    connection = get_mysql_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        query = """
        SELECT 
            r.year,
            COUNT(*) as races,
            SUM(rr.points) as total_points,
            SUM(CASE WHEN rr.position = 1 THEN 1 ELSE 0 END) as wins,
            ROUND(AVG(rr.position), 2) as avg_position
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
        return results
    finally:
        cursor.close()
        connection.close()

@app.get("/performance/{circuit}", dependencies=[Depends(verify_token)])
def get_circuit_performance(circuit: str, year: Optional[int] = None):
    """Obtient les données de performance pour un circuit"""
    mongo_collection = get_mongo_connection()
    
    try:
        query = {"circuit": circuit}
        if year:
            query["year"] = year
            
        pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": {
                        "year": "$year",
                        "race_name": "$race_name"
                    },
                    "avg_speed": {"$avg": "$performance.speeds.avg"},
                    "max_speed": {"$max": "$performance.speeds.max"},
                    "best_lap_time": {"$min": "$performance.best_lap_time"},
                    "year": {"$first": "$year"}
                }
            },
            {"$sort": {"year": 1}}
        ]
        
        results = list(mongo_collection.aggregate(pipeline))
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/weather-impact", dependencies=[Depends(verify_token)])
def get_weather_impact(year: Optional[int] = None):
    """Analyse l'impact de la météo sur les performances"""
    mongo_collection = get_mongo_connection()
    
    try:
        match_stage = {"$match": {}} if year is None else {"$match": {"year": year}}
        
        pipeline = [
            match_stage,
            {
                "$group": {
                    "_id": {
                        "condition": {
                            "$cond": [
                                {"$gt": ["$weather.precipitation", 0]},
                                "Pluie",
                                "Sec"
                            ]
                        }
                    },
                    "avg_speed": {"$avg": "$performance.speeds.avg"},
                    "races_count": {"$sum": 1}
                }
            }
        ]
        
        results = list(mongo_collection.aggregate(pipeline))
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("\nDémarrage du serveur...")
    uvicorn.run(app, host="0.0.0.0", port=8000)