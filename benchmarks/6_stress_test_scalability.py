import os
import time
import random
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph

load_dotenv()

# Konfiguracja
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

def run_stress_test():
    print("\n🚀 STRESS TEST: Scalability Check (Target: 600+ nodes)")
    
    try:
        graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return

    # 1. Sprawdź obecny stan
    count_query = "MATCH (p:Person) RETURN count(p) as cnt"
    current_count = graph.query(count_query)[0]['cnt']
    print(f"    📊 Current Database Size: {current_count} people")

    target_count = 600
    if current_count >= target_count:
        print("    ✅ Database already large enough. Skipping injection.")
    else:
        # Oblicz mnożnik, żeby przebić 600
        needed = target_count - current_count
        # Obliczenie mnożnika: $multiplier = \text{int}\left(\left(\frac{needed}{current\_count}\right) \times 1.2\right) + 1$
        multiplier = int((needed / current_count) * 1.2) + 1  
        
        print(f"    💉 Injecting synthetic profiles (Multiplier: x{multiplier})...")
        print("    ⏳ Running injection (This forces Active/Historical projects)...")
        
        start_inj = time.time()
        
        # --- ZMIANA: Dodanie is_synthetic do projektów ---
        injection_cypher = """
        MATCH (p:Person)
        WITH collect(p) as people
        UNWIND people as p
        UNWIND range(1, $multiplier) as i
        
        // A. Klonowanie Osoby
        CREATE (new_p:Person)
        SET new_p = p {
            .*,
            id: p.id + '_Gen_' + toString(i) + '_' + toString(rand()),
            name: p.name + ' (Gen ' + toString(i) + ')',
            is_synthetic: true
        }
        
        // B. Klonowanie Skilli
        WITH new_p, p, i
        OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
        FOREACH (ignoreMe IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END |
            MERGE (sk:Skill {id: s.id})
            MERGE (new_p)-[:HAS_SKILL]->(sk)
        )
        FOREACH (ignoreMe IN CASE WHEN s IS NULL THEN [1] ELSE [] END |
            MERGE (sk:Skill {id: 'Python'})
            MERGE (new_p)-[:HAS_SKILL]->(sk)
        )

        // C. WYMUSZENIE PROJEKTÓW (Z FLAGĄ IS_SYNTHETIC)
        // Każdy klon dostaje 1 aktywny projekt
        MERGE (ap:Project {name: 'StressActive_' + toString(new_p.id)})
        SET ap.status = 'Active', 
            ap.is_synthetic = true  // <--- KLUCZOWA POPRAWKA
        MERGE (new_p)-[:ASSIGNED_TO {
            role: 'Developer',
            allocation: 1.0,
            start_date: date(),
            end_date: date() + duration('P6M')
        }]->(ap)

        // Każdy klon dostaje 1 historyczny projekt
        MERGE (hp:Project {name: 'StressHist_' + toString(new_p.id)})
        SET hp.status = 'Closed', 
            hp.is_synthetic = true  // <--- KLUCZOWA POPRAWKA
        MERGE (new_p)-[:ASSIGNED_TO {
            role: 'Junior',
            allocation: 0.0,
            start_date: date() - duration('P2Y'),
            end_date: date() - duration('P1Y')
        }]->(hp)
        """
        
        graph.query(injection_cypher, params={"multiplier": multiplier})
        
        time_inj = time.time() - start_inj
        print(f"    ✅ Injection Complete in {time_inj:.2f}s")

    # 2. Weryfikacja
    final_people = graph.query("MATCH (p:Person) RETURN count(p) as cnt")[0]['cnt']
    active_proj = graph.query("MATCH (p:Project {status: 'Active'}) RETURN count(p) as cnt")[0]['cnt']
    closed_proj = graph.query("MATCH (p:Project {status: 'Closed'}) RETURN count(p) as cnt")[0]['cnt']

    print(f"    🎉 Final Stats:")
    print(f"      - People:          {final_people} (Target: >600)")
    print(f"      - Active Projects: {active_proj} (Target: >50)")
    print(f"      - Closed Projects: {closed_proj} (Target: >100)")

    # 3. Testy Wydajności
    print("\n⏱️ PERFORMANCE CHECK: Database Latency")
    
    t1_start = time.time()
    res1 = graph.query("MATCH (p:Person)-[:HAS_SKILL]->(s:Skill) WHERE toLower(s.id) CONTAINS 'python' RETURN count(p) as cnt")
    t1_end = time.time()
    print(f"    Test 1 (Simple Filter): Find Python Devs ({res1[0]['cnt']} hits)")
    print(f"      ⏱️ Time: {t1_end - t1_start:.4f}s")

    t2_start = time.time()
    res2 = graph.query("""
        MATCH (p:Person)-[r:ASSIGNED_TO]->(pr:Project {status: 'Active'})
        RETURN count(p) as total_active
    """)
    t2_end = time.time()
    print(f"    Test 2 (Aggregation): Count Active Assignments ({res2[0]['total_active']} hits)")
    print(f"      ⏱️ Time: {t2_end - t2_start:.4f}s")

    if (t1_end - t1_start) < 0.1 and (t2_end - t2_start) < 0.2:
        print("    ✅ RESULT: PASS (Blazing fast < 100ms)")
    else:
        print("    ⚠️ RESULT: WARNING (Check indexes)")

if __name__ == "__main__":
    run_stress_test()