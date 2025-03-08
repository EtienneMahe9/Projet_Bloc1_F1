"""
Description:
------------
Ce script automatise la collecte, le stockage et la mise à disposition de données 
de courses de Formule 1 et de données météorologiques associées.
"""

import requests
import pandas as pd
import json
import os
import time
import random
import logging
import sys
import hashlib
import configparser
from datetime import datetime, timedelta
from pathlib import Path

# Constantes globales
CONFIG_FILE = "f1_config.ini"
DEFAULT_CACHE_DIR = "cache"
DEFAULT_DATA_DIR = "data"
DEFAULT_LOG_DIR = "logs"
DEFAULT_DB_PATH = "f1_data.db"

# Configuration par défaut
DEFAULT_CONFIG = {
    "general": {
        "cache_dir": DEFAULT_CACHE_DIR,
        "data_dir": DEFAULT_DATA_DIR,
        "log_dir": DEFAULT_LOG_DIR,
        "log_level": "INFO",
        "use_cache": "True",
        "years_to_collect": "5",
    },
    "apis": {
        "ergast_base_url": "http://ergast.com/api/f1",
        "openmeteo_base_url": "https://archive-api.open-meteo.com/v1/archive",
        "max_retries": "3",
        "retry_wait": "5"
    },
    "web_scraping": {
        "min_delay": "3.0",
        "max_delay": "7.0",
    }
}

# Initialisation du logging
def init_logging(log_dir, log_level="INFO"):
    """Configure le système de journalisation"""
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    
    # Génère un nom de fichier basé sur la date
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir_path / f"f1_data_{timestamp}.log"
    
    # Niveau de log
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    level = levels.get(log_level.upper(), logging.INFO)
    
    # Configuration
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logging.info(f"Journalisation initialisée, fichier: {log_file}")
    
    return log_file

# Chargement de la configuration
def load_config(config_file=CONFIG_FILE):
    """Charge ou crée un fichier de configuration"""
    config = configparser.ConfigParser()
    
    if os.path.exists(config_file):
        try:
            config.read(config_file)
            logging.info(f"Configuration chargée depuis {config_file}")
        except Exception as e:
            logging.error(f"Erreur lors du chargement de la configuration: {str(e)}")
            create_default_config(config, config_file)
    else:
        create_default_config(config, config_file)
        
    return config

def create_default_config(config, config_file):
    """Crée un fichier de configuration par défaut"""
    for section, options in DEFAULT_CONFIG.items():
        if not config.has_section(section):
            config.add_section(section)
        for option, value in options.items():
            config.set(section, option, value)
    
    try:
        with open(config_file, 'w') as f:
            config.write(f)
        logging.info(f"Configuration par défaut créée dans {config_file}")
    except Exception as e:
        logging.error(f"Erreur lors de la création de la configuration par défaut: {str(e)}")

# Fonctions pour le cache de données
def get_from_cache(cache_dir, key):
    """Récupère des données du cache"""
    filepath = Path(cache_dir) / f"{key}.json"
    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logging.debug(f"Données récupérées du cache: {key}")
            return data
        except Exception as e:
            logging.warning(f"Erreur lors de la lecture du cache pour {key}: {str(e)}")
            return None
    return None

def save_to_cache(cache_dir, key, data):
    """Enregistre des données dans le cache"""
    filepath = Path(cache_dir) / f"{key}.json"
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logging.debug(f"Données enregistrées dans le cache: {key}")
    except Exception as e:
        logging.error(f"Erreur lors de l'écriture dans le cache pour {key}: {str(e)}")

# Fonctions pour les API F1
def fetch_ergast_data(base_url, endpoint, max_retries=3, retry_wait=5):
    """Récupère des données depuis l'API Ergast"""
    url = f"{base_url}/{endpoint}"
    logging.debug(f"Récupération des données: {url}")
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.warning(f"Tentative {attempt+1}/{max_retries} échouée: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_wait)
            else:
                logging.error(f"Échec de la récupération des données après {max_retries} tentatives")
                raise

def get_season_data(base_url, year, max_retries=3, retry_wait=5, cache_dir=None):
    """Récupère les données d'une saison de F1"""
    cache_key = f"season_{year}"
    
    # Vérifier le cache
    if cache_dir:
        cached_data = get_from_cache(cache_dir, cache_key)
        if cached_data:
            return cached_data
    
    try:
        endpoint = f"{year}.json"
        result = fetch_ergast_data(base_url, endpoint, max_retries, retry_wait)
        
        # Vérifier le format des données
        if 'MRData' not in result or 'RaceTable' not in result['MRData']:
            raise Exception(f"Format de données invalide pour la saison {year}")
        
        # Sauvegarder dans le cache
        if cache_dir:
            save_to_cache(cache_dir, cache_key, result)
            
        return result
        
    except Exception as e:
        logging.error(f"Erreur lors de la récupération des données de saison {year}: {str(e)}")
        return None

def get_race_results(base_url, year, round_number, max_retries=3, retry_wait=5, cache_dir=None):
    """Récupère les résultats d'une course"""
    cache_key = f"race_{year}_{round_number}"
    
    # Vérifier le cache
    if cache_dir:
        cached_data = get_from_cache(cache_dir, cache_key)
        if cached_data:
            return cached_data
    
    try:
        endpoint = f"{year}/{round_number}/results.json"
        result = fetch_ergast_data(base_url, endpoint, max_retries, retry_wait)
        
        # Vérifier le format des données
        if ('MRData' not in result or 'RaceTable' not in result['MRData'] or 
            'Races' not in result['MRData']['RaceTable'] or 
            len(result['MRData']['RaceTable']['Races']) == 0):
            raise Exception(f"Format de données invalide pour {year} round {round_number}")
        
        # Sauvegarder dans le cache
        if cache_dir:
            save_to_cache(cache_dir, cache_key, result)
            
        return result
        
    except Exception as e:
        logging.error(f"Erreur lors de la récupération des résultats: {str(e)}")
        return None

# Fonction pour récupérer les données météo
def get_weather_data(base_url, lat, lon, date, max_retries=3, retry_wait=5):
    """Récupère les données météo historiques pour une localisation et une date"""
    try:
        # Format des dates pour l'API
        start_date = date.strftime("%Y-%m-%d")
        end_date = (date + timedelta(days=1)).strftime("%Y-%m-%d")
        
        params = {
            'latitude': lat,
            'longitude': lon,
            'start_date': start_date,
            'end_date': end_date,
            'hourly': 'temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,surface_pressure'
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.get(base_url, params=params)
                response.raise_for_status()
                result = response.json()
                
                # Récupération des données pour l'heure de la course (14h00 par défaut)
                race_hour = 14
                hourly_data = result['hourly']
                hour_index = race_hour
                
                weather_data = {
                    'temperature': hourly_data['temperature_2m'][hour_index],
                    'humidity': hourly_data['relative_humidity_2m'][hour_index],
                    'wind_speed': hourly_data['wind_speed_10m'][hour_index],
                    'wind_direction': hourly_data['wind_direction_10m'][hour_index],
                    'precipitation': hourly_data['precipitation'][hour_index],
                    'pressure': hourly_data['surface_pressure'][hour_index]
                }
                
                logging.debug(f"Données météo récupérées pour {start_date}")
                return weather_data
                
            except Exception as e:
                logging.warning(f"Tentative {attempt+1}/{max_retries} échouée: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_wait)
                else:
                    raise
                    
    except Exception as e:
        logging.error(f"Erreur lors de la récupération des données météo: {str(e)}")
        return None

# Fonction pour le web scraping
def fetch_page(url, min_delay=3.0, max_delay=7.0, max_retries=3):
    """Récupère une page web"""
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.8,en-US;q=0.5,en;q=0.3',
        'Connection': 'keep-alive',
        'DNT': '1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.67 Safari/537.36'
    }
    
    for attempt in range(max_retries):
        try:
            logging.debug(f"Récupération de la page: {url}")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Délai pour éviter de surcharger le serveur
            delay = random.uniform(min_delay, max_delay)
            time.sleep(delay)
            
            logging.debug(f"Page récupérée avec succès: {url} ({len(response.text)} caractères)")
            return response.text
            
        except Exception as e:
            logging.warning(f"Tentative {attempt+1}/{max_retries} échouée: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2)  # Court délai avant nouvelle tentative
            else:
                logging.error(f"Échec de la récupération de la page après {max_retries} tentatives")
                return None

# Fonctions pour analyser la collection MongoDB
def print_collection_stats(collection_data):
    """Analyse les données F1 et génère des statistiques"""
    print("\nStatistiques de la base de données:")
    
    # Nombre de courses par année
    print("\nNombre de courses par année:")
    # Récupération des documents groupés par année
    courses_par_annee = {}
    for document in collection_data:
        annee = document.get('year')
        nom_course = document.get('race_name')
        
        # Créer une clé unique année+course pour éviter les doublons
        cle_unique = f"{annee}_{nom_course}"
        
        if annee not in courses_par_annee:
            courses_par_annee[annee] = set()
        
        courses_par_annee[annee].add(cle_unique)
    
    # Affichage des résultats triés par année
    for annee in sorted(courses_par_annee.keys()):
        nombre_courses = len(courses_par_annee[annee])
        print(f"Année {annee}: {nombre_courses} courses")
    
    # Circuits uniques
    print("\nCircuits uniques:")
    circuits_uniques = set()
    
    # Récupération de tous les circuits
    for document in collection_data:
        circuit = document.get('circuit')
        if circuit:
            circuits_uniques.add(circuit)
    
    n_circuits = len(circuits_uniques)
    print(f"\nNombre de circuits uniques: {n_circuits}")
    
    # Pilotes uniques
    print("\nPilotes uniques:")
    pilotes_uniques = set()
    
    # Récupération de tous les pilotes
    for document in collection_data:
        pilote = document.get('driver')
        if pilote:
            pilotes_uniques.add(pilote)
    
    n_drivers = len(pilotes_uniques)
    print(f"Nombre de pilotes uniques: {n_drivers}")

# Fonctions d'analyse des performances par circuit
def get_performance_by_circuit(collection_data, circuit_name):
    """Analyse des performances sur un circuit spécifique"""
    print(f"\nAnalyse des performances sur le circuit: {circuit_name}")
    
    # Filtrer les documents pour le circuit spécifique et les années >= 2021
    filtered_docs = []
    for doc in collection_data:
        if doc.get('circuit') == circuit_name and doc.get('year', 0) >= 2021:
            filtered_docs.append(doc)
    
    if not filtered_docs:
        print(f"Aucune donnée disponible pour {circuit_name}")
        return
    
    # Regrouper par année et race_name
    grouped_data = {}
    for doc in filtered_docs:
        year = doc.get('year')
        race_name = doc.get('race_name')
        key = f"{year}_{race_name}"
        
        if key not in grouped_data:
            grouped_data[key] = {
                'year': year,
                'speeds': [],
                'max_speeds': [],
                'rpm_values': [],
                'lap_times': []
            }
        
        # Extraire les données de performance
        performance = doc.get('performance', {})
        speeds = performance.get('speeds', {})
        
        if 'avg' in speeds:
            grouped_data[key]['speeds'].append(speeds['avg'])
        if 'max' in speeds:
            grouped_data[key]['max_speeds'].append(speeds['max'])
        
        engine = performance.get('engine', {})
        if 'avg_rpm' in engine:
            grouped_data[key]['rpm_values'].append(engine['avg_rpm'])
        
        if 'best_lap_time' in performance:
            grouped_data[key]['lap_times'].append(performance['best_lap_time'])
    
    # Calculer les moyennes et minimums pour chaque groupe
    results = []
    for key, data in grouped_data.items():
        speeds = data['speeds']
        avg_speed = sum(speeds) / len(speeds) if speeds else None
        
        max_speeds = data['max_speeds']
        max_speed = max(max_speeds) if max_speeds else None
        
        rpm_values = data['rpm_values']
        avg_rpm = sum(rpm_values) / len(rpm_values) if rpm_values else None
        
        lap_times = data['lap_times']
        best_lap = min(lap_times) if lap_times else None
        
        results.append({
            'year': data['year'],
            'avg_speed': avg_speed,
            'max_speed': max_speed,
            'avg_rpm': avg_rpm,
            'best_lap_time': best_lap
        })
    
    # Trier par année
    results.sort(key=lambda x: x['year'])
    
    # Afficher les résultats
    for result in results:
        print(f"Année {result['year']}:")
        print(f"  - Vitesse moyenne: {result['avg_speed']:.2f} km/h")
        print(f"  - Vitesse max: {result['max_speed']:.2f} km/h")
        print(f"  - RPM moyen: {result['avg_rpm']:.2f}")
        print(f"  - Meilleur tour: {result['best_lap_time']}")
        print("")

# Fonction d'analyse de l'impact météo
def analyze_weather_impact(collection_data):
    """Analyse de l'impact des conditions météo sur les performances"""
    print("\nAnalyse de l'impact des conditions météorologiques:")
    
    # Récupérer et filtrer tous les documents avec données météo et performance
    weather_data = {
        'Pluie': {'speeds': [], 'count': 0},
        'Sec': {'speeds': [], 'count': 0}
    }
    
    for doc in collection_data:
        # Vérifier si le document a les informations nécessaires
        if not (doc.get('weather') and doc.get('performance') and 
                'speeds' in doc['performance'] and 'avg' in doc['performance']['speeds']):
            continue
        
        # Déterminer la condition météo
        precipitation = doc['weather'].get('precipitation', 0)
        condition = 'Pluie' if precipitation and precipitation > 0 else 'Sec'
        
        # Ajouter la vitesse moyenne
        avg_speed = doc['performance']['speeds']['avg']
        if avg_speed:
            weather_data[condition]['speeds'].append(avg_speed)
            weather_data[condition]['count'] += 1
    
    # Calculer et afficher les moyennes
    for condition, data in weather_data.items():
        if data['speeds']:
            avg_speed = sum(data['speeds']) / len(data['speeds'])
            count = data['count']
            print(f"Condition: {condition}")
            print(f"  - Nombre de courses: {count}")
            print(f"  - Vitesse moyenne: {avg_speed:.2f} km/h")
            print("")
        else:
            print(f"Condition: {condition} - Aucune donnée disponible")

# Fonction principale
def main():
    # Chargement de la configuration
    config = load_config()
    
    # Récupération des paramètres
    log_dir = config.get('general', 'log_dir')
    log_level = config.get('general', 'log_level')
    cache_dir = config.get('general', 'cache_dir')
    
    # Initialisation du logging
    log_file = init_logging(log_dir, log_level)
    
    # Création du répertoire de cache
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    
    # Paramètres des APIs
    ergast_url = config.get('apis', 'ergast_base_url')
    openmeteo_url = config.get('apis', 'openmeteo_base_url')
    max_retries = int(config.get('apis', 'max_retries'))
    retry_wait = int(config.get('apis', 'retry_wait'))
    
    # Liste des années à collecter
    years_to_collect = int(config.get('general', 'years_to_collect'))
    current_year = datetime.now().year
    years = list(range(current_year - years_to_collect, current_year + 1))
    
    # Exemple d'utilisation
    print(f"Collecte des données F1 pour les années: {', '.join(map(str, years))}")
    
    # Collection factice pour test
    test_collection = [
        {
            'year': 2022, 
            'race_name': 'Monaco Grand Prix', 
            'circuit': 'Circuit de Monaco',
            'driver': 'Max Verstappen'
        },
        {
            'year': 2022, 
            'race_name': 'French Grand Prix', 
            'circuit': 'Circuit Paul Ricard',
            'driver': 'Lewis Hamilton'
        },
        {
            'year': 2021, 
            'race_name': 'Monaco Grand Prix', 
            'circuit': 'Circuit de Monaco',
            'driver': 'Max Verstappen',
            'performance': {
                'speeds': {'avg': 180.5, 'max': 240.8},
                'engine': {'avg_rpm': 10500},
                'best_lap_time': '1:13.456'
            },
            'weather': {'precipitation': 0}
        },
        {
            'year': 2021, 
            'race_name': 'Bahrain Grand Prix', 
            'circuit': 'Bahrain International Circuit',
            'driver': 'Charles Leclerc',
            'performance': {
                'speeds': {'avg': 192.3, 'max': 245.1},
                'engine': {'avg_rpm': 10800},
                'best_lap_time': '1:33.456'
            },
            'weather': {'precipitation': 1.5}
        }
    ]
    
    # Démonstration des fonctions simplifiées
    print_collection_stats(test_collection)
    get_performance_by_circuit(test_collection, 'Circuit de Monaco')
    analyze_weather_impact(test_collection)
    
    print("\nTraitement terminé avec succès.")

if __name__ == "__main__":
    main()