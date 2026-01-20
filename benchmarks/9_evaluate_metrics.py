import os
import sys
import pandas as pd
import importlib.util
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision
)
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_neo4j import Neo4jGraph

# --- 1. CONFIG ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(parent_dir, ".env"))

from bi_engine import BusinessIntelligenceEngine

def load_naive_module():
    spec = importlib.util.spec_from_file_location("naive_mod", os.path.join(current_dir, "4_naive_rag_cv.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.NaiveRAGSystem

# --- 2. WRAPPER DLA AZURE O1 ---
class SafeAzureChatOpenAI(AzureChatOpenAI):
    @property
    def _default_params(self):
        params = super()._default_params
        params["temperature"] = 1
        return params

azure_llm = SafeAzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    temperature=1,
    max_retries=2
)

azure_embeddings = AzureOpenAIEmbeddings(
    azure_deployment=os.getenv("AZURE_EMBEDDING_NAME", "text-embedding-3-small"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
)

# --- 3. DYNAMICZNY GROUND TRUTH ---
def get_dynamic_ground_truth():
    print("🔮 Connecting to Neo4j to fetch REAL-TIME Ground Truth...")
    try:
        graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI"), 
            username=os.getenv("NEO4J_USERNAME"), 
            password=os.getenv("NEO4J_PASSWORD")
        )
        
        # Pobieranie danych "na żywo"
        q1 = graph.query("MATCH (p:Person) WHERE toLower(p.seniority) CONTAINS 'senior' AND p.rate IS NOT NULL RETURN avg(p.rate) as val, count(p) as cnt")
        avg_rate = round(q1[0]['val'], 2) if q1 else 0
        
        q2 = graph.query("MATCH (p1:Person {name: 'Jacob Young'})-[:WORKED_AT]->(c)<-[:WORKED_AT]-(p2:Person) RETURN collect(p2.name)[..5] as names")
        jacob_friends = ", ".join(q2[0]['names']) if q2 and q2[0]['names'] else "None"
        
        q3 = graph.query("MATCH (p:Person) OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->() WITH p, sum(CASE WHEN r.allocation IS NOT NULL THEN r.allocation ELSE 0.0 END) as load WHERE load < 1.0 RETURN count(p) as cnt")
        avail_count = q3[0]['cnt'] if q3 else 0
        
        q4 = graph.query("MATCH (p:Person)-[:HAS_SKILL]->(s:Skill) WHERE toLower(s.id) CONTAINS 'aws' AND toLower(p.seniority) CONTAINS 'senior' AND toLower(p.role) CONTAINS 'devops' RETURN collect(p.name) as names")
        aws_experts = ", ".join(q4[0]['names']) if q4 and q4[0]['names'] else "None"

        q5 = graph.query("MATCH (p:Person)-[:HAS_SKILL]->(s:Skill) WHERE toLower(s.id) CONTAINS 'security' RETURN count(DISTINCT p) as cnt")
        sec_count = q5[0]['cnt'] if q5 else 0

        # Zwracamy listę wzorcową
        return [
            {"question": "What is the average hourly rate of Senior Python Developers?", "ground_truth": f"The calculated average is {avg_rate} USD."},
            {"question": "Who has worked with Jacob Young in the past?", "ground_truth": f"Colleagues include: {jacob_friends} and others from Company B."},
            {"question": "Who is currently available (has spare capacity)?", "ground_truth": f"There are exactly {avail_count} candidates available (load < 1.0)."},
            {"question": "Find Senior DevOps Engineers who know AWS.", "ground_truth": f"Matching candidates: {aws_experts}."},
            {"question": "How many candidates have 'Security' related skills?", "ground_truth": f"There are {sec_count} candidates with Security skills."},
            {"question": "Suggest an optimal team of 3 available Developers with Python skills.", "ground_truth": "Requires 3 available Python developers. If fewer exist in DB, a full team cannot be formed."}
        ]
    except Exception as e:
        print(f"⚠️ Neo4j Connection Error: {e}. Using fallback static data.")
        return [
            {"question": "Find Senior DevOps Engineers who know AWS.", "ground_truth": "List of Senior DevOps with AWS skills."}
        ]

# --- 4. GŁÓWNA PĘTLA ---
def run_benchmark():
    print("\n" + "="*60)
    print("📊 STARTING RAGAS EVALUATION (GraphRAG vs Naive RAG)")
    print("="*60)

    TEST_DATA = get_dynamic_ground_truth()

    print("🔹 Initializing Systems...")
    try:
        graph_engine = BusinessIntelligenceEngine()
        NaiveRAG = load_naive_module()
        naive_system = NaiveRAG()
        
        db_path = os.path.join(parent_dir, "chroma_db")
        if not os.path.exists(db_path) or not os.listdir(db_path):
            naive_system.ingest_data()
        else:
            naive_system.query("warmup")
            
    except Exception as e:
        print(f"❌ Init failed: {e}")
        return

    data_graph = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
    data_naive = {"question": [], "answer": [], "contexts": [], "ground_truth": []}

    print("\n🚀 Generating Answers...")
    
    for item in TEST_DATA:
        q = item["question"]
        gt = item["ground_truth"]
        print(f"   ❓ Processing: {q}")

        # --- A. GRAPH RAG ---
        g_resp = graph_engine.answer_question(q)
        g_ans = g_resp.get('natural_answer', "Error")
        decoder = g_resp.get('decoder_map', {})
        for k, v in decoder.items():
            g_ans = g_ans.replace(k, v)
        
        # Kontekst GraphRAG = wynik zapytania JSON
        g_ctx = [str(g_resp.get('result', {}))]
        
        data_graph["question"].append(q)
        data_graph["answer"].append(g_ans)
        data_graph["contexts"].append(g_ctx)
        data_graph["ground_truth"].append(gt)

        # --- B. NAIVE RAG (FIX: POBIERAMY PRAWDZIWY KONTEKST) ---
        n_ans = naive_system.query(q)
        
        # Tutaj wyciągamy prawdziwe dokumenty z bazy wektorowej!
        # Używamy retrievera z systemu Naive
        try:
            # Zakładamy, że naive_system ma dostęp do swojego vector_store
            # Jeśli nie, tworzymy retriever ad-hoc
            retriever = naive_system.vector_store.as_retriever(search_kwargs={"k": 3})
            retrieved_docs = retriever.invoke(q)
            n_ctx = [doc.page_content for doc in retrieved_docs]
        except:
            # Fallback jeśli coś pójdzie nie tak
            n_ctx = ["Error retrieving context"]

        data_naive["question"].append(q)
        data_naive["answer"].append(str(n_ans))
        data_naive["contexts"].append(n_ctx) # <--- TERAZ TO SĄ PRAWDZIWE TEKSTY CV
        data_naive["ground_truth"].append(gt)

    # --- EVALUATION ---
    print("\n⚖️  Calculating Metrics...")
    metrics = [faithfulness, answer_relevancy, context_precision]

    ds_graph = Dataset.from_dict(data_graph)
    ds_naive = Dataset.from_dict(data_naive)

    print("   👉 Evaluating GraphRAG...")
    score_graph = evaluate(ds_graph, metrics=metrics, llm=azure_llm, embeddings=azure_embeddings, raise_exceptions=False)
    
    print("   👉 Evaluating Naive RAG...")
    score_naive = evaluate(ds_naive, metrics=metrics, llm=azure_llm, embeddings=azure_embeddings, raise_exceptions=False)

    # Wyniki
    df_g = score_graph.to_pandas()
    df_n = score_naive.to_pandas()
    df_g["System"] = "GraphRAG"
    df_n["System"] = "NaiveRAG"

    final_df = pd.concat([df_g, df_n], ignore_index=True)
    output_file = os.path.join(current_dir, "ragas_evaluation_results.csv")
    final_df.to_csv(output_file, index=False)

    print("\n" + "="*60)
    print("🏆 FINAL RESULTS SUMMARY")
    print("="*60)
    print(final_df.groupby("System")[["faithfulness", "answer_relevancy", "context_precision"]].mean())
    print(f"\n✅ Results saved to: {output_file}")

if __name__ == "__main__":
    run_benchmark()