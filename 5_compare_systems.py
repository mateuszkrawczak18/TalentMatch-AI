import time
import os
import sys
import importlib.util
from dotenv import load_dotenv

# Ładowanie zmiennych środowiskowych
load_dotenv()

def import_module_from_file(module_name, file_path):
    """Pomocnicza funkcja do importowania plików z cyframi w nazwie"""
    if not os.path.exists(file_path):
        print(f"❌ Critical Error: File {file_path} not found!")
        sys.exit(1)
        
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# --- DYNAMICZNY IMPORT MODUŁÓW ---
print("🔄 Loading modules dynamically...")
try:
    # Importujemy 3_match_team.py jako 'match_module'
    match_module = import_module_from_file("match_module", "3_match_team.py")
    TeamMatcher = match_module.TeamMatcher
    
    # Importujemy 4_naive_rag_cv.py jako 'naive_module'
    naive_module = import_module_from_file("naive_module", "4_naive_rag_cv.py")
    NaiveRAGSystem = naive_module.NaiveRAGSystem
    print("✅ Modules loaded successfully.")
except Exception as e:
    print(f"❌ Error loading modules: {e}")
    sys.exit(1)

def run_comparison():
    print("\n" + "="*60)
    print("🥊 STARTING COMPARISON: GraphRAG vs Naive RAG")
    print("="*60)

    # 1. Inicjalizacja GraphRAG (Neo4j)
    print("\n[1/2] Initializing GraphRAG (Neo4j)...")
    try:
        graph_system = TeamMatcher()
        # Resetujemy stan bazy dla czystego porównania
        graph_system.reset_assignments() 
        # Musimy stworzyć przykładowe projekty w bazie, żeby GraphRAG działał
        # (W normalnym trybie robi to analyze_rfp, tu zrobimy mocka)
        mock_reqs = {"project_name": "Test Project", "required_skills": ["Python"], "location": "London"}
        graph_system.create_project_node(mock_reqs)
    except Exception as e:
        print(f"❌ GraphRAG Init Failed: {e}")
        return

    # 2. Inicjalizacja Naive RAG (Chroma)
    print("[2/2] Initializing Naive RAG (Vector)...")
    try:
        naive_system = NaiveRAGSystem()
        success = naive_system.ingest_data()
        if not success:
            print("❌ Naive RAG Ingestion Failed. Stopping.")
            return
    except Exception as e:
        print(f"❌ Naive RAG Init Failed: {e}")
        return

    # --- SCENARIUSZ 1: Wyszukiwanie proste (Simple Retrieval) ---
    question1 = "Find a Python developer."
    print(f"\n\n🔸 SCENARIO 1: Simple Retrieval ('{question1}')")
    print("-" * 60)
    
    print("🔵 GraphRAG Result:")
    # Symulujemy zapytanie o zespół
    reqs = {"required_skills": ["Python"], "team_size": 1, "project_name": "Test Project", "location": None}
    graph_result = graph_system.find_and_assign_team(reqs)
    if graph_result:
        # Bierzemy pierwszego z brzegu
        top_candidate = graph_result[0]
        print(f"Found: {top_candidate['name']} (Score: {top_candidate['final_score']})")
    else:
        print("None found.")

    print("\n🟠 Naive RAG Result:")
    naive_system.query(question1)
    
    print("\n🔎 WNIOSEK 1: Obie metody powinny sobie poradzić. Naive RAG znajdzie słowo 'Python' w CV.")


    # --- SCENARIUSZ 2: Agregacja (Aggregation) ---
    # Pytamy o Londyn, bo wiemy że mamy tam ludzi z generatora
    question2 = "How many developers are located in London?"
    print(f"\n\n🔸 SCENARIO 2: Aggregation ('{question2}')")
    print("-" * 60)
    
    print("🔵 GraphRAG Result:")
    # GraphRAG liczy globalnie w bazie
    count_query = "MATCH (p:Person)-[:LOCATED_IN]->(l:Location) WHERE toLower(l.id) CONTAINS 'london' RETURN count(p) as c"
    try:
        count = graph_system.graph.query(count_query)[0]['c']
        print(f"Graph Count: {count} developers found in Database.")
    except:
        print("Graph Count: Error executing query")

    print("\n🟠 Naive RAG Result:")
    naive_system.query(question2)
    
    print("\n🔎 WNIOSEK 2: GraphRAG poda dokładną liczbę. Naive RAG poda liczbę z 'Context Window' (np. 3-5), co jest błędem.")


    # --- SCENARIUSZ 3: Logika Biznesowa (Availability) ---
    question3 = "Who is currently available (not busy)?"
    print(f"\n\n🔸 SCENARIO 3: Availability Logic ('{question3}')")
    print("-" * 60)
    
    print("🔵 GraphRAG Result:")
    # GraphRAG sprawdza relacje w bazie
    # Znajdźmy kogoś kto NIE ma relacji ASSIGNED_TO
    avail_query = "MATCH (p:Person) WHERE NOT (p)-[:ASSIGNED_TO]->() RETURN p.id LIMIT 3"
    try:
        free_people = graph_system.graph.query(avail_query)
        names = [p['p.id'] for p in free_people]
        print(f"Available people (Graph): {names} (Checking relations in DB)")
    except:
        print("Graph Availability: Error")

    print("\n🟠 Naive RAG Result:")
    naive_system.query(question3)
    
    print("\n🔎 WNIOSEK 3: Naive RAG nie wie kto jest zajęty, bo to jest stan w bazie, a nie tekst w PDF.")

if __name__ == "__main__":
    run_comparison()