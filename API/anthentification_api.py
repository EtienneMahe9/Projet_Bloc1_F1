import os
import jwt
import datetime
from fastapi import FastAPI, Query, Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import mysql.connector
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Configuration de la sécurité
security = HTTPBearer()

# Modèle pour l'authentification
class TokenRequest(BaseModel):
    password: str
    duration: Optional[int] = 3600  # Durée en secondes (1h par défaut)

def create_jwt(duration: int) -> str:
    """
    Fonction qui permet de générer un token JWT
    
    :param duration: Durée de validité du token en secondes
    :return: Token JWT encodé
    """
    expiration = datetime.datetime.utcnow() + datetime.timedelta(seconds=duration)
    return jwt.encode(
        {"exp": expiration},
        SECRET_KEY,
        algorithm="HS256"
    )

@app.post("/token")
def generate_token(request: TokenRequest):
    """
    Route qui permet de générer un token pour un utilisateur qui saisit son mot de passe
    
    :param request: Objet TokenRequest contenant le mot de passe et la durée
    :return: Token JWT
    """
    if request.password != API_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    token = create_jwt(request.duration)
    return {"token": token}

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Fonction qui permet de vérifier le token JWT
    
    :param credentials: Credentials fournis via le bearer token
    :return: None
    :raises: HTTPException si le token est invalide ou expiré
    """
    try:
        jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_db_connection():
    """
    Fonction qui permet de se connecter à la base de données MySQL
    
    :return: Objet connexion à la base de données
    """
    return mysql.connector.connect(
        host="localhost",
        user=USER,
        password=PASSWORD,
        database="employees"
    )

@app.get("/employees")
async def get_employees(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    last_name: Optional[str] = Query(None, alias="last_name"),
    birth_date: Optional[str] = Query(None, alias="birth_date"),
    gender: Optional[str] = Query(None, alias="gender"),
    limit: Optional[int] = Query(10, alias="limit")
):
    """
    Route qui permet de récupérer les employés en fonction de différents critères
    
    :param credentials: Credentials pour l'authentification
    :param last_name: Nom de famille de l'employé
    :param birth_date: Date de naissance de l'employé
    :param gender: Genre de l'employé
    :param limit: Nombre d'employés limite à retourner
    :return: Liste des employés
    """
    # Vérification du token
    await verify_token(credentials)
    
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = "SELECT * FROM employees WHERE 1=1"
    params = []

    if last_name:
        query += " AND last_name = %s"
        params.append(last_name)
    if birth_date:
        query += " AND birth_date = %s"
        params.append(birth_date)
    if gender:
        query += " AND gender = %s"
        params.append(gender)

    query += " LIMIT %s"
    params.append(limit)

    cursor.execute(query, params)
    results = cursor.fetchall()

    cursor.close()
    connection.close()

    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)