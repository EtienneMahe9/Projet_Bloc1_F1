
import os

import jwt
import datetime
from fastapi import FastAPI, Query, Depends, HTTPException, Header
import mysql.connector
from typing import Optional
from pydantic import BaseModel

from dotenv import load_dotenv

load_dotenv()

USER = os.getenv("USER_MYSQL")
PASSWORD = os.getenv("PASSWORD_MYSQL")

SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSWORD = os.getenv("API_PASSWORD")

app = FastAPI()

# Modèle pour l’authentification
class TokenRequest(BaseModel):
    password: str
    duration: Optional[int] = 3600  # Durée en secondes (1h par défaut)

# Fonction pour générer un JWT
def create_jwt(duration: int):
    """
    Fonction qui permet de générer un token JWT
    """
    expiration = datetime.datetime.now() + datetime.timedelta(seconds=duration)
    payload = {"exp": expiration}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

# Route pour obtenir un token
@app.post("/token")
def generate_token(request: TokenRequest):

    """
    Fonction/route qui permet de générer un token pour un utilisateur qui saisi son mot de passe

    :param request: Objet TokenRequest
    """

    if request.password != API_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    token = create_jwt(request.duration)
    return {"token": token}

# Vérification du token
def verify_token(authorization: Optional[str] = Header(None)):

    """
    Fonction qui permet de vérifier le token

    :param authorization: Token JWT

    :return: None
    """
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    
    token = authorization.split("Bearer ")[1]
    
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Connexion MySQL
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

@app.get("/employees", dependencies=[Depends(verify_token)])
def get_employees(
    last_name: Optional[str] = Query(None, alias="last_name"),
    birth_date: Optional[str] = Query(None, alias="birth_date"),
    gender: Optional[str] = Query(None, alias="gender"),
    limit: Optional[int] = Query(10, alias="limit")
    ):

    """
    Fonction qui permet de récupérer les employés en fonction de différents critères

    :param last_name: Nom de famille de l'employé
    :param birth_date: Date de naissance de l'employé
    :param gender: Genre de l'employé
    :param limit: Nombre d'employés limite à retourner

    :return: Liste des employés
    """
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