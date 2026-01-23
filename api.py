import os
import time
import uuid
import logging
from typing import Optional, Dict, Any

import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from bi_engine import BusinessIntelligenceEngine

# --- 1) LOGGING / METRICS ---
LOG_PATH = os.getenv("SYSTEM_METRICS_LOG", "system_metrics.log")
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="TalentMatch AI API",
    description="Interfejs REST API do systemu rekrutacji opartego o GraphRAG.",
    version="1.1.0",
)

# Global engine (init on startup)
engine: Optional[BusinessIntelligenceEngine] = None


# --- 2) STARTUP: INIT ENGINE ONCE ---
@app.on_event("startup")
def startup_init():
    global engine
    try:
        logging.info("STARTUP | Initializing BusinessIntelligenceEngine...")
        engine = BusinessIntelligenceEngine()
        logging.info("STARTUP | Engine initialized successfully.")
    except Exception as e:
        engine = None
        logging.error(f"STARTUP | Engine initialization failed: {e}")


# --- 3) REQUEST MODELS ---
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    webhook_url: Optional[str] = None  # Optional webhook for async delivery


class FeedbackRequest(BaseModel):
    query_id: str = Field(..., min_length=1)
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class CypherRequest(BaseModel):
    query: str = Field(..., min_length=1)
    params: Optional[Dict[str, Any]] = None


# --- 4) WEBHOOK SUPPORT (REAL HTTP POST) ---
def send_webhook_notification(url: str, payload: Dict[str, Any]) -> None:
    """
    Sends the payload to a webhook URL (best effort).
    Runs in FastAPI BackgroundTasks (sync).
    """
    try:
        # Keep timeouts tight to avoid resource hogging
        resp = requests.post(url, json=payload, timeout=(3.0, 10.0))
        logging.info(f"WEBHOOK | url={url} | status={resp.status_code}")
    except Exception as e:
        logging.warning(f"WEBHOOK | url={url} | failed={e}")


# --- 5) MAIN ENDPOINT: QUERY ---
@app.post("/api/v1/query")
def query_knowledge_graph(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    Send a question, get an answer + metrics + query_id.
    """
    global engine
    if engine is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    query_id = str(uuid.uuid4())
    start_time = time.time()

    logging.info(f"QUERY_START | id={query_id} | q={request.question!r}")

    try:
        response = engine.answer_question(request.question)
        formatted_answer = engine.format_result(response)
    except Exception as e:
        logging.error(f"QUERY_ERROR | id={query_id} | err={e}")
        raise HTTPException(status_code=500, detail=str(e))

    duration = time.time() - start_time
    query_type = (response.get("plan", {}) or {}).get("query_type", "unknown")

    # Basic performance metric logging
    logging.info(
        f"QUERY_END | id={query_id} | type={query_type} | time={duration:.4f}s"
    )

    # Webhook: send full response (includes cypher, decoder_map, etc.)
    # If you want stricter GDPR behavior here, send only a reduced payload.
    if request.webhook_url:
        webhook_payload = {
            "query_id": query_id,
            "question": request.question,
            "result": response,
            "formatted_answer": formatted_answer,
            "metrics": {
                "execution_time_seconds": round(duration, 4),
                "query_type": query_type,
            },
        }
        background_tasks.add_task(send_webhook_notification, request.webhook_url, webhook_payload)

    return {
        "query_id": query_id,
        "answer": formatted_answer,
        "metrics": {
            "execution_time_seconds": round(duration, 4),
            "query_type": query_type,
        },
    }


# --- 6) FEEDBACK ENDPOINT ---
@app.post("/api/v1/feedback")
def submit_feedback(feedback: FeedbackRequest):
    """
    Records feedback tied to a query_id (for quality monitoring).
    """
    logging.info(
        f"FEEDBACK | id={feedback.query_id} | rating={feedback.rating}/5 | comment={feedback.comment}"
    )
    return {"status": "recorded", "query_id": feedback.query_id}


# --- 7) CYPHER QUERY ENDPOINT (READ-ONLY) ---
@app.post("/api/v1/cypher")
def execute_cypher(request: CypherRequest):
    """
    Execute a read-only Cypher query directly against Neo4j.
    
    Security:
    - Blocks write operations (CREATE, MERGE, DELETE, SET, DROP, etc.)
    - Only allows MATCH, RETURN, WITH, ORDER BY, LIMIT, etc.
    """
    global engine
    if engine is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    query = (request.query or "").strip()
    
    # Validate query is read-only
    forbidden_keywords = [
        "create", "merge", "delete", "detach", "set", "drop", "remove",
        "call", "load csv", "apoc", "gds", "periodic", "foreach",
        "dbms", "admin", "schema"
    ]
    
    query_lower = query.lower()
    
    # Check for forbidden operations
    for keyword in forbidden_keywords:
        if keyword in query_lower:
            logging.warning(f"CYPHER_BLOCKED | keyword={keyword} | query={query[:100]}")
            raise HTTPException(
                status_code=403,
                detail=f"Write operation not allowed. Blocked keyword: {keyword}"
            )
    
    # Must start with MATCH, WITH, or RETURN
    if not query_lower.startswith(("match", "with", "return")):
        raise HTTPException(
            status_code=400,
            detail="Query must start with MATCH, WITH, or RETURN"
        )
    
    try:
        start_time = time.time()
        params = request.params or {}
        
        logging.info(f"CYPHER_EXEC | query={query[:100]}... | params={params}")
        
        result = engine.graph.query(query, params)
        duration = time.time() - start_time
        
        logging.info(f"CYPHER_SUCCESS | rows={len(result)} | time={duration:.4f}s")
        
        return {
            "success": True,
            "result": result,
            "row_count": len(result),
            "execution_time_seconds": round(duration, 4)
        }
        
    except Exception as e:
        logging.error(f"CYPHER_ERROR | err={e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 8) HEALTH CHECK (REAL DB CHECK) ---
@app.get("/health")
def health_check():
    """
    Health check: verifies API + Neo4j connectivity.
    """
    global engine
    if engine is None:
        return {"status": "degraded", "engine": "not_initialized", "database": "unknown"}

    try:
        # Real ping to Neo4j
        res = engine.graph.query("RETURN 1 as ok")
        ok = bool(res and res[0].get("ok") == 1)
        return {
            "status": "active" if ok else "degraded",
            "engine": "ready",
            "database": "connected" if ok else "not_connected",
        }
    except Exception as e:
        logging.warning(f"HEALTH | db_check_failed={e}")
        return {"status": "degraded", "engine": "ready", "database": "not_connected"}
