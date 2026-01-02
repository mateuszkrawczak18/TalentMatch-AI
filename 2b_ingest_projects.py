import os
import random
from dotenv import load_dotenv
from langchain_community.graphs import Neo4jGraph

load_dotenv()

# Używamy langchain_community, żeby było spójnie z Agentem
graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    username=os.getenv("NEO4J_USERNAME", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "password123")
)

def ingest_dynamic_projects():
    print("🏗️  Simulating 'Current State' (Limited to 10 busy people)...")
    
    # 1. Pobierz wszystkich pracowników z bazy
    try:
        people_result = graph.query("MATCH (p:Person) RETURN p.name as name")
        all_people = [r['name'] for r in people_result]
    except Exception as e:
        print(f"❌ Error fetching people: {e}")
        return

    if not all_people:
        print("❌ No people found in DB! Run '2_data_to_knowledge_graph.py' first.")
        return

    # 2. Zdefiniuj projekty "Legacy" (Trwające w tle)
    ongoing_projects = [
        "Legacy Banking System",
        "Internal HR Portal",
        "Data Warehouse Migration",
        "Cybersecurity Audit 2024",
        "Mobile App Maintenance"
    ]

    # Stwórz węzły projektów i oznacz jako 'Ongoing'
    for proj in ongoing_projects:
        graph.query("""
            MERGE (p:Project {name: $name})
            SET p.status = 'Ongoing', p.budget = 'Active'
        """, {"name": proj})

    # 3. Przypisywanie (Symulacja życia)
    # ZMIANA: Sztywno 10 osób, żeby kontrolować matematykę (30 total - 10 busy = 20 available for RFPs)
    num_busy = 10
    
    # Zabezpieczenie, gdyby w bazie było mniej niż 10 osób
    if num_busy > len(all_people):
        num_busy = len(all_people)
    
    # Mieszamy listę pracowników
    random.shuffle(all_people)
    busy_people = all_people[:num_busy]

    print(f"🎲 Selecting exactly {num_busy} people to be BUSY (Legacy Projects)...")

    for person in busy_people:
        project = random.choice(ongoing_projects)
        # ZMIANA: Dajemy 1.0 (100%), żeby na pewno byli niedostępni dla nowych projektów
        allocation = 1.0 
        role = random.choice(["Developer", "Lead", "Tester", "Architect"])
        
        try:
            query = """
            MATCH (p:Person {name: $person}), (proj:Project {name: $proj})
            MERGE (p)-[r:ASSIGNED_TO]->(proj)
            SET r.allocation = $alloc, 
                r.role = $role, 
                r.start_date = '2023-01-01'
            """
            graph.query(query, {
                "person": person,
                "proj": project,
                "alloc": allocation,
                "role": role
            })
            print(f"   🔒 Assigned: {person} -> {project} ({allocation*100}%)")
        except Exception as e:
            print(f"⚠️ Error assigning {person}: {e}")

    # Podsumowanie matematyczne dla Ciebie
    print(f"\n✅ Simulation Complete.")
    print(f"   📊 Statistics:")
    print(f"      - Total Employees: {len(all_people)}")
    print(f"      - Busy (Legacy):   {num_busy}")
    print(f"      - Available:       {len(all_people) - num_busy}")

if __name__ == "__main__":
    ingest_dynamic_projects()