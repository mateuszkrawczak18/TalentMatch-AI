import sys
import os
import time
import importlib.util

# --- 1. SETUP ŚCIEŻEK ---
# Pozwala importować moduły z folderu głównego
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(parent_dir, ".env"))

# --- 2. IMPORTY SILNIKÓW ---

# A. GraphRAG (Twój główny silnik BI)
try:
    from bi_engine import BusinessIntelligenceEngine
    print("✅ Successfully imported BusinessIntelligenceEngine")
except ImportError as e:
    print(f"❌ Critical Error: Could not import bi_engine. Check if bi_engine.py exists in parent dir. {e}")
    sys.exit(1)

# B. Naive RAG (Dynamiczny import pliku z cyfrą w nazwie)
try:
    spec = importlib.util.spec_from_file_location("naive_rag_module", os.path.join(current_dir, "4_naive_rag_cv.py"))
    naive_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(naive_module)
    NaiveRAGSystem = naive_module.NaiveRAGSystem
    print("✅ Successfully loaded NaiveRAGSystem module")
except Exception as e:
    print(f"❌ Error loading Naive RAG module: {e}")
    sys.exit(1)

# --- 3. GŁÓWNA FUNKCJA BENCHMARKU ---

def run_benchmark():
    print("\n" + "="*70)
    print("🥊 FINAL BENCHMARK: GraphRAG (BI Engine) vs Naive RAG")
    print("="*70)

    # 1. Inicjalizacja GraphRAG
    print("\n[1/2] Initializing GraphRAG (BI Engine)...")
    try:
        graph_engine = BusinessIntelligenceEngine()
        print("✅ Graph Engine ready (connected to Neo4j).")
    except Exception as e:
        print(f"❌ GraphRAG Init Failed: {e}")
        return

    # 2. Inicjalizacja Naive RAG
    print("[2/2] Initializing Naive RAG (Vector)...")
    try:
        naive_system = NaiveRAGSystem()
        # Sprawdzamy czy baza istnieje, jak nie to budujemy
        db_path = os.path.join(parent_dir, "chroma_db")
        if not os.path.exists(db_path) or not os.listdir(db_path):
            print("   ⚠️ ChromaDB not found. Ingesting data...")
            naive_system.ingest_data()
        else:
            # "Rozgrzewka" bazy (lazy loading)
            naive_system.query("warmup")
        print("✅ Naive RAG ready.")
    except Exception as e:
        print(f"❌ Naive RAG Init Failed: {e}")
        return

    # 3. Definicja Scenariuszy (Pełne spektrum testów)
    scenarios = [
        # --- TYP 1: AGGREGATION ---
        {
            "name": "SCENARIO 1: Aggregation (Math)",
            "question": "What is the average hourly rate of Senior Python Developers?",
            "expectation": "GraphRAG: Dokładna liczba (AVG). Naive RAG: Brak danych/Halucynacja."
        },
        # --- TYP 2: REASONING ---
        {
            "name": "SCENARIO 2: Multi-hop (Relationships)",
            "question": "Who has worked with Jacob Young in the past?",
            "expectation": "GraphRAG: Lista współpracowników (Traversals). Naive RAG: Tylko Jacob/Brak."
        },
        # --- TYP 3: TEMPORAL ---
        {
            "name": "SCENARIO 3: Availability (Business Logic)",
            "question": "Who is currently available (has spare capacity)?",
            "expectation": "GraphRAG: Sumuje allocation < 1.0. Naive RAG: Zgaduje."
        },
        # --- TYP 4: FILTERING ---
        {
            "name": "SCENARIO 4: Precise Filtering",
            "question": "Find Senior DevOps Engineers who know AWS.",
            "expectation": "GraphRAG: Dokładna lista z bazy. Naive RAG: Częściowa lista z tekstu."
        },
        # --- TYP 5: COUNTING (Nowy!) ---
        {
            "name": "SCENARIO 5: Global Counting",
            "question": "How many candidates have 'Security' related skills?",
            "expectation": "GraphRAG: Dokładna liczba (COUNT). Naive RAG: 'Kilku' lub błąd."
        },
        # --- TYP 6: COMPLEX SCENARIO (Nowy!) ---
        {
            "name": "SCENARIO 6: Team Optimization",
            "question": "Suggest an optimal team of 3 available Developers with Python skills.",
            "expectation": "GraphRAG: Skill='Python' AND Availability=True -> Sort -> Limit. Naive RAG: Losowe nazwiska."
        }
    ]

    # 4. Pętla Wykonawcza
    for scenario in scenarios:
        q = scenario["question"]
        print("\n\n" + "🔸"*30)
        print(f"🔸 {scenario['name']}")
        print(f"❓ Question: '{q}'")
        print(f"ℹ️  Expectation: {scenario['expectation']}")
        print("-" * 70)

        # --- A. GraphRAG ---
        print("🔵 GraphRAG (Thinking...):")
        start_g = time.time()
        
        try:
            # Zapytanie do silnika
            g_response = graph_engine.answer_question(q)
            time_g = time.time() - start_g
            
            # LOGIKA DEKODOWANIA (TO NAPRAWIA WIDOK)
            if g_response.get('success'):
                final_answer = g_response.get('natural_answer', "")
                decoder_map = g_response.get('decoder_map', {})
                query_type = g_response.get('type', 'unknown')
                
                # Pętla podmieniająca hashe na nazwiska
                if decoder_map:
                    for fake_id, real_name in decoder_map.items():
                        final_answer = final_answer.replace(fake_id, f"{real_name}")
                
                print(f"⏱️ Time: {time_g:.2f}s")
                print(f"🏷️ Type: {query_type}")
                print(f"💡 Result:\n{final_answer.strip()}")
                
                # Opcjonalnie pokaż Cypher dla Scenariusza 6 (żeby widzieć jak to zrobił)
                if "SCENARIO 6" in scenario['name']:
                    print(f"\n[Cypher Logic]:\n{g_response.get('cypher')}")

            else:
                print(f"❌ Error: {g_response.get('error')}")
                
        except Exception as e:
            print(f"❌ Critical Crash in GraphRAG: {e}")

        print("\n" + "-" * 30)

        # --- B. Naive RAG ---
        print("🟠 Naive RAG (Searching text...):")
        start_n = time.time()
        try:
            n_response = naive_system.query(q) 
            time_n = time.time() - start_n
            
            print(f"⏱️ Time: {time_n:.2f}s")
            print(f"💡 Result:\n{n_response}")
        except Exception as e:
            print(f"❌ Error in Naive RAG: {e}")
        
        print("-" * 70)

    print("\n✅ Benchmark Finished. Zrób screenshoty do raportu!")

if __name__ == "__main__":
    run_benchmark()