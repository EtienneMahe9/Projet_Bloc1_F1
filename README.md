# Projet d'Analyse des Performances F1

## Présentation du Projet

Ce projet d'analyse de données vise à réaliser une étude approfondie des données historiques de la Formule 1 depuis sa création en 1950, . En exploitant plus de 70 ans d'histoire de la compétition, nous cherchons à identifier les tendances, les facteurs de succès et les stratégies gagnantes qui ont façonné ce sport prestigieux.


## Contexte et Importance

La Formule 1 représente le sommet du sport automobile mondial, avec une riche histoire de plus de 70 ans. Elle se distingue par son excellence technologique, ses voitures ultra-sophistiquées et ses moteurs hybrides développant plus de 1000 chevaux. Cette compétition d'élite a vu naître des légendes comme Michael Schumacher et Lewis Hamilton (7 titres chacun), ainsi que des écuries emblématiques comme Ferrari, Williams et McLaren.

Dans cet univers où la performance se mesure en millièmes de seconde, l'analyse de données est devenue un avantage compétitif crucial. Notre projet s'inscrit dans cette démarche d'optimisation continue, en mettant à profit les techniques modernes de data science pour extraire des connaissances précieuses des données historiques.

## Objectifs Détaillés du Projet

### Analyse Historique Complète
- Étude chronologique de l'évolution des performances des écuries depuis 1950
- Identification des facteurs technologiques et réglementaires ayant influencé les performances
- Création d'indicateurs de performance normalisés pour comparer différentes époques


### Identification des Variables Clés de Succès
- Étude des données télémétriques et leur corrélation avec les performances en course


## Architecture Détaillée du Projet

### Collecte de Données

#### Sources de Données Primaires
**Formula1.com** : Source officielle et fiable pour les données essentielles
   - Utilisation avancée de la bibliothèque `requests` en Python
   - Implémentation d'un système de gestion intelligente des taux de requêtes pour éviter les limitations
   - Validation systématique des données via des schémas prédéfinis
   - Extraction des résultats de courses, positions des pilotes et informations détaillées sur les circuits
   - Traitement des pages HTML avec analyse structurée des tables et éléments dynamiques

**API FastF1** : Source spécialisée pour les données détaillées et techniques
   - Implémentation d'une classe personnalisée `F1Scraper` utilisant BeautifulSoup4 pour le parsing avancé
   - Utilisation de délais aléatoires entre les requêtes (1.5-3.0 secondes) pour respecter les politiques des serveurs
   - Rotation systématique des User-Agents pour imiter différents navigateurs
   - Récupération des données spécifiques comme les temps de qualification, temps par secteur et stratégies de course
   - Gestion sophistiquée des erreurs avec mécanisme de retry (jusqu'à 3 tentatives)

#### Traitement et Nettoyage des Données
- Vérification rigoureuse de la cohérence des formats de date (conversion des formats britanniques/américains)
- Harmonisation des unités de mesure (conversion mph/km/h, temps en secondes, etc.)
- Normalisation des noms des pilotes et écuries pour assurer la consistance sur toute la période historique
- Algorithmes de détection des valeurs aberrantes basés sur des méthodes statistiques (Z-score, IQR)
- Système de résolution des doublons avec règles de priorité des sources
- Génération de fichiers CSV intermédiaires structurés couvrant l'ensemble des 70+ années de compétition

### Automatisation et Orchestration 

#### Système Crontab
- Implémentation d'un système d'exécution automatique des scripts après chaque Grand Prix
- Configuration précise des tâches avec spécification des minutes, heures, jours du mois, mois et jours de la semaine
- Exemple détaillé de configuration pour le calendrier 2025 :
  ```
  # GP d'Australie (16 mars 2025)
  0 10 17 3 * python3 /Users/etiennemahe/Desktop/PROJET_F1/Scrapping/Project_F1/Scrapping_Agregation_Nettoyage.py
  ```
- Journalisation automatique des exécutions avec suivi des erreurs et succès
- Mécanismes de reprise en cas d'échec avec notifications par email

### Architecture des Bases de Données 

#### Base de Données Relationnelle (MySQL)
- Conception normalisée suivant les principes de la 3ème forme normale (3NF)
- Tables principales :
  - `drivers` : Informations sur les pilotes (id, nom, nationalité)
  - `constructors` : Données des écuries (id, nom, nationalité)
  - `races` : Détails des courses (id, année, circuit, date)
  - `results` : Résultats des courses (position, points, temps)
  

#### Base de Données NoSQL (MongoDB)
- Architecture flexible adaptée aux données variables comme la télémétrie
- Collections principales :
  - `weather` : Conditions météorologiques (température, humidité, vent)
  - `telemetry` : Données télémétriques détaillées des voitures
  - `lap_times` : Temps au tour et performances sectorielles


#### Modélisation Sophistiquée des Données
- **Modèle Conceptuel de Données (MCD)** : Représentation logique avec entités et associations
  - Entités principales : RACES, DRIVERS, CONSTRUCTORS, WEATHER_CONDITIONS, LAP_RECORDS
  - Associations avec cardinalités précises (0,N pour "plusieurs possibles", 1,1 pour "exactement un")
  - Attributs détaillés pour chaque entité (ex: pour WEATHER_CONDITIONS: temperature, humidity, wind_speed, etc.)

- **Modèle Physique de Données (MPD)** : Traduction technique du MCD
  - Spécification des types de données (INTEGER, VARCHAR(100), FLOAT, etc.)
  - Définition des clés primaires (PK) et étrangères (FK)
  - Mise en place des contraintes d'intégrité référentielle

### API REST

#### Framework et Architecture
- Utilisation de Pydantic pour la validation des données et la génération automatique de la documentation
- Implémentation de requêtes pour maximiser les performances et le débit
- Structure organisée par domaines fonctionnels (routes pour pilotes, écuries, circuits, etc.)

#### Sécurité et Authentification Robuste
- Système d'authentification basé sur JWT (JSON Web Tokens) avec rotation des clés
- Durée de vie configurable des tokens avec refresh tokens
- Hachage sécurisé des mots de passe avec bcrypt et salt
- Limitation du taux de requêtes pour prévenir les abus
- Headers sécurisés 

#### Endpoints Principaux avec Fonctionnalités Détaillées
- `/races/{year}` : Accès aux informations des courses par année et circuit

- `/driver/{driver_name}` : Statistiques détaillées des pilotes

- `/performance/{circuit}` : Analyse des performances par circuit
  - Évolution des temps au tour au fil des années
  - Impact des conditions météorologiques sur les performances
  - Comparaison des stratégies gagnantes

- `/championship/races/{year}` : Classement du championnat pour une saison donnée
  - Évolution des points course par course
  - Prédiction des chances de titre basée sur les performances historiques

#### Documentation 
- Interface Swagger UI entièrement personnalisée aux couleurs de la F1
- Tests des endpoints directement depuis l'interface

#### Optimisations Techniques
- Système de cache intelligent avec invalidation sélective
  - Mise en cache des données historiques rarement modifiées
  - Rafraîchissement automatique des données récentes
  - Cache à plusieurs niveaux (mémoire, disque)

- Gestion robuste des erreurs et exceptions
  - Fallback gracieux en cas d'indisponibilité des données
  - Journalisation détaillée des problèmes
  - Mécanismes de récupération automatique

- Performance optimisée
  - Chargement asynchrone des composants lourds
  - Actualisation sélective des graphiques
  - Compression des données pour minimiser les transferts

## Technologies et Stack Technique

### Langages de Programmation
- **Python 3.9+** : Langage principal pour le traitement des données, l'API et le dashboard
- **SQL** : Pour les requêtes complexes sur la base de données relationnelle

### Bibliothèques et Frameworks Python
- **Collecte et Traitement de Données**
  - Requests 2.28.1 : Gestion des requêtes HTTP
  - BeautifulSoup4 4.11.1 : Parsing HTML avancé
  - Pandas 1.5.2 : Manipulation et analyse des données
  - NumPy 1.23.4 : Calculs numériques avancés
  - Scikit-learn 1.1.3 : Algorithmes de machine learning

- **Développement API**
  - FastAPI 0.89.1 : Framework API haute performance
  - Uvicorn 0.20.0 : Serveur ASGI pour FastAPI
  - Python-jose 3.3.0 : Implémentation JWT
  - Passlib 1.7.4 : Gestion des mots de passe et hachage
  - Pydantic 1.10.4 : Validation de données

### Bases de Données et Stockage
- **MySQL 8.0** : Système de gestion de base de données relationnelle
  - mysql-connector-python 8.0.31 : Connecteur Python pour MySQL
  - SQLAlchemy 2.0.0 : ORM pour l'abstraction de la base de données

- **MongoDB 5.0** : Base de données NoSQL orientée documents
  - PyMongo 4.3.3 : Driver Python pour MongoDB
  - Motor 3.1.1 : Driver asynchrone pour MongoDB

### Outils de Développement et d'Opérations
- **Gestion de Version**
  - Git 2.39.0 : Système de contrôle de version
  - GitHub : Plateforme de gestion de dépôt

- **Automatisation et Déploiement**
  - Crontab : Planification des tâches sur Unix/Linux

- **Tests et Qualité du Code**
  - Pytest 7.2.1 : Framework de test

- **Documentation**
  - Swagger UI / OpenAPI : Documentation interactive de l'API

## Installation et Déploiement Détaillé

### Prérequis Système
- **Système d'exploitation** : Linux (Ubuntu 20.04+ recommandé), macOS, ou Windows 10+
- **Python** : Version 3.9 ou supérieure
- **Mémoire** : Minimum 8 Go RAM recommandé
- **Espace disque** : Minimum 10 Go disponibles
- **Services externes** : Accès Internet pour le scraping initial

### Installation Pas à Pas

**Clonage du dépôt Git**
   ```bash
   git clone https://github.com/votre-username/projet-f1-analyse.git
   cd projet-f1-analyse
   ```

**Création et activation d'un environnement virtuel Python**
   ```bash
   # Pour Linux/macOS
   python3 -m venv venv
   source venv/bin/activate
   
   # Pour Windows
   python -m venv venv
   venv\Scripts\activate
   ```

**Installation des dépendances**
   ```bash
   pip install -r requirements.txt
   ```

**Configuration des variables d'environnement**
   Créez un fichier `.env` à la racine du projet avec les paramètres suivants :
   ```
   # Configuration des bases de données
   MYSQL_HOST=localhost
   MYSQL_USER=votre_utilisateur
   MYSQL_PASSWORD=votre_mot_de_passe
   MYSQL_DATABASE=f1_database
   
   MONGODB_URI=mongodb://localhost:27017
   MONGODB_DB=f1_nosql_db
   
   # Configuration de l'API
   API_SECRET_KEY=votre_clé_secrète
   API_TOKEN_EXPIRATION=3600
   
   # Configuration du scraping
   SCRAPING_DELAY_MIN=1.5
   SCRAPING_DELAY_MAX=3.0
   SCRAPING_MAX_RETRIES=3
   ```

**Mise en place des bases de données**

   **Pour MySQL :**
   ```bash
   # Créez la base de données
   mysql -u root -p
   ```
   ```sql
   CREATE DATABASE f1_database CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'f1_user'@'localhost' IDENTIFIED BY 'password';
   GRANT ALL PRIVILEGES ON f1_database.* TO 'f1_user'@'localhost';
   FLUSH PRIVILEGES;
   EXIT;
   ```
   
   **Pour MongoDB :**
   Assurez-vous que le service MongoDB est en cours d'exécution :
   ```bash
   sudo systemctl start mongod
   # Vérifiez le statut
   sudo systemctl status mongod
   ```

**Initialisation des bases de données**
   ```bash
   python scripts/setup_databases.py
   ```

**Collecte initiale des données historiques**
   ```bash
   python scripts/initial_data_scraping.py
   ```
   Note : Cette opération peut prendre plusieurs heures en fonction de la quantité de données à collecter.

**Configuration des tâches Crontab**
   ```bash
   crontab -e
   ```
   Ajoutez les lignes de configuration pour les Grands Prix comme indiqué dans la section Automatisation.

## Utilisation Détaillée

### API REST

#### Authentification et Obtention d'un Token
```python
import requests

def get_auth_token():
    response = requests.post(
        "http://localhost:8000/token",
        json={
            "password": "notre_mot_de_passe_api",
            "duration": 3600  # Durée de validité en secondes (1 heure)
        }
    )
    if response.status_code == 200:
        return response.json()["token"]
    else:
        raise Exception(f"Erreur d'authentification: {response.text}")

# Utilisation
token = get_auth_token()
headers = {"Authorization": f"Bearer {token}"}
```

#### Exemples d'Utilisation des Endpoints

**Obtenir les Statistiques d'un Pilote**
   ```python
   def get_driver_stats(driver_name, year=None):
       params = {}
       if year:
           params["year"] = year
           
       response = requests.get(
           f"http://localhost:8000/drivers/{driver_name}/stats",
           headers=headers,
           params=params
       )
       
       if response.status_code == 200:
           return response.json()
       else:
           print(f"Erreur: {response.status_code} - {response.text}")
           return None
   
   # Exemple d'utilisation
   hamilton_stats = get_driver_stats("Lewis Hamilton", 2021)
   print(f"Victoires en 2021: {hamilton_stats['wins']}")
   print(f"Podiums en 2021: {hamilton_stats['podiums']}")
   print(f"Points totaux: {hamilton_stats['total_points']}")
   ```

**Analyser les Performances sur un Circuit**
   ```python
   def analyze_circuit_performance(circuit_name, top_drivers=5, year=None):
       params = {"limit": top_drivers}
       if year:
           params["year"] = year
           
       response = requests.get(
           f"http://localhost:8000/performance/{circuit_name}",
           headers=headers,
           params=params
       )
       
       if response.status_code == 200:
           return response.json()
       else:
           print(f"Erreur: {response.status_code} - {response.text}")
           return None
   
   # Exemple d'utilisation
   monza_analysis = analyze_circuit_performance("Monza", top_drivers=3, year=2023)
   
   print("Top 3 pilotes à Monza en 2023:")
   for i, result in enumerate(monza_analysis):
       print(f"{i+1}. {result['driver']} ({result['constructor']}) - {result['avg_speed']} km/h de moyenne")
   ```

**Récupérer les Résultats d'une Saison**
   ```python
   def get_season_results(year):
       response = requests.get(
           f"http://localhost:8000/championship/races/{year}/detailed",
           headers=headers
       )
       
       if response.status_code == 200:
           return response.json()
       else:
           print(f"Erreur: {response.status_code} - {response.text}")
           return None
   
   # Exemple d'utilisation
   season_2023 = get_season_results(2023)
   
   print(f"Résultats du Championnat {season_2023['year']}:")
   
   print("\nClassement Pilotes:")
   for i, driver in enumerate(season_2023['drivers_standings']):
       print(f"{i+1}. {driver['name']} - {driver['points']} pts")
   
   print("\nClassement Constructeurs:")
   for i, team in enumerate(season_2023['constructors_standings']):
       print(f"{i+1}. {team['name']} - {team['points']} pts")
   ```



## Maintenance et Mise à Jour

### Mises à Jour des Données
- Après chaque Grand Prix, les données sont automatiquement collectées via les tâches Crontab


## Contributeurs et Contacts

### Développement par:
- **MAHE ETIENNE** - Apprenti en Intelligence Artificielle



## Licence et Droits d'Utilisation

Ce projet est développé dans le cadre d'une formation de Développeur en Intelligence Artificielle. Il s'agit d'un projet visant à mettre en pratique diverses compétences techniques dans le domaine de la data science et du machine learning.
Le projet utilise des données publiques de Formule 1 à des fins éducatives uniquement. Les noms, logos et marques associés à la Formule 1 et autres entités mentionnées dans ce projet sont la propriété de leurs détenteurs respectifs et sont utilisés dans un cadre académique sans intention commerciale.

Le code source et la documentation associés à ce projet sont fournis à titre informatif. L'utilisation, la reproduction ou la distribution de ce code et des données associées à des fins autres qu'éducatives sans autorisation explicite est strictement interdite.

---


2025 - Projet F1 Analyse - MAHE ETIENNE
