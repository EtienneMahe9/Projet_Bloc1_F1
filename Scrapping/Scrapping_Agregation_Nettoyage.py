"""
Description:
------------
Ce script automatise la collecte, le stockage et la mise à disposition de données 
de courses de Formule 1 et de données météorologiques associées. Il utilise plusieurs
sources de données (API Ergast, Open-Meteo API, Web Scraping) pour constituer un jeu
de données complet sur les performances des pilotes et les conditions météorologiques.

Contexte du projet:
------------------
- Objectif fonctionnel: Analyser l'impact des conditions météorologiques sur les performances en F1
- Technologies utilisées: Python, APIs REST, Web Scraping
- Budget: Utilisation d'APIs gratuites pour limiter les coûts
- Organisation: Exécution quotidienne/hebdomadaire possible via planificateur
- Contraintes techniques: Respect des limites de rate des APIs, gestion du cache

Dépendances externes:
--------------------
- requests: Pour les appels API REST
- pandas: Pour la manipulation des données tabulaires
- playwright: Pour le web scraping avancé
- tenacity: Pour la gestion des tentatives et des backoffs
- sqlalchemy (optionnel): Pour la connexion à des bases de données
- fake_useragent: Pour la rotation des user agents
- loguru: Pour une gestion avancée des logs
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import json
import os
import time
import random
import sys
import hashlib
import argparse
import configparser
import shutil
from pathlib import Path
import socket
import platform
import uuid
import re
from typing import Dict, List, Tuple, Union, Optional, Any
import traceback
import tempfile
import csv
import contextlib
import sqlite3
try:
    import sqlalchemy
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

from bs4 import BeautifulSoup
try:
    from fake_useragent import UserAgent
    FAKE_USERAGENT_AVAILABLE = True
except ImportError:
    FAKE_USERAGENT_AVAILABLE = False
    
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Version du script pour le versionnement
__version__ = "1.0.0"

# Constantes globales
CONFIG_FILE = "f1_config.ini"
DEFAULT_CACHE_DIR = "cache"
DEFAULT_DATA_DIR = "data"
DEFAULT_LOG_DIR = "logs"
DEFAULT_DB_PATH = "f1_data.db"
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
        "retry_wait_multiplier": "2",
        "retry_wait_min": "4",
        "retry_wait_max": "30",
    },
    "database": {
        "use_db": "True",
        "db_type": "sqlite",  # sqlite, postgres, mysql
        "db_path": DEFAULT_DB_PATH,
        "db_host": "localhost",
        "db_port": "5432",
        "db_name": "f1_data",
        "db_user": "",
        "db_password": "",
    },
    "web_scraping": {
        "use_playwright": "True",
        "headless": "True",
        "user_agent_rotation": "True",
        "min_delay": "3.0",
        "max_delay": "7.0",
    }
}

class ScriptError(Exception):
    """Exception de base pour les erreurs du script"""
    pass

class ConfigError(ScriptError):
    """Exception pour les erreurs de configuration"""
    pass

class APIError(ScriptError):
    """Exception pour les erreurs d'API"""
    pass

class DatabaseError(ScriptError):
    """Exception pour les erreurs de base de données"""
    pass

class DataExtractionError(ScriptError):
    """Exception pour les erreurs d'extraction de données"""
    pass

class ConfigManager:
    """Gestionnaire de configuration pour le script"""
    
    def __init__(self, config_file=CONFIG_FILE):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()
        
    def load_config(self):
        """Charge la configuration depuis le fichier ou crée une configuration par défaut"""
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file)
                logging.info(f"Configuration chargée depuis {self.config_file}")
            except Exception as e:
                raise ConfigError(f"Erreur lors du chargement de la configuration: {str(e)}")
        else:
            # Création de la configuration par défaut
            for section, options in DEFAULT_CONFIG.items():
                if not self.config.has_section(section):
                    self.config.add_section(section)
                for option, value in options.items():
                    self.config.set(section, option, value)
            try:
                with open(self.config_file, 'w') as f:
                    self.config.write(f)
                logging.info(f"Configuration par défaut créée dans {self.config_file}")
            except Exception as e:
                raise ConfigError(f"Erreur lors de la création de la configuration par défaut: {str(e)}")
    
    def get(self, section, option, fallback=None):
        """Récupère une valeur de configuration"""
        try:
            return self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if fallback is not None:
                return fallback
            raise ConfigError(f"Option de configuration manquante: {section}.{option}")
            
    def get_int(self, section, option, fallback=None):
        """Récupère une valeur de configuration en tant qu'entier"""
        try:
            return self.config.getint(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if fallback is not None:
                return fallback
            raise ConfigError(f"Option de configuration manquante: {section}.{option}")
            
    def get_float(self, section, option, fallback=None):
        """Récupère une valeur de configuration en tant que float"""
        try:
            return self.config.getfloat(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if fallback is not None:
                return fallback
            raise ConfigError(f"Option de configuration manquante: {section}.{option}")
            
    def get_boolean(self, section, option, fallback=None):
        """Récupère une valeur de configuration en tant que booléen"""
        try:
            return self.config.getboolean(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if fallback is not None:
                return fallback
            raise ConfigError(f"Option de configuration manquante: {section}.{option}")
            
    def set(self, section, option, value):
        """Définit une valeur de configuration"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, str(value))
        
    def save(self):
        """Sauvegarde la configuration dans le fichier"""
        try:
            with open(self.config_file, 'w') as f:
                self.config.write(f)
            logging.info(f"Configuration sauvegardée dans {self.config_file}")
        except Exception as e:
            raise ConfigError(f"Erreur lors de la sauvegarde de la configuration: {str(e)}")

class LoggingManager:
    """Gestionnaire de journalisation pour le script"""
    
    def __init__(self, log_dir=DEFAULT_LOG_DIR, log_level="INFO"):
        self.log_dir = Path(log_dir)
        self.log_level = self._parse_level(log_level)
        self.log_file = self._generate_log_filename()
        self._setup_logging()
        
    def _parse_level(self, level_str):
        """Convertit une chaîne de niveau de log en niveau logging"""
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        return levels.get(level_str.upper(), logging.INFO)
        
    def _generate_log_filename(self):
        """Génère un nom de fichier de log basé sur la date"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.log_dir / f"f1_data_{timestamp}.log"
        
    def _setup_logging(self):
        """Configure le système de journalisation"""
        # Création du répertoire de logs si nécessaire
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration du logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Format du message
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Handler pour la console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # Handler pour le fichier
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # Log d'initialisation
        logging.info(f"Journalisation initialisée, fichier: {self.log_file}")
        logging.info(f"Version du script: {__version__}")
        logging.info(f"Système: {platform.system()} {platform.release()}")
        logging.info(f"Python: {sys.version}")
        
    def rotate_logs(self, max_logs=10):
        """Supprime les anciens fichiers de log si leur nombre dépasse max_logs"""
        try:
            log_files = sorted(list(self.log_dir.glob("f1_data_*.log")))
            if len(log_files) > max_logs:
                for old_log in log_files[:-max_logs]:
                    old_log.unlink()
                logging.info(f"Anciens fichiers de log supprimés, conservés: {max_logs}")
        except Exception as e:
            logging.warning(f"Erreur lors de la rotation des logs: {str(e)}")

class SystemInfo:
    """Classe pour collecter et fournir des informations système"""
    
    @staticmethod
    def get_system_info():
        """Collecte les informations système importantes pour le débogage"""
        info = {
            "os": platform.system(),
            "os_version": platform.release(),
            "python_version": platform.python_version(),
            "hostname": socket.gethostname(),
            "cpu_count": os.cpu_count(),
            "machine": platform.machine(),
            "platform": platform.platform(),
            "timestamp": datetime.now().isoformat()
        }
        
        # Vérification des modules importants
        dependencies = {
            "requests": "Unknown",
            "pandas": "Unknown",
            "numpy": "Unknown",
            "bs4": "Unknown",
            "tenacity": "Unknown",
            "playwright": "Not installed" if not PLAYWRIGHT_AVAILABLE else "Installed",
            "sqlalchemy": "Not installed" if not SQLALCHEMY_AVAILABLE else "Installed",
            "fake_useragent": "Not installed" if not FAKE_USERAGENT_AVAILABLE else "Installed"
        }
        
        # Récupération des versions
        try:
            import requests
            dependencies["requests"] = requests.__version__
        except (ImportError, AttributeError):
            pass
            
        try:
            import pandas
            dependencies["pandas"] = pandas.__version__
        except (ImportError, AttributeError):
            pass
            
        try:
            import numpy
            dependencies["numpy"] = numpy.__version__
        except (ImportError, AttributeError):
            pass
            
        try:
            import bs4
            dependencies["bs4"] = bs4.__version__
        except (ImportError, AttributeError):
            pass
            
        try:
            import tenacity
            dependencies["tenacity"] = tenacity.__version__
        except (ImportError, AttributeError):
            pass
            
        info["dependencies"] = dependencies
        return info
        
    @staticmethod
    def log_system_info():
        """Journalise les informations système"""
        info = SystemInfo.get_system_info()
        logging.info("Informations système:")
        for key, value in info.items():
            if key != "dependencies":
                logging.info(f"  {key}: {value}")
                
        logging.info("Dépendances:")
        for dep, ver in info["dependencies"].items():
            logging.info(f"  {dep}: {ver}")
            
    @staticmethod
    def check_dependencies():
        """Vérifie si toutes les dépendances requises sont disponibles"""
        required = {
            "requests": True,
            "pandas": True,
            "numpy": True,
            "bs4": True,
            "tenacity": True
        }
        
        missing = []
        for dep, required in required.items():
            if required:
                try:
                    __import__(dep)
                except ImportError:
                    missing.append(dep)
                    
        if missing:
            logging.error(f"Dépendances manquantes: {', '.join(missing)}")
            logging.error("Installez-les avec: pip install " + " ".join(missing))
            return False
        return True

class OpenMeteoAPI:
    """Interface pour l'API Open-Meteo"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.base_url = self.config.get("apis", "openmeteo_base_url")
        self.max_retries = self.config.get_int("apis", "max_retries", 3)
        self.retry_wait_multiplier = self.config.get_float("apis", "retry_wait_multiplier", 2)
        self.retry_wait_min = self.config.get_float("apis", "retry_wait_min", 4)
        self.retry_wait_max = self.config.get_float("apis", "retry_wait_max", 30)
        
        # Journalisation de l'initialisation
        logging.info(f"Initialisation de l'API Open-Meteo: {self.base_url}")
    
    def get_weather_data(self, lat, lon, date):
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
                'hourly': [
                    'temperature_2m',
                    'relative_humidity_2m',
                    'precipitation',
                    'wind_speed_10m',
                    'wind_direction_10m',
                    'surface_pressure'
                ]
            }
            
            # Appel à l'API avec retry
            result = self._api_call_with_retry(params)
            
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
            
            logging.debug(f"Données météo récupérées pour {start_date}, coordonnées: {lat},{lon}")
            return weather_data
            
        except Exception as e:
            error_msg = f"Erreur lors de la récupération des données météo: {str(e)}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            raise APIError(error_msg)
            
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _api_call_with_retry(self, params):
        """Effectue un appel API avec retry en cas d'échec"""
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.warning(f"Tentative échouée pour Open-Meteo API: {str(e)}")
            raise

class F1Scraper:
    """Classe pour le web scraping F1"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.use_playwright = self.config.get_boolean("web_scraping", "use_playwright", True)
        self.headless = self.config.get_boolean("web_scraping", "headless", True)
        self.user_agent_rotation = self.config.get_boolean("web_scraping", "user_agent_rotation", True)
        self.min_delay = self.config.get_float("web_scraping", "min_delay", 3.0)
        self.max_delay = self.config.get_float("web_scraping", "max_delay", 7.0)
        
        # Initialisation du user agent
        if self.user_agent_rotation and FAKE_USERAGENT_AVAILABLE:
            try:
                self.user_agent = UserAgent()
                logging.info("UserAgent initialisé pour la rotation des user agents")
            except Exception as e:
                logging.warning(f"Échec de l'initialisation de UserAgent: {str(e)}")
                self.user_agent_rotation = False
        else:
            self.user_agent_rotation = False
            
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.8,en-US;q=0.5,en;q=0.3',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.67 Safari/537.36'
        }
        
        # Vérification de la disponibilité de Playwright
        if self.use_playwright and not PLAYWRIGHT_AVAILABLE:
            logging.warning("Playwright n'est pas installé, utilisation de requests à la place")
            self.use_playwright = False
            
        # Journalisation de l'initialisation
        logging.info(f"Initialisation du scraper F1 (Playwright: {self.use_playwright}, rotation UA: {self.user_agent_rotation})")
    
    def _get_random_delay(self):
        """Génère un délai aléatoire"""
        return random.uniform(self.min_delay, self.max_delay)
    
    def _get_user_agent(self):
        """Récupère un user agent aléatoire ou par défaut"""
        if self.user_agent_rotation and hasattr(self, 'user_agent'):
            return self.user_agent.random
        return self.headers['User-Agent']
    
    def fetch_page(self, url):
        """Récupère une page avec gestion des erreurs et méthode adaptée"""
        if self.use_playwright:
            return self._fetch_with_playwright(url)
        else:
            return self._fetch_with_requests(url)
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _fetch_with_playwright(self, url):
        """Récupère une page avec Playwright"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    user_agent=self._get_user_agent(),
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = context.new_page()
                page.set_extra_http_headers(self.headers)
                
                logging.debug(f"Récupération de la page avec Playwright: {url}")
                page.goto(url, wait_until='networkidle')
                
                # Comportement "humain"
                page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                delay_ms = int(self._get_random_delay() * 1000)
                page.wait_for_timeout(delay_ms)
                
                content = page.content()
                browser.close()
                
                logging.debug(f"Page récupérée avec succès: {url} ({len(content)} caractères)")
                return content
                
        except Exception as e:
            error_msg = f"Erreur lors de la récupération de la page avec Playwright: {url}, {str(e)}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            raise DataExtractionError(error_msg)
            
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_with_requests(self, url):
        """Récupère une page avec Requests"""
        try:
            headers = self.headers.copy()
            if self.user_agent_rotation:
                headers['User-Agent'] = self._get_user_agent()
                
            logging.debug(f"Récupération de la page avec Requests: {url}")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Délai pour éviter de surcharger le serveur
            time.sleep(self._get_random_delay())
            
            logging.debug(f"Page récupérée avec succès: {url} ({len(response.text)} caractères)")
            return response.text
            
        except Exception as e:
            error_msg = f"Erreur lors de la récupération de la page avec Requests: {url}, {str(e)}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            raise DataExtractionError(error_msg)

class ErgastAPI:
    """Interface pour l'API Ergast F1"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.base_url = self.config.get("apis", "ergast_base_url")
        self.max_retries = self.config.get_int("apis", "max_retries", 3)
        self.retry_wait_multiplier = self.config.get_float("apis", "retry_wait_multiplier", 2)
        self.retry_wait_min = self.config.get_float("apis", "retry_wait_min", 4)
        self.retry_wait_max = self.config.get_float("apis", "retry_wait_max", 30)
        self.session = requests.Session()
        
        # Journalisation de l'initialisation
        logging.info(f"Initialisation de l'API Ergast F1: {self.base_url}")
    
    def get_season_data(self, year):
        """Récupère les données d'une saison"""
        try:
            url = f"{self.base_url}/{year}.json"
            logging.info(f"Récupération des données de saison pour {year}")
            
            result = self._api_call_with_retry(url)
            
            # Validation des données
            if 'MRData' not in result or 'RaceTable' not in result['MRData']:
                raise APIError(f"Format de données invalide pour la saison {year}")
                
            return result
            
        except Exception as e:
            error_msg = f"Erreur lors de la récupération des données de saison pour {year}: {str(e)}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            raise APIError(error_msg)
    
    def get_race_results(self, year, round_number):
        """Récupère les résultats d'une course"""
        try:
            url = f"{self.base_url}/{year}/{round_number}/results.json"
            logging.debug(f"Récupération des résultats de course pour {year} round {round_number}")
            
            result = self._api_call_with_retry(url)
            
            # Validation des données
            if ('MRData' not in result or 'RaceTable' not in result['MRData'] or 
                'Races' not in result['MRData']['RaceTable'] or 
                len(result['MRData']['RaceTable']['Races']) == 0):
                raise APIError(f"Format de données invalide pour {year} round {round_number}")
                
            return result
            
        except Exception as e:
            error_msg = f"Erreur lors de la récupération des résultats de course: {str(e)}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            raise APIError(error_msg)
            
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _api_call_with_retry(self, url):
        """Effectue un appel API avec retry en cas d'échec"""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.warning(f"Tentative échouée pour Ergast API: {str(e)}")
            raise

class DataCache:
    """Système de cache pour les données"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.cache_dir = Path(self.config.get("general", "cache_dir"))
        
        # Création du répertoire de cache si nécessaire
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Journalisation de l'initialisation
        logging.info(f"Initialisation du système de cache: {self.cache_dir}")
    
    def get(self, key):
        """Récupère des données du cache"""
        filepath = self.cache_dir / f"{key}.json"
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
    
    def set(self, key, data):
        """Enregistre des données dans le cache"""
        filepath = self.cache_dir / f"{key}.json"
        try:
            # Sécurisation de l'écriture avec un fichier temporaire
            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as tf:
                json.dump(data, tf, indent=2, ensure_ascii=False)
                temp_name = tf.name
                
            # Renommage atomique
            shutil.move(temp_name, filepath)
            logging.debug(f"Données enregistrées dans le cache: {key}")
        except Exception as e:
            logging.error(f"Erreur lors de l'écriture dans le cache pour {key}: {str(e)}")
            # Nettoyage en cas d'erreur
            if 'temp_name' in locals() and os.path.exists(temp_name):
                try:
                    os.unlink(temp_name)
                except:
                    pass
                    
    def invalidate(self, key):
        """Invalide une entrée du cache"""
        filepath = self.cache_dir / f"{key}.json"
        if filepath.exists():
            try:
                filepath.unlink()
                logging.debug(f"Cache invalidé pour: {key}")
                return True
            except Exception as e:
                logging.warning(f"Erreur lors de l'invalidation du cache pour {key}: {str(e)}")
                return False
        return False
        
    def clear(self, pattern=None):
        """Vide le cache, avec filtrage optionnel par pattern"""
        try:
            count = 0
            if pattern:
                files = list(self.cache_dir.glob(f"{pattern}.json"))
            else:
                files = list(self.cache_dir.glob("*.json"))
                
            for f in files:
                f.unlink()
                count += 1
                
            logging.info(f"{count} fichiers supprimés du cache")
                
        except Exception as e:
            logging.error(f"Erreur lors du nettoyage du cache: {str(e)}")
            
    def get_stats(self):
        """Renvoie des statistiques sur le cache"""
        try:
            files = list(self.cache_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in files)
            return {
                "count": len(files),
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "oldest": min([f.stat().st_mtime for f in files]) if files else None,
                "newest": max([f.stat().st_mtime for f in files]) if files else None
            }
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des statistiques du cache: {str(e)}")
            return {}