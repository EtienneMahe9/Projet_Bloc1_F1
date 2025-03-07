from fastapi import FastAPI, HTTPException, Depends, status, Query
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
    """
    Classe de configuration pour les paramètres de l'API.
    Charge les variables d'environnement nécessaires pour:
    - Connexion MySQL
    - Connexion MongoDB
    - Sécurité (clé secrète JWT et mot de passe API)
    """
    USER_MYSQL = os.getenv("USER_MYSQL")
    PASSWORD_MYSQL = os.getenv("PASSWORD_MYSQL")
    SECRET_KEY = os.getenv("SECRET_KEY")
    API_PASSWORD = os.getenv("API_PASSWORD")
    MONGO_URI = os.getenv("MONGO_URI")

settings = Settings()

# Configuration FastAPI
app = FastAPI(
    title="F1 API",
    description="""
    API complète pour accéder aux données historiques et actuelles de la Formule 1.
    
    Cette API permet d'interroger les courses, les statistiques des pilotes, les performances sur circuit 
    et les classements des championnats via une architecture sécurisée par authentification JWT.
    
    Utilisez cette API pour développer des applications d'analyse statistique, des dashboards de visualisation,
    ou alimenter vos sites web et applications mobiles dédiés à la F1.
    """,
    version="3.9.5",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1}
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
    """
    Modèle pour les requêtes de génération de token.
    """
    password: str
    duration: Optional[int] = 3600

def create_jwt(duration: int) -> str:
    """
    Crée un token JWT valide pour la durée spécifiée.
    """
    expiration = datetime.datetime.utcnow() + datetime.timedelta(seconds=duration)
    return jwt.encode(
        {"exp": expiration},
        settings.SECRET_KEY,
        algorithm="HS256"
    )

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Vérifie la validité d'un token JWT.
    """
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
    """
    Établit une connexion à la base de données MySQL.
    """
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
    """
    Établit une connexion à la base de données MongoDB.
    """
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
    """
    # Route racine
    
    Vérifie que l'API est en cours d'exécution.
    
    ## Retour
    ```json
    {
        "message": "F1 API is running"
    }
    ```
    
    ## Authentification
    - Ne nécessite pas d'authentification
    """
    return {"message": "F1 API is running"}

@app.post("/token")
async def generate_token(request: TokenRequest):
    """
    # Génération de token
    
    Génère un token JWT pour accéder aux endpoints protégés de l'API.
    
    ## Paramètres
    - **password** (str): Mot de passe API pour authentifier la demande
    - **duration** (int, optionnel): Durée de validité du token en secondes (défaut: 3600)
    
    ## Retour
    ```json
    {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```
    
    ## Erreurs
    - **401 Unauthorized**: Si le mot de passe est incorrect
    
    ## Authentification
    - Ne nécessite pas d'authentification
    """
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
    """
    # Liste des courses
    
    Récupère la liste des courses pour une année donnée, avec possibilité de filtrer par circuit.
    
    ## Paramètres
    - **year** (int): Année pour laquelle récupérer les courses
    - **circuit** (str, optionnel): Nom du circuit pour filtrer les résultats
    
    ## Retour
    Liste des courses correspondant aux critères, chaque course contenant:
    ```json
    [
        {
            "id": 1,
            "race_name": "Grand Prix d'Australie",
            "circuit": "Albert Park",
            "date": "2023-03-05",
            "year": 2023
        },
        ...
    ]
    ```
    
    ## Erreurs
    - **401 Unauthorized**: Si le token est invalide ou expiré
    - **500 Internal Server Error**: Si une erreur de base de données survient
    
    ## Authentification
    - Nécessite un token JWT valide
    """
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
    """
    # Statistiques d'un pilote
    
    Récupère les statistiques d'un pilote, globales ou pour une année spécifique.
    
    ## Paramètres
    - **driver_name** (str): Nom du pilote
    - **year** (int, optionnel): Année pour laquelle récupérer les statistiques
    
    ## Retour
    Liste des statistiques par année, contenant:
    ```json
    [
        {
            "year": 2023,
            "races": 22,
            "total_points": 356,
            "wins": 8
        },
        ...
    ]
    ```
    
    ## Erreurs
    - **401 Unauthorized**: Si le token est invalide ou expiré
    - **500 Internal Server Error**: Si une erreur de base de données survient
    
    ## Authentification
    - Nécessite un token JWT valide
    """
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
    """
    # Performances sur circuit
    
    Récupère les données de performance (vitesses) pour un circuit spécifique.
    
    ## Paramètres
    - **circuit** (str): Nom du circuit
    - **year** (int, optionnel): Année pour laquelle récupérer les performances
    
    ## Retour
    Liste des performances par année et course, contenant:
    ```json
    [
        {
            "_id": {
                "year": 2023,
                "race_name": "Grand Prix de Monaco"
            },
            "avg_speed": 213.5,
            "max_speed": 325.2
        },
        ...
    ]
    ```
    
    ## Erreurs
    - **401 Unauthorized**: Si le token est invalide ou expiré
    - **500 Internal Server Error**: Si une erreur de base de données survient
    
    ## Authentification
    - Nécessite un token JWT valide
    """
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

@app.get("/championship/races/{year}")
async def get_race_championship(
    year: int,
    token: str = Depends(verify_token)
):
    """
    # Classement des Grands Prix
    
    Récupère le classement simplifié des Grands Prix pour une année donnée.
    
    ## Paramètres
    - **year** (int): Année pour laquelle récupérer le classement
    
    ## Retour
    Liste des courses de l'année avec informations agrégées:
    ```json
    [
        {
            "id": 1,
            "race_name": "Grand Prix d'Australie",
            "circuit": "Albert Park",
            "date": "2023-03-05",
            "total_drivers": 20,
            "max_points": 25,
            "winner": "Max Verstappen"
        },
        ...
    ]
    ```
    
    ## Erreurs
    - **401 Unauthorized**: Si le token est invalide ou expiré
    - **500 Internal Server Error**: Si une erreur de base de données survient
    
    ## Authentification
    - Nécessite un token JWT valide
    """
    connection = None
    cursor = None
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT 
            r.id,
            r.race_name,
            r.circuit,
            r.date,
            COUNT(DISTINCT rr.driver) as total_drivers,
            MAX(rr.points) as max_points,
            GROUP_CONCAT(DISTINCT 
                CASE WHEN rr.position = 1 THEN rr.driver ELSE NULL END
            ) as winner
        FROM races r
        JOIN race_results rr ON r.id = rr.race_id
        WHERE r.year = %s
        GROUP BY r.id, r.race_name, r.circuit, r.date
        ORDER BY r.date
        """
        params = [year]

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

@app.get("/championship/races/{year}/detailed")
async def get_detailed_race_championship(
    year: int,
    limit: Optional[int] = Query(3, description="Nombre de premières positions à afficher"),
    token: str = Depends(verify_token)
):
    """
    # Classement détaillé des Grands Prix
    
    Récupère le classement détaillé des Grands Prix pour une année donnée,
    incluant les informations de podium pour chaque course.
    
    ## Paramètres
    - **year** (int): Année pour laquelle récupérer le classement
    - **limit** (int, optionnel): Nombre de positions à inclure dans le podium (défaut: 3)
    
    ## Retour
    Liste des courses avec détails du podium:
    ```json
    [
        {
            "id": 1,
            "race_name": "Grand Prix d'Australie",
            "circuit": "Albert Park",
            "date": "2023-03-05",
            "podium": [
                {
                    "driver": "Max Verstappen",
                    "constructor": "Red Bull Racing",
                    "position": 1,
                    "points": 25
                },
                {
                    "driver": "Lewis Hamilton",
                    "constructor": "Mercedes",
                    "position": 2,
                    "points": 18
                },
                {
                    "driver": "Fernando Alonso",
                    "constructor": "Aston Martin",
                    "position": 3,
                    "points": 15
                }
            ]
        },
        ...
    ]
    ```
    
    ## Erreurs
    - **401 Unauthorized**: Si le token est invalide ou expiré
    - **500 Internal Server Error**: Si une erreur de base de données survient
    
    ## Authentification
    - Nécessite un token JWT valide
    """
    connection = None
    cursor = None
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)

        # Récupérer la liste des courses
        races_query = "SELECT id, race_name, circuit, date FROM races WHERE year = %s ORDER BY date"
        cursor.execute(races_query, [year])
        races = cursor.fetchall()

        if not races:
            return {"message": f"No races found for year {year}"}

        # Pour chaque course, récupérer le podium
        for race in races:
            podium_query = """
            SELECT driver, constructor, position, points
            FROM race_results
            WHERE race_id = %s AND position <= %s
            ORDER BY position
            """
            cursor.execute(podium_query, [race['id'], limit])
            race['podium'] = cursor.fetchall()

        return races

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)