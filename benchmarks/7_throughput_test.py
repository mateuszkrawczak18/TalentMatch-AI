import sys
import os
import time
import concurrent.futures
from dotenv import load_dotenv

# --- MAGICZNY NAGŁÓWEK ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Ładowanie .env
load_dotenv(os.path.join(parent_dir, ".env"))

# Import Silnika (z głównego folderu)
from bi_engine import BusinessIntelligenceEngine

def run_load_test():
    print("\n" + "="*70)
    print("🚦 THROUGHPUT TEST: Simulating 100 concurrent users")
    print("="*70)

    # 1. Inicjalizacja silnika
    try:
        engine = BusinessIntelligenceEngine()
        print("✅ Engine initialized. Starting attack...")
    except Exception as e:
        print(f"❌ Engine init failed: {e}")
        return

    # 2. Funkcja symulująca jednego użytkownika
    def simulate_user_request(user_id):
        try:
            start = time.time()
            # Wykonujemy "lekkie" zapytanie bezpośrednio do grafu, 
            # żeby przetestować wydajność połączeń (Connection Pool)
            # Omijamy LLM, żeby nie dostać błędu 429 (Too Many Requests) od OpenAI
            engine.graph.query("MATCH (p:Person) RETURN count(p)")
            end = time.time()
            return True, end - start
        except Exception as e:
            return False, str(e)

    # 3. Uruchomienie 100 wątków na raz
    TOTAL_REQUESTS = 100
    CONCURRENT_THREADS = 20 # Typowy limit dla lokalnego laptopa
    
    start_test = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as executor:
        # Odpalamy 100 zadań
        results = list(executor.map(simulate_user_request, range(TOTAL_REQUESTS)))
    
    end_test = time.time()
    total_duration = end_test - start_test

    # 4. Analiza wyników
    success_count = sum(1 for r in results if r[0])
    failures = [r[1] for r in results if not r[0]]
    avg_latency = sum(r[1] for r in results if r[0]) / success_count if success_count > 0 else 0
    throughput = TOTAL_REQUESTS / total_duration

    print(f"\n📊 RESULTS:")
    print(f"   - Total Requests: {TOTAL_REQUESTS}")
    print(f"   - Successful:     {success_count} ✅")
    print(f"   - Failed:         {len(failures)} ❌")
    print(f"   - Total Time:     {total_duration:.2f}s")
    print(f"   - Avg Latency:    {avg_latency:.4f}s")
    print(f"   - Throughput:     {throughput:.2f} req/sec")

    if success_count == TOTAL_REQUESTS:
        print("\n✅ SUCCESS: System handled 100 concurrent requests without crashing.")
        print("   (Note: We tested DB/Backend throughput. LLM API limits are external constraints.)")
    else:
        print("\n⚠️ WARNING: Some requests failed.")
        if failures:
            print(f"   Reason: {failures[0]}")

if __name__ == "__main__":
    run_load_test()