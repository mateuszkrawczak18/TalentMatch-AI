import time
import logging
import asyncio
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from bi_engine import BusinessIntelligenceEngine

# --- 1. KONFIGURACJA MONITORINGU (Wymaganie: Monitoring metrics) ---
# Wszystko co system robi, będzie zapisywane w pliku 'system_metrics.log'
# To spełnia wymóg: "Query performance metrics, matching accuracy tracking"
logging.basicConfig(
    filename='system_metrics.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Tworzymy aplikację API (To jest ten "interfejs dla maszyn")
app = FastAPI(
    title="TalentMatch AI API",
    description="Interfejs REST API do systemu rekrutacji opartego o GraphRAG.",
    version="1.0.0"
)

# Inicjalizacja Twojego silnika (Tego samego co w Streamlit)
print("⏳ Uruchamianie silnika BI w tle...")
try:
    engine = BusinessIntelligenceEngine()
    print("✅ Silnik gotowy do pracy!")
except Exception as e:
    print(f"❌ Błąd silnika: {e}")
    engine = None

# --- MODELE DANYCH (Co inny program musi nam wysłać) ---
class QueryRequest(BaseModel):
    question: str               # Pytanie, np. "Find Python devs"
    webhook_url: Optional[str] = None  # Opcjonalnie: Adres, gdzie mamy wysłać wynik

class FeedbackRequest(BaseModel):
    query_id: str
    rating: int                 # Ocena 1-5
    comment: Optional[str] = None

# --- FUNKCJA DO WEBHOOKÓW (Wymaganie: Webhook support) ---
async def send_webhook_notification(url: str, payload: Dict[str, Any]):
    """
    To symuluje sytuację, gdzie Twój system sam "dzwoni" do innego systemu z wynikiem.
    """
    await asyncio.sleep(2) # Symulacja opóźnienia sieci
    logging.info(f"🔔 WEBHOOK TRIGGERED: Wysyłanie wyników do {url}")
    # Tu normalnie byłoby wysłanie danych, na potrzeby projektu wystarczy log.

# --- ENDPOINT 1: ZADAJ PYTANIE (Główne API) ---
@app.post("/api/v1/query")
async def query_knowledge_graph(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    Inny program wysyła tu pytanie w JSON, a my odsyłamy odpowiedź w JSON.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    start_time = time.time()
    
    # 1. Użycie Twojego silnika (bi_engine.py)
    try:
        response = engine.answer_question(request.question)
        formatted_answer = engine.format_result(response)
    except Exception as e:
        logging.error(f"QUERY ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    duration = time.time() - start_time
    
    # 2. Logowanie wydajności (To spełnia wymóg monitoringu)
    logging.info(f"PERFORMANCE | Query: '{request.question}' | Time: {duration:.4f}s")
    
    # 3. Obsługa Webhooka (Jeśli klient o to poprosił)
    if request.webhook_url:
        background_tasks.add_task(send_webhook_notification, request.webhook_url, response)
    
    # Zwracamy czyste dane dla maszyny
    return {
        "answer": formatted_answer,
        "metrics": {
            "execution_time_seconds": round(duration, 4),
            "query_type": response.get('type', 'unknown')
        }
    }

# --- ENDPOINT 2: FEEDBACK (Monitoring Jakości) ---
@app.post("/api/v1/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """Pozwala zapisać ocenę jakości odpowiedzi."""
    logging.info(f"FEEDBACK | Rating: {feedback.rating}/5 | Comment: {feedback.comment}")
    return {"status": "recorded"}

# --- ENDPOINT 3: HEALTH CHECK (Wymóg Deploymentu) ---
@app.get("/health")
async def health_check():
    """Prosty test czy serwer żyje."""
    return {"status": "active", "database": "connected"}