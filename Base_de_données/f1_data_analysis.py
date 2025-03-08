import mysql.connector
from mysql.connector import Error
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import warnings
import os
import argparse
from pymongo import MongoClient

# Ignorer les avertissements
warnings.filterwarnings('ignore')

# Configuration des bases de données
MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Compound3522?',
    'database': 'f1_database'
}

MONGODB_URI = 'mongodb+srv://etiennemahe3:suS8anlC8zl4yLlP@cluster0.wiirj.mongodb.net/'
MONGODB_DB = 'F1'
MONGODB_COLLECTION = 'f1_performance_data'

# Fonctions utilitaires
def safe_value(value):
    """Gère les valeurs NaN pour l'insertion dans la base de données."""
    if pd.isna(value) or value == 'nan':
        return None
    return value

# ===== PARTIE MYSQL =====
def create_mysql_connection():
    """Établit la connexion à MySQL."""
    try:
        connection = mysql.connector.connect(**MYSQL_CONFIG)
        if connection.is_connected():
            print(f"✓ Connecté à MySQL version {connection.get_server_info()}")
            return connection
    except Error as e:
        print(f"✗ Erreur de connexion MySQL: {e}")
        return None

def create_database_structure(connection):
    """Crée la structure de la base de données MySQL."""
    cursor = connection.cursor()
    
    # Suppression des tables dans l'ordre correct
    drop_tables_sql = """
    DROP TABLE IF EXISTS weather_conditions;
    DROP TABLE IF EXISTS race_results;
    DROP TABLE IF EXISTS rankings;
    DROP TABLE IF EXISTS races;
    DROP TABLE IF EXISTS drivers;
    DROP TABLE IF EXISTS constructors;
    """
    
    print("Nettoyage de la base de données MySQL...")
    for statement in drop_tables_sql.split(';'):
        if statement.strip():
            try:
                cursor.execute(statement)
                print(f"✓ Table supprimée")
            except Error as e:
                print(f"✗ Erreur de suppression: {e}")
    
    # Création des tables
    create_tables_sql = """
    CREATE TABLE constructors (
        constructor_id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        nationality VARCHAR(100),
        UNIQUE(name)
    );

    CREATE TABLE drivers (
        driver_id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        nationality VARCHAR(100),
        UNIQUE(name)
    );

    CREATE TABLE races (
        race_id INT AUTO_INCREMENT PRIMARY KEY,
        year INT NOT NULL,
        round INT NOT NULL,
        race_name VARCHAR(255) NOT NULL,
        circuit VARCHAR(255),
        date DATE,
        UNIQUE(year, round)
    );

    CREATE TABLE weather_conditions (
        weather_id INT AUTO_INCREMENT PRIMARY KEY,
        race_id INT,
        temperature FLOAT,
        humidity INT,
        wind_speed FLOAT,
        wind_direction INT,
        precipitation FLOAT,
        pressure FLOAT,
        FOREIGN KEY (race_id) REFERENCES races(race_id)
        ON DELETE CASCADE
    );

    CREATE TABLE race_results (
        result_id INT AUTO_INCREMENT PRIMARY KEY,
        race_id INT,
        driver_id INT,
        constructor_id INT,
        grid INT,
        position INT,
        points FLOAT,
        race_time VARCHAR(20),
        fastest_lap_rank INT,
        fastest_lap_time VARCHAR(20),
        fastest_lap_speed FLOAT,
        FOREIGN KEY (race_id) REFERENCES races(race_id) ON DELETE CASCADE,
        FOREIGN KEY (driver_id) REFERENCES drivers(driver_id) ON DELETE CASCADE,
        FOREIGN KEY (constructor_id) REFERENCES constructors(constructor_id) ON DELETE CASCADE
    );

    CREATE TABLE rankings (
        ranking_id INT AUTO_INCREMENT PRIMARY KEY,
        race_id INT,
        driver_id INT,
        constructor_id INT,
        points FLOAT,
        position INT,
        FOREIGN KEY (race_id) REFERENCES races(race_id) ON DELETE CASCADE,
        FOREIGN KEY (driver_id) REFERENCES drivers(driver_id) ON DELETE CASCADE,
        FOREIGN KEY (constructor_id) REFERENCES constructors(constructor_id) ON DELETE CASCADE
    );
    """
    
    print("\nCréation des tables MySQL...")
    for statement in create_tables_sql.split(';'):
        if statement.strip():
            try:
                cursor.execute(statement)
                print(f"✓ Table créée avec succès")
            except Error as e:
                print(f"✗ Erreur de création: {e}")
                return False
    
    connection.commit()
    return True

def import_f1_data(connection, df):
    """Importe les données F1 depuis un DataFrame vers MySQL."""
    cursor = connection.cursor()
    
    try:
        total_rows = len(df)
        
        # Import des pilotes
        for driver in df['driver'].unique():
            if pd.notna(driver):
                cursor.execute(
                    "INSERT IGNORE INTO drivers (name) VALUES (%s)", 
                    (driver,)
                )
        
        # Import des constructeurs
        for constructor in df['constructor'].unique():
            if pd.notna(constructor):
                cursor.execute(
                    "INSERT IGNORE INTO constructors (name) VALUES (%s)", 
                    (constructor,)
                )
        
        # Import des courses et résultats
        print(f"\nImport des {total_rows} courses...")
        for idx, row in df.iterrows():
            if idx % 100 == 0:
                print(f"Progression: {idx}/{total_rows} ({(idx/total_rows*100):.1f}%)")
            
            if pd.isna(row['year']) or pd.isna(row['round']):
                continue
                
            cursor.execute("""
                INSERT IGNORE INTO races (year, round, race_name, circuit, date)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                int(row['year']), 
                int(row['round']), 
                row['race_name'],
                safe_value(row['circuit']),
                pd.to_datetime(row['date']) if pd.notna(row['date']) else None
            ))
            
            # Récupération des IDs
            cursor.execute(
                "SELECT race_id FROM races WHERE year=%s AND round=%s", 
                (int(row['year']), int(row['round']))
            )
            race_id = cursor.fetchone()[0]
            
            cursor.execute(
                "SELECT driver_id FROM drivers WHERE name=%s", 
                (row['driver'],)
            )
            driver_result = cursor.fetchone()
            if not driver_result:
                continue
            driver_id = driver_result[0]
            
            cursor.execute(
                "SELECT constructor_id FROM constructors WHERE name=%s", 
                (row['constructor'],)
            )
            constructor_result = cursor.fetchone()
            if not constructor_result:
                continue
            constructor_id = constructor_result[0]
            
            # Insertion résultat
            cursor.execute("""
                INSERT INTO race_results (
                    race_id, driver_id, constructor_id, position, 
                    grid, points, race_time, fastest_lap_rank, 
                    fastest_lap_time, fastest_lap_speed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                race_id,
                driver_id,
                constructor_id,
                safe_value(row['position']),
                safe_value(row['grid']),
                safe_value(row['points']),
                safe_value(row['race_time']),
                safe_value(row['fastest_lap_rank']),
                safe_value(row['fastest_lap_time']),
                safe_value(row['fastest_lap_speed'])
            ))
            
            # Insertion météo
            cursor.execute("""
                INSERT INTO weather_conditions (
                    race_id, temperature, humidity, wind_speed,
                    wind_direction, precipitation, pressure
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                race_id,
                safe_value(row['temperature']),
                safe_value(row['humidity']),
                safe_value(row['wind_speed']),
                safe_value(row['wind_direction']),
                safe_value(row['precipitation']),
                safe_value(row['pressure'])
            ))
        
        connection.commit()
        print("✓ Import MySQL terminé avec succès")
        
    except Error as e:
        print(f"\n✗ Erreur MySQL: {e}")
        connection.rollback()
    except Exception as e:
        print(f"\n✗ Erreur: {e}")
        connection.rollback()
    finally:
        cursor.close()

def create_mysql_visualizations(connection):
    """Crée des visualisations à partir des données MySQL."""
    print("\nCréation des visualisations MySQL...")
    
    # 1. Top constructeurs
    query_constructors = """
    SELECT c.name as constructor, 
           SUM(r.points) as total_points,
           COUNT(DISTINCT ra.year) as seasons
    FROM race_results r
    JOIN constructors c ON r.constructor_id = c.constructor_id
    JOIN races ra ON r.race_id = ra.race_id
    GROUP BY c.name
    HAVING seasons >= 3
    ORDER BY total_points DESC
    LIMIT 10
    """
    df_constructors = pd.read_sql(query_constructors, connection)
    
    fig1 = px.bar(df_constructors,
                 x='constructor',
                 y='total_points',
                 title='Top 10 Constructeurs en F1',
                 labels={'constructor': 'Constructeur',
                        'total_points': 'Points totaux'})
    fig1.update_layout(
        xaxis_tickangle=-45,
        margin=dict(t=50, b=100),
        height=600
    )
    fig1.write_html("top_constructors.html")
    print("✓ Visualisation 'Top 10 Constructeurs' créée")
    
    # 2. Performance par circuit
    query_circuits = """
    SELECT r.circuit,
           AVG(rr.fastest_lap_speed) as avg_speed,
           COUNT(*) as races
    FROM races r
    JOIN race_results rr ON r.race_id = rr.race_id
    WHERE rr.fastest_lap_speed IS NOT NULL
    GROUP BY r.circuit
    HAVING races >= 10
    ORDER BY avg_speed DESC
    LIMIT 15
    """
    df_circuits = pd.read_sql(query_circuits, connection)
    
    fig2 = px.bar(df_circuits,
                 x='circuit',
                 y='avg_speed',
                 title='Vitesse moyenne par circuit (km/h)',
                 labels={'circuit': 'Circuit',
                        'avg_speed': 'Vitesse moyenne'})
    fig2.update_layout(
        xaxis_tickangle=-45,
        margin=dict(t=50, b=100),
        height=600
    )
    fig2.write_html("circuit_performance.html")
    print("✓ Visualisation 'Performance par circuit' créée")
    
    # 3. Évolution des performances par année
    query_evolution = """
    SELECT 
        ra.year,
        c.name as constructor,
        SUM(r.points) as year_points
    FROM race_results r
    JOIN races ra ON r.race_id = ra.race_id
    JOIN constructors c ON r.constructor_id = c.constructor_id
    GROUP BY ra.year, c.name
    ORDER BY ra.year, year_points DESC
    """
    df_evolution = pd.read_sql(query_evolution, connection)
    
    fig3 = px.line(df_evolution,
                   x='year',
                   y='year_points',
                   color='constructor',
                   title='Évolution des points par constructeur',
                   labels={'year': 'Année',
                          'year_points': 'Points',
                          'constructor': 'Constructeur'})
    fig3.update_layout(
        showlegend=True,
        height=600,
        margin=dict(t=50, b=50)
    )
    fig3.write_html("constructor_evolution.html")
    print("✓ Visualisation 'Évolution des performances' créée")
    
    # 4. Conditions météo et performances
    query_weather = """
    SELECT 
        wc.temperature,
        wc.humidity,
        rr.fastest_lap_speed,
        r.circuit
    FROM weather_conditions wc
    JOIN races r ON wc.race_id = r.race_id
    JOIN race_results rr ON r.race_id = rr.race_id
    WHERE wc.temperature IS NOT NULL 
    AND wc.humidity IS NOT NULL 
    AND rr.fastest_lap_speed IS NOT NULL
    """
    df_weather = pd.read_sql(query_weather, connection)
    
    fig4 = px.scatter(df_weather,
                     x='temperature',
                     y='fastest_lap_speed',
                     color='humidity',
                     title='Impact de la météo sur les performances',
                     labels={'temperature': 'Température (°C)',
                            'fastest_lap_speed': 'Vitesse max (km/h)',
                            'humidity': 'Humidité (%)'})
    fig4.update_layout(height=600)
    fig4.write_html("weather_impact.html")
    print("✓ Visualisation 'Impact de la météo' créée")

# ===== PARTIE MONGODB =====
def create_mongodb_connection():
    """Établit la connexion à MongoDB."""
    try:
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DB]
        collection = db[MONGODB_COLLECTION]
        print("✓ Connecté à MongoDB")
        return client, collection
    except Exception as e:
        print(f"✗ Erreur de connexion MongoDB: {e}")
        return None, None

def print_collection_stats(collection):
    """Analyse une collection MongoDB de données F1 et génère des statistiques détaillées"""
    print("\nStatistiques de la base de données:")
    
    # Nombre de courses par année
    print("\nNombre de courses par année:")
    # Récupération des documents groupés par année
    courses_par_annee = {}
    for document in collection.find():
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
    for document in collection.find():
        circuit = document.get('circuit')
        if circuit:
            circuits_uniques.add(circuit)
    
    n_circuits = len(circuits_uniques)
    print(f"\nNombre de circuits uniques: {n_circuits}")
    
    # Pilotes uniques
    print("\nPilotes uniques:")
    pilotes_uniques = set()
    
    # Récupération de tous les pilotes
    for document in collection.find():
        pilote = document.get('driver')
        if pilote:
            pilotes_uniques.add(pilote)
    
    n_drivers = len(pilotes_uniques)
    print(f"Nombre de pilotes uniques: {n_drivers}")

def get_performance_by_circuit_simple(collection, circuit_name):
    """Analyse des performances sur un circuit spécifique sans pipeline."""
    print(f"\nAnalyse des performances sur le circuit: {circuit_name}")
    
    # Filtrer les documents pour le circuit spécifique et les années >= 2021
    filtered_docs = []
    for doc in collection.find({"circuit": circuit_name}):
        if doc.get("year") and doc.get("year") >= 2021:
            filtered_docs.append(doc)
    
    if not filtered_docs:
        print(f"Aucune donnée disponible pour {circuit_name}")
        return
    
    # Regrouper par année et race_name
    grouped_data = {}
    for doc in filtered_docs:
        year = doc.get("year")
        race_name = doc.get("race_name")
        key = f"{year}_{race_name}"
        
        if key not in grouped_data:
            grouped_data[key] = {
                "year": year,
                "race_name": race_name,
                "speeds": [],
                "max_speeds": [],
                "rpm_values": [],
                "lap_times": []
            }
        
        # Extraire les données de performance
        if "performance" in doc:
            perf = doc["performance"]
            if "speeds" in perf and "avg" in perf["speeds"]:
                grouped_data[key]["speeds"].append(perf["speeds"]["avg"])
            if "speeds" in perf and "max" in perf["speeds"]:
                grouped_data[key]["max_speeds"].append(perf["speeds"]["max"])
            if "engine" in perf and "avg_rpm" in perf["engine"]:
                grouped_data[key]["rpm_values"].append(perf["engine"]["avg_rpm"])
            if "best_lap_time" in perf:
                grouped_data[key]["lap_times"].append(perf["best_lap_time"])
    
    # Calculer les moyennes et minimums pour chaque groupe
    results = []
    for key, data in grouped_data.items():
        avg_speed = sum(data["speeds"]) / len(data["speeds"]) if data["speeds"] else None
        max_speed = max(data["max_speeds"]) if data["max_speeds"] else None
        avg_rpm = sum(data["rpm_values"]) / len(data["rpm_values"]) if data["rpm_values"] else None
        best_lap = min(data["lap_times"]) if data["lap_times"] else None
        
        results.append({
            "year": data["year"],
            "avg_speed": avg_speed,
            "max_speed": max_speed,
            "avg_rpm": avg_rpm,
            "best_lap_time": best_lap
        })
    
    # Trier par année
    results.sort(key=lambda x: x["year"])
    
    # Conversion en dataframe et affichage
    df = pd.DataFrame(results)
    print(df)
    
    # Visualisation
    fig = px.line(df, 
                  x="year", 
                  y=["avg_speed", "max_speed"], 
                  title=f"Évolution des performances sur {circuit_name}")
    fig.update_layout(yaxis_title="Vitesse (km/h)")
    fig.write_html(f"circuit_{circuit_name.replace(' ', '_')}.html")
    print(f"✓ Visualisation pour le circuit '{circuit_name}' créée")

def analyze_weather_impact_simple(collection):
    """Analyse de l'impact des conditions météo sur les performances sans pipeline."""
    print("\nAnalyse de l'impact des conditions météorologiques:")
    
    # Récupérer et filtrer tous les documents avec données météo et performance
    weather_data = {
        "Pluie": {"speeds": [], "count": 0},
        "Sec": {"speeds": [], "count": 0}
    }
    
    for doc in collection.find():
        # Vérifier si le document a les informations nécessaires
        if not (doc.get("weather") and doc.get("performance") and 
                "speeds" in doc["performance"] and "avg" in doc["performance"]["speeds"]):
            continue
        
        # Déterminer la condition météo
        precipitation = doc["weather"].get("precipitation", 0)
        condition = "Pluie" if precipitation and precipitation > 0 else "Sec"
        
        # Ajouter la vitesse moyenne
        avg_speed = doc["performance"]["speeds"]["avg"]
        if avg_speed:
            weather_data[condition]["speeds"].append(avg_speed)
            weather_data[condition]["count"] += 1
    
    # Calculer les moyennes
    results = []
    for condition, data in weather_data.items():
        if data["speeds"]:
            avg_speed = sum(data["speeds"]) / len(data["speeds"])
            results.append({
                "weather_condition": condition,
                "avg_speed": avg_speed,
                "races_count": data["count"]
            })
    
    if not results:
        print("Aucune donnée disponible pour l'analyse météo")
        return
    
    # Conversion en dataframe
    df = pd.DataFrame(results)
    print(df)
    
    # Visualisation
    fig = px.bar(df, 
                 x="weather_condition", 
                 y="avg_speed",
                 text="races_count",
                 title="Impact des conditions météo sur la vitesse moyenne",
                 labels={"weather_condition": "Conditions", 
                         "avg_speed": "Vitesse moyenne (km/h)",
                         "races_count": "Nombre de courses"})
    fig.update_traces(texttemplate='%{text} courses', textposition='outside')
    fig.write_html("mongodb_weather_impact.html")
    print("✓ Visualisation 'Impact météo (MongoDB)' créée")

def combined_analysis_simple(mysql_conn, mongo_collection):
    """Analyse combinée des données MySQL et MongoDB sans pipeline."""
    print("\nAnalyse combinée MySQL et MongoDB:")
    
    # Récupérer les données de courses récentes de MySQL
    mysql_data = None
    if mysql_conn and mysql_conn.is_connected():
        recent_races_query = """
        SELECT 
            r.year, 
            r.race_name, 
            r.circuit,
            COUNT(DISTINCT rr.driver_id) as drivers_count,
            AVG(rr.fastest_lap_speed) as avg_speed
        FROM races r
        JOIN race_results rr ON r.race_id = rr.race_id
        WHERE r.year >= 2021
        GROUP BY r.year, r.race_name, r.circuit
        ORDER BY r.year DESC, r.race_name
        """
        mysql_data = pd.read_sql(recent_races_query, mysql_conn)
        print(f"Données MySQL récupérées: {len(mysql_data)} courses")
        
        # Enregistrer en CSV
        mysql_data.to_csv("mysql_recent_races.csv", index=False)
        print("✓ Données MySQL exportées vers mysql_recent_races.csv")
    
    # Récupérer des statistiques de performance de MongoDB
    mongo_data = None
    if mongo_collection:
        # Filtrer et traiter manuellement
        circuit_performances = {}
        for doc in mongo_collection.find():
            # Vérifier l'année
            if not doc.get("year") or doc.get("year") < 2021:
                continue
                
            # Extraire le circuit
            circuit = doc.get("circuit")
            if not circuit:
                continue
                
            # Extraire la performance
            performance = 0
            if (doc.get("performance") and 
                doc["performance"].get("speeds") and 
                doc["performance"]["speeds"].get("avg")):
                performance = doc["performance"]["speeds"]["avg"]
            else:
                continue
                
            # Ajouter aux données
            if circuit not in circuit_performances:
                circuit_performances[circuit] = {
                    "performances": [],
                    "count": 0
                }
            
            circuit_performances[circuit]["performances"].append(performance)
            circuit_performances[circuit]["count"] += 1
        
        # Calculer les moyennes
        mongo_results = []
        for circuit, data in circuit_performances.items():
            if data["performances"]:
                avg_performance = sum(data["performances"]) / len(data["performances"])
                mongo_results.append({
                    "circuit": circuit,
                    "avg_performance": avg_performance,
                    "races_count": data["count"]
                })
        
        # Trier par performance moyenne
        mongo_results.sort(key=lambda x: x["avg_performance"], reverse=True)
        
        # Conversion en dataframe
        if mongo_results:
            mongo_data = pd.DataFrame(mongo_results)
            print(f"Données MongoDB récupérées: {len(mongo_data)} circuits")
            mongo_data.to_csv("mongodb_circuit_performance.csv", index=False)
            print("✓ Données MongoDB exportées vers mongodb_circuit_performance.csv")
            
            # Visualisation combinée si les deux sources sont disponibles
            if mysql_data is not None and not mysql_data.empty:
                print("Création d'une visualisation combinée...")
                # Visualisation à titre d'exemple
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=mysql_data['circuit'][:10],
                    y=mysql_data['avg_speed'][:10],
                    name='MySQL - Vitesse moyenne'
                ))
                fig.add_trace(go.Bar(
                    x=mongo_data['circuit'][:10] if 'circuit' in mongo_data.columns else [],
                    y=mongo_data['avg_performance'][:10] if 'avg_performance' in mongo_data.columns else [],
                    name='MongoDB - Performance moyenne'
                ))
                fig.update_layout(
                    title="Comparaison des données MySQL et MongoDB",
                    xaxis_title="Circuit",
                    yaxis_title="Vitesse / Performance",
                    barmode='group'
                )
                fig.write_html("combined_analysis.html")
                print("✓ Visualisation combinée créée")

# ===== FONCTION PRINCIPALE =====
def main():
    parser = argparse.ArgumentParser(description='Analyse de données F1')
    parser.add_argument('--mode', choices=['mysql', 'mongodb', 'all'], default='all',
                        help='Mode d\'analyse: mysql, mongodb ou all (défaut)')
    parser.add_argument('--csv', type=str, default='f1_data_all_years.csv',
                        help='Chemin vers le fichier CSV pour MySQL (défaut: f1_data_all_years.csv)')
    parser.add_argument('--circuit', type=str, default='Circuit de Monaco',
                        help='Circuit à analyser pour MongoDB (défaut: Circuit de Monaco)')
    parser.add_argument('--setup', action='store_true',
                        help='Initialiser/réinitialiser la base de données MySQL')
    
    args = parser.parse_args()
    
    # Variables pour stocker les connexions
    mysql_conn = None
    mongo_client = None
    mongo_collection = None
    
    try:
        # Analyse MySQL
        if args.mode in ['mysql', 'all']:
            mysql_conn = create_mysql_connection()
            if mysql_conn:
                if args.setup:
                    if create_database_structure(mysql_conn):
                        # Import des données
                        try:
                            df = pd.read_csv(args.csv)
                            print(f"✓ {len(df):,} lignes lues du fichier CSV")
                            import_f1_data(mysql_conn, df)
                        except Exception as e:
                            print(f"✗ Erreur lors de la lecture du CSV: {e}")
                
                # Créer des visualisations MySQL
                create_mysql_visualizations(mysql_conn)
        
        # Analyse MongoDB
        if args.mode in ['mongodb', 'all']:
            mongo_client, mongo_collection = create_mongodb_connection()
            if mongo_collection:
                # Utiliser la version simplifiée sans pipeline
                print_collection_stats(mongo_collection)
                get_performance_by_circuit_simple(mongo_collection, args.circuit)
                analyze_weather_impact_simple(mongo_collection)
        
        # Analyse combinée si les deux modes sont actifs
        if args.mode == 'all' and mysql_conn and mongo_collection:
            combined_analysis_simple(mysql_conn, mongo_collection)
            
        print("\n✓ Analyse terminée. Les fichiers de visualisation HTML ont été créés.")
        
    except Exception as e:
        print(f"✗ Erreur générale: {e}")
    finally:
        # Fermeture des connexions
        if mysql_conn and mysql_conn.is_connected():
            mysql_conn.close()
            print("Connexion MySQL fermée")
        
        if mongo_client:
            mongo_client.close()
            print("Connexion MongoDB fermée")

if __name__ == "__main__":
    main()