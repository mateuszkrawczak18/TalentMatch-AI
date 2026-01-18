import sys
import os
import time
import random
from dotenv import load_dotenv

# --- MAGICZNY NAGŁÓWEK ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Ładowanie .env
load_dotenv(os.path.join(parent_dir, ".env"))

from langchain_neo4j import Neo4jGraph

# Połączenie z Neo4j
graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
    username=os.getenv("NEO4J_USERNAME", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "password123")
)

def inject_dummy_data(target_count=600):
    print(f"\n🚀 STRESS TEST: Scalability Check (Target: {target_count}+ nodes)")
    
    # 1. Sprawdź obecny stan
    try:
        current_count = graph.query("MATCH (p:Person) RETURN count(p) as c")[0]['c']
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    print(f"   📊 Current Database Size: {current_count} people")
    
    if current_count >= target_count:
        print("   ✅ Requirement Met: Database already has > 500 profiles.")
        return

    needed = target_count - current_count
    print(f"   💉 Injecting {needed} synthetic profiles (Cloning existing data)...")

    # 2. Masowe Klonowanie (Cypher Batch)
    # Klonujemy węzły, dodając losowy suffix do ID, żeby były unikalne
    query = """
    MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
    WITH p, collect(s) as skills
    LIMIT 30  // Bierzemy wzorzec z pierwszych 30 prawdziwych CV
    
    UNWIND range(1, $multiplier) as i
    CREATE (new_p:Person)
    SET new_p = p
    SET new_p.id = p.id + '_Clone_' + toString(i) + '_' + toString(rand())
    SET new_p.name = p.name + ' (Clone ' + toString(i) + ')'
    SET new_p.is_synthetic = true
    
    FOREACH (skill in skills | 
        MERGE (sk:Skill {name: skill.name}) 
        MERGE (new_p)-[:HAS_SKILL]->(sk)
    )
    """
    
    # Obliczamy ile razy trzeba pomnożyć te 30 osób
    multiplier = (needed // 30) + 2
    
    print("   ⏳ Running batch insertion (this might take 10-20s)...")
    start_time = time.time()
    try:
        graph.query(query, {"multiplier": multiplier})
    except Exception as e:
        print(f"❌ Error during injection: {e}")
        return
        
    end_time = time.time()
    
    # Weryfikacja
    final_count = graph.query("MATCH (p:Person) RETURN count(p) as c")[0]['c']
    print(f"   ✅ Injection Complete in {end_time - start_time:.2f}s")
    print(f"   🎉 Final Database Size: {final_count} people")

def benchmark_query_speed():
    print("\n⏱️ PERFORMANCE CHECK: Database Latency")
    
    # Testujemy proste wyszukiwanie w dużej bazie
    start = time.time()
    result = graph.query("""
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
        WHERE toLower(s.name) = 'python'
        RETURN count(p) as count
    """)
    end = time.time()
    duration = end - start
    
    count = result[0]['count']
    print(f"   🔍 Query: Find all Python Developers in dataset of {count} people.")
    print(f"   ⏱️ Execution Time: {duration:.4f} seconds")
    
    if duration < 0.1:
        print("   ✅ RESULT: PASS (Database is blazing fast, < 0.1s)")
    elif duration < 2.0:
        print("   ✅ RESULT: PASS (< 2.0s limit met)")
    else:
        print("   ⚠️ RESULT: SLOW (> 2.0s)")

if __name__ == "__main__":
    inject_dummy_data()
    benchmark_query_speed()