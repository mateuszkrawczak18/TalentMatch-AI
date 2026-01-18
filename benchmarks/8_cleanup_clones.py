import os
import time
from dotenv import load_dotenv
from langchain_community.graphs import Neo4jGraph

# Ładowanie zmiennych środowiskowych
load_dotenv()

def clean_synthetic_data():
    print("🧹 Connecting to Neo4j to clean up stress-test data...")
    
    try:
        graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password123")
        )

        # 1. Sprawdź, ile jest klonów
        count_query = "MATCH (n:Person) WHERE n.is_synthetic = true RETURN count(n) as count"
        result = graph.query(count_query)
        count = result[0]['count']

        if count == 0:
            print("✅ Database is already clean! No synthetic clones found.")
            return

        print(f"⚠️  Found {count} synthetic clones (created by Stress Test). Deleting them now...")

        # 2. Usuń tylko klony (flaga is_synthetic)
        delete_query = """
        MATCH (n)
        WHERE n.is_synthetic = true
        DETACH DELETE n
        """
        graph.query(delete_query)
        
        print(f"♻️  Success! {count} clones removed.")
        print("✅ Database restored to original state (Real Candidates only).")

    except Exception as e:
        print(f"❌ Error during cleanup: {e}")

if __name__ == "__main__":
    clean_synthetic_data()