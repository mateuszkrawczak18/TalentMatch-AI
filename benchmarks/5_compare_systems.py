import sys
import os
import time
import csv
import statistics
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

# Configuration
RUNS_PER_SCENARIO = 5  # Number of times to run each scenario for statistical analysis

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

    # 4. CSV Results Storage
    csv_file = os.path.join(parent_dir, "benchmarks", "benchmark_results.csv")
    csv_exists = os.path.exists(csv_file)
    
    # Open CSV file for writing
    with open(csv_file, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['scenario', 'system', 'run_idx', 'latency_seconds', 'success', 'timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not csv_exists:
            writer.writeheader()
        
        # 5. Statistics tracking
        graphrag_times = {s['name']: [] for s in scenarios}
        naive_times = {s['name']: [] for s in scenarios}
        
        # 6. Pętla Wykonawcza (Multiple runs)
        for run_idx in range(1, RUNS_PER_SCENARIO + 1):
            print(f"\n{'='*70}")
            print(f"🔄 RUN {run_idx}/{RUNS_PER_SCENARIO}")
            print(f"{'='*70}")
            
            for scenario in scenarios:
                q = scenario["question"]
                scenario_name = scenario["name"]
                
                if run_idx == 1:  # Only show details on first run
                    print("\n\n" + "🔸"*30)
                    print(f"🔸 {scenario_name}")
                    print(f"❓ Question: '{q}'")
                    print(f"ℹ️  Expectation: {scenario['expectation']}")
                    print("-" * 70)
                else:
                    print(f"\n▶️ {scenario_name} - Run {run_idx}/{RUNS_PER_SCENARIO}", end=" ")

                # --- A. GraphRAG ---
                if run_idx == 1:
                    print("🔵 GraphRAG (Thinking...):")
                
                start_g = time.time()
                success_g = False
                
                try:
                    # Zapytanie do silnika
                    g_response = graph_engine.answer_question(q)
                    time_g = time.time() - start_g
                    
                    # LOGIKA DEKODOWANIA (TO NAPRAWIA WIDOK)
                    if g_response.get('success'):
                        success_g = True
                        graphrag_times[scenario_name].append(time_g)
                        
                        if run_idx == 1:  # Only show details on first run
                            final_answer = g_response.get('natural_answer', "")
                            
                            # Retrieve query type from the plan object
                            plan_data = g_response.get('plan', {})
                            query_type = plan_data.get('type', 'unknown')
                            
                            # Note: decoder_map logic removed as names are not masked in current BI Engine
                            
                            print(f"⏱️ Time: {time_g:.2f}s")
                            print(f"🏷️ Type: {query_type}")
                            print(f"💡 Result:\n{final_answer.strip()}")
                            
                            # Opcjonalnie pokaż Cypher dla Scenariusza 6 (żeby widzieć jak to zrobił)
                            if "SCENARIO 6" in scenario_name:
                                print(f"\n[Cypher Logic]:\n{g_response.get('cypher')}")
                    else:
                        if run_idx == 1:
                            print(f"❌ Error: {g_response.get('error')}")
                        
                except Exception as e:
                    time_g = time.time() - start_g
                    if run_idx == 1:
                        print(f"❌ Critical Crash in GraphRAG: {e}")
                
                # Write to CSV
                writer.writerow({
                    'scenario': scenario_name,
                    'system': 'GraphRAG',
                    'run_idx': run_idx,
                    'latency_seconds': round(time_g, 4),
                    'success': success_g,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                })

                if run_idx == 1:
                    print("\n" + "-" * 30)

                # --- B. Naive RAG ---
                if run_idx == 1:
                    print("🟠 Naive RAG (Searching text...):")
                
                start_n = time.time()
                success_n = False
                
                try:
                    n_response = naive_system.query(q) 
                    time_n = time.time() - start_n
                    success_n = bool(n_response)
                    naive_times[scenario_name].append(time_n)
                    
                    if run_idx == 1:
                        print(f"⏱️ Time: {time_n:.2f}s")
                        print(f"💡 Result:\n{n_response}")
                except Exception as e:
                    time_n = time.time() - start_n
                    if run_idx == 1:
                        print(f"❌ Error in Naive RAG: {e}")
                
                # Write to CSV
                writer.writerow({
                    'scenario': scenario_name,
                    'system': 'NaiveRAG',
                    'run_idx': run_idx,
                    'latency_seconds': round(time_n, 4),
                    'success': success_n,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                })
                
                if run_idx == 1:
                    print("-" * 70)
                elif run_idx == RUNS_PER_SCENARIO:
                    print(f"✓ (GraphRAG: {time_g:.2f}s, NaiveRAG: {time_n:.2f}s)")
    
    # 7. Print Statistics Summary
    print("\n" + "="*70)
    print("📊 PERFORMANCE STATISTICS SUMMARY")
    print("="*70)
    print(f"Runs per scenario: {RUNS_PER_SCENARIO}\n")
    
    for scenario in scenarios:
        sname = scenario['name']
        g_times = graphrag_times[sname]
        n_times = naive_times[sname]
        
        print(f"\n{sname}")
        print("-" * 70)
        
        if g_times:
            g_avg = statistics.mean(g_times)
            g_p95 = sorted(g_times)[int(len(g_times) * 0.95)] if len(g_times) > 1 else g_times[0]
            print(f"  GraphRAG:  avg={g_avg:.3f}s, p95={g_p95:.3f}s, min={min(g_times):.3f}s, max={max(g_times):.3f}s")
        
        if n_times:
            n_avg = statistics.mean(n_times)
            n_p95 = sorted(n_times)[int(len(n_times) * 0.95)] if len(n_times) > 1 else n_times[0]
            print(f"  NaiveRAG:  avg={n_avg:.3f}s, p95={n_p95:.3f}s, min={min(n_times):.3f}s, max={max(n_times):.3f}s")
        
        if g_times and n_times:
            speedup = statistics.mean(n_times) / statistics.mean(g_times)
            print(f"  Speedup: {speedup:.2f}x ({'GraphRAG faster' if speedup > 1 else 'NaiveRAG faster'})")
    
    print("\n" + "="*70)
    print(f"✅ Benchmark Finished! Results saved to: {csv_file}")
    print("="*70)

if __name__ == "__main__":
    run_benchmark()