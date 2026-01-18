import time
import os
import sys
import importlib.util
from dotenv import load_dotenv

# --- MAGICZNY NAGŁÓWEK ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Ładowanie zmiennych środowiskowych
load_dotenv(os.path.join(parent_dir, ".env"))

def import_module_from_file(module_name, file_path):
    if not os.path.exists(file_path):
        print(f"❌ Critical Error: File {file_path} not found!")
        sys.exit(1)
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

print("🔄 Loading modules dynamically...")
try:
    # 1. Ładujemy Twój Inteligentny Agent (z folderu src/ w głównym katalogu)
    # parent_dir/src -> graph_agent
    src_path = os.path.join(parent_dir, 'src')
    sys.path.append(src_path)
    from graph_agent import TalentAgent
    
    # 2. Ładujemy Naive RAG (z tego samego folderu benchmarks/)
    # Ponieważ plik jest obok, używamy current_dir
    naive_path = os.path.join(current_dir, "4_naive_rag_cv.py")
    naive_module = import_module_from_file("naive_module", naive_path)
    NaiveRAGSystem = naive_module.NaiveRAGSystem
    print("✅ Modules loaded successfully.")
except Exception as e:
    print(f"❌ Error loading modules: {e}")
    sys.exit(1)

def run_comparison():
    print("\n" + "="*70)
    print("🥊 FINAL BENCHMARK: GraphRAG vs Naive RAG (Full Compliance Test)")
    print("="*70)

    # INICJALIZACJA
    print("\n[1/2] Initializing GraphRAG (TalentAgent)...")
    try:
        graph_agent = TalentAgent()
        print("✅ Graph Agent ready (connected to Neo4j).")
    except Exception as e:
        print(f"❌ GraphRAG Init Failed: {e}")
        return

    print("[2/2] Initializing Naive RAG (Vector)...")
    try:
        naive_system = NaiveRAGSystem()
        if not naive_system.ingest_data():
            print("❌ Naive RAG Ingestion Failed.")
            return
    except Exception as e:
        print(f"❌ Naive RAG Init Failed: {e}")
        return

    # --- LISTA PYTAŃ DO BATTLE (ZGODNA Z AUDYTEM PRD) ---
    scenarios = [
        {
            "name": "SCENARIO 1: Aggregation (BI Analytics)",
            "question": "What is the average hourly rate of Senior Python Developers?",
            "expected": "GraphRAG should calculate exact average. Naive RAG will fail."
        },
        {
            "name": "SCENARIO 2: Multi-hop (Network Analysis)",
            "question": "Who has worked with Jacob Young in the past?",
            "expected": "GraphRAG traverses relationships (Company/Project). Naive RAG usually fails."
        },
        {
            "name": "SCENARIO 3: Business Logic (Availability)",
            "question": "Who is currently available (not assigned to any project)?",
            "expected": "GraphRAG checks 'ASSIGNED_TO' status. Naive RAG doesn't know state."
        },
        {
            "name": "SCENARIO 4: Complex Matching (RFP)",
            "question": "I need a Senior DevOps Engineer in London who knows Docker and AWS.",
            "expected": "Both might work, but GraphRAG validates seniority strictly."
        }
    ]

    for scenario in scenarios:
        time.sleep(1) # Krótka przerwa dla API
        q = scenario["question"]
        print(f"\n\n🔸 {scenario['name']}")
        print(f"❓ Question: '{q}'")
        print(f"ℹ️  Expectation: {scenario['expected']}")
        print("-" * 70)
        
        # 1. GraphRAG (Dynamiczny + Metryki)
        print("🔵 GraphRAG Agent (Thinking...):")
        start_g = time.time() # START STOPERA
        try:
            response = graph_agent.ask(q)
            end_g = time.time()   # STOP STOPERA
            duration_g = end_g - start_g
            
            print(f"⏱️ Time: {duration_g:.2f}s")
            # Skracamy wynik jeśli jest bardzo długi, żeby nie zaśmiecać konsoli
            clean_res = str(response).strip()
            print(f"Result: {clean_res[:400]}..." if len(clean_res) > 400 else f"Result: {clean_res}")
        except Exception as e:
            print(f"Error: {e}")

        # 2. Naive RAG (Metryki)
        print("\n🟠 Naive RAG (Searching text...):")
        start_n = time.time() # START STOPERA
        try:
            naive_system.query(q)
            end_n = time.time()   # STOP STOPERA
            duration_n = end_n - start_n
            print(f"⏱️ Time: {duration_n:.2f}s")
        except Exception as e:
             print(f"Error: {e}")
        
        print("-" * 70)

    print("\n✅ Comparison Finished. Use these screenshots for your report.")

if __name__ == "__main__":
    run_comparison()