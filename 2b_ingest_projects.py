import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph

load_dotenv()

# Konfiguracja
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

def ingest_projects():
    print("🚀 Starting Project Simulation (Scenario: 10 Busy, Rest Available)...")
    
    try:
        graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return

    # ==========================================
    # 1. CZYSZCZENIE (Totalny reset projektów)
    # ==========================================
    print("🧹 [1/4] Cleaning ALL old assignments and projects...")
    graph.query("MATCH (:Person)-[r:ASSIGNED_TO]->() DELETE r")
    graph.query("MATCH (p:Project) DETACH DELETE p")

    # ==========================================
    # 2. TWORZENIE PROJEKTÓW
    # ==========================================
    print("🏗️  [2/4] Creating active projects...")
    
    projects_data = [
        {"name": "Legacy System Migration", "end_days": 120},
        {"name": "Cybersecurity Audit", "end_days": 30},
        {"name": "Mobile App Refresh", "end_days": 180},
        {"name": "HR Portal Update", "end_days": 60},
        {"name": "Cloud Infrastructure Setup", "end_days": 90}
    ]

    for p in projects_data:
        end_date = (datetime.now() + timedelta(days=p['end_days'])).strftime("%Y-%m-%d")
        graph.query(
            """
            MERGE (p:Project {name: $name})
            SET p.status = 'Active', 
                p.end_date = date($end_date)
            """,
            params={"name": p['name'], "end_date": end_date}
        )

    # ==========================================
    # 3. POBRANIE LUDZI
    # ==========================================
    people_result = graph.query("MATCH (p:Person) RETURN p.name as name")
    all_people = [r['name'] for r in people_result]
    
    if not all_people:
        print("❌ No people found! Run script '2_data_to_knowledge_graph.py' first.")
        return

    total_people = len(all_people)
    
    # ==========================================
    # 4. PRZYPISYWANIE (Sztywno 10 osób)
    # ==========================================
    # Ustawiamy limit zajętych na 10
    target_busy_count = 10
    
    # Zabezpieczenie, gdyby w bazie było mniej niż 10 osób
    if total_people < target_busy_count:
        target_busy_count = total_people

    print(f"🎲 [3/4] Selecting exactly {target_busy_count} people to be BUSY...")
    
    # Mieszamy listę, żeby było losowo
    random.shuffle(all_people)
    
    busy_people = all_people[:target_busy_count]      # Te 10 osób dostanie projekt (100% obłożenia)
    available_people = all_people[target_busy_count:] # Reszta zostaje bez projektu (0% obłożenia)

    for person in busy_people:
        project_def = random.choice(projects_data)
        
        # Nadajemy relację ASSIGNED_TO z allocation 1.0 (pełny etat)
        graph.query(
            """
            MATCH (p:Person {name: $person})
            MATCH (proj:Project {name: $project_name})
            MERGE (p)-[r:ASSIGNED_TO]->(proj)
            SET r.allocation = 1.0,
                r.role = 'Developer',
                r.assigned_at = date()
            """,
            params={
                "person": person,
                "project_name": project_def['name']
            }
        )

    # ==========================================
    # 5. PODSUMOWANIE
    # ==========================================
    print("\n✅ Simulation Complete.")
    print(f"📊 Final Stats:")
    print(f"   - Total Staff: {total_people}")
    print(f"   - Busy (Load 1.0): {len(busy_people)}  <-- Te osoby są niedostępne")
    print(f"   - Bench (Load 0.0): {len(available_people)} <-- Te osoby są dostępne do nowych projektów")

if __name__ == "__main__":
    ingest_projects()