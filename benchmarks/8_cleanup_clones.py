import os
import time
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph

# Ładowanie zmiennych środowiskowych
load_dotenv()

def clean_synthetic_data():
    print("🧹 Starting FORCE CLEANUP of all stress-test remains...")
    
    try:
        # Połączenie z Neo4j
        graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password123")
        )

        # 1. Agresywne zapytanie statystyczne (identyfikacja po flagach i nazwach)
        stats_query = """
        MATCH (n) 
        WHERE n.is_synthetic = true 
           OR (n:Project AND (n.name STARTS WITH 'StressActive' OR n.name STARTS WITH 'StressHist'))
           OR (n:Person AND n.name CONTAINS '(Gen ')
        RETURN labels(n)[0] as type, count(n) as count
        """
        stats = graph.query(stats_query)

        if not stats:
            print("✅ Database is already clean! No synthetic or stress-related data found.")
            return

        print("⚠️  Found the following entities to be removed:")
        total_count = 0
        for item in stats:
            print(f"   - {item['type']}: {item['count']}")
            total_count += item['count']

        # 2. Usuwanie WSZYSTKIEGO co pasuje do wzorca testów obciążeniowych
        # Używamy DETACH DELETE, aby usunąć krawędzie (np. puste projekty bez ludzi)
        delete_query = """
        MATCH (n)
        WHERE n.is_synthetic = true 
           OR (n:Project AND (n.name STARTS WITH 'StressActive' OR n.name STARTS WITH 'StressHist'))
           OR (n:Person AND n.name CONTAINS '(Gen ')
        DETACH DELETE n
        """
        
        print("\n⏳ Processing deletion... (this may take a few seconds)")
        start_time = time.time()
        graph.query(delete_query)
        duration = round(time.time() - start_time, 2)
        
        print(f"♻️  Success! Removed {total_count} entities in {duration}s.")
        print("✅ Database restored to original state (Real Candidates & Real Projects only).")

    except Exception as e:
        print(f"❌ Error during cleanup: {e}")

if __name__ == "__main__":
    clean_synthetic_data()