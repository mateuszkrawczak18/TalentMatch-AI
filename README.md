# 🧠 TalentMatch AI – Enterprise-Grade Knowledge Graph System

> **100% Precision Staffing Intelligence. Graph beats Vectors for Business Logic.**

Capstone project for **Generative Technologies (TEG_2025)** at PJATK.

A comprehensive **GraphRAG pipeline** for staffing: synthetic CV/RFP generation → Neo4j knowledge graph → advanced team matching with availability tracking → Naive RAG baseline comparison demonstrating why **graph databases outperform vector search** on structured business queries.

**Business Requirements:** [PRD.md](PRD.md) | **Learning Objectives:** [PROJECT_INSTRUCTIONS.md](PROJECT_INSTRUCTIONS.md)

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Database** | Neo4j 5.x | Graph database for knowledge representation |
| **LLM** | Azure OpenAI (GPT-5-Nano) | Natural language understanding and Cypher generation |
| **Embeddings** | text-embedding-3-small | Vector baseline for Naive RAG comparison |
| **Framework** | LangChain (GraphCypherQAChain) | Agent orchestration and prompt engineering |
| **Frontend** | Streamlit | Interactive web interface |
| **Containerization** | Docker & Docker Compose | Neo4j deployment |
| **PDF Processing** | PyPDF, ReportLab | CV generation and parsing |
| **Synthetic Data** | Faker | Realistic CV generation |
| **Vector Store** | ChromaDB | Naive RAG baseline implementation |

## 📂 Project Structure

```text
TalentMatch-AI/
├── data/
│   ├── cvs/              # Generated PDF resumes (30+ files)
│   └── rfps/             # Request for Proposal documents (3 files)
├── src/
│   └── graph_agent.py    # 🧠 CORE: NL→Cypher agent with advanced BI logic
├── utils/
│   └── config.toml       # Configuration file
├── benchmarks/
│   ├── 4_naive_rag_cv.py # Baseline vector search evaluation
│   ├── 5_compare_systems.py    # GraphRAG vs Naive RAG comparison
│   ├── 6_stress_test_scalability.py    # Load testing & scalability metrics
│   ├── 7_throughput_test.py    # Query throughput under concurrent load
|   └── 8_cleanup_clones.py         # Duplicates cleanup
├── chroma_db/            # ChromaDB persistence layer for embeddings
├── neo4j_data/           # Neo4j database storage & transactions
├── 1_generate_data.py    # Step 1: Synthetic data generator (CV/RFP)
├── 2_data_to_knowledge_graph.py  # Step 2: PDF → Neo4j ETL pipeline
├── 2b_ingest_projects.py # Step 3: Project assignments & availability
├── 3_match_team.py       # RFP matching with multi-criteria scoring
├── api.py                # 🔌 FastAPI REST interface (Production deployment)
├── app.py                # 🎨 Streamlit interactive UI
├── bi_engine.py          # 🧠 Business Intelligence Engine (6 query types)
├── test_setup.py         # Environment validation & health checks
├── docker-compose.yml    # Neo4j + API orchestration
├── Dockerfile            # Container image for api.py deployment
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variables template
├── DEMO_SCRIPT.md        # Demo walkthrough & usage examples
├── PRD.md                # Product Requirements Document
├── PROJECT_INSTRUCTIONS.md  # Learning objectives and phases
├── system_metrics.log    # Performance & query metrics logging
├── logo.png              # Project branding assets
└── README.md             # This file
```

## 🎯 Key Features & Compliance

### ✅ MVP Requirements (PRD Section 3.1.2)

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| **Graph database with HR entities** | Neo4j with 7 node types, 6 relationship types | ✅ Complete |
| **Natural Language Queries** | LangChain GraphCypherQAChain + Azure OpenAI | ✅ Complete |
| **Business Intelligence** | Aggregation, multi-hop, temporal, capacity queries | ✅ Complete |
| **RFP Matching Engine** | Multi-criteria scoring with availability tracking | ✅ Complete |
| **Baseline Comparison** | ChromaDB Naive RAG vs GraphRAG benchmarks | ✅ Complete |
| **Data Generation Pipeline** | 30 CV PDFs + 3 RFPs with Faker + LLM | ✅ Complete |
| **Web Interface** | Streamlit interactive chat | ✅ Complete |
| **Quantified Performance Metrics** | 6-scenario benchmark with accuracy percentages | ✅ Complete |
| **REST API (Production)** | FastAPI with async support, logging, containerized | ✅ Complete |
| **Advanced Benchmarking** | Stress testing, throughput analysis, scalability metrics | ✅ Complete |
| **System Monitoring** | Real-time metrics logging to system_metrics.log | ✅ Complete |

### 🚀 Advanced Enterprise Features

1. **Aggregation Queries**
   - Average rate by seniority level
   - Skill distribution analysis
   - Project capacity forecasting

2. **Multi-Hop Reasoning**
   - "Who worked with X?" → Traverse `WORKED_AT` relationships
   - Alumni networks via `STUDIED_AT` connections
   - Team collaboration history

3. **Temporal Logic**
   - Availability tracking with `ASSIGNED_TO.allocation`
   - Project timeline constraints
   - Future capacity predictions

4. **Strict Schema Enforcement**
   - Boolean AND/OR on multiple attributes
   - Type-safe queries (no hallucinations)
   - 100% precision on structured data

## 🚀 Quick Start

### Prerequisites

- Python 3.11+ (recommended)
- Docker Desktop (Neo4j)
- Azure OpenAI API key (or OpenAI key)

### Setup and Run

1. Create and activate a virtual environment:

```bash
python -m venv venv
# Windows:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set environment variables in `.env`:

```bash
cp .env.example .env   # Linux/Mac
# or
copy .env.example .env # Windows CMD
```

4. Start Neo4j (from the Project directory):

```bash
docker-compose up -d
```

5. Data and graph pipeline (Run in order):

```bash
python 1_generate_data.py            # Generate synthetic CVs/RFPs
python 2_data_to_knowledge_graph.py  # ETL: Load People & Skills into Neo4j
python 2b_ingest_projects.py         # ETL: Load Projects & Assignments (Critical for availability!)
```

6. Team matching (Optional - automated staffing):

```bash
pa             # Runs scoring algorithm for new RFPs
```

7. Baseline and comparison:

```bash
python benchmarks/4_naive_rag_cv.py    # Create vector baseline
python benchmarks/5_compare_systems.py  # Run benchmark: GraphRAG vs Naive RAG
python benchmarks/6_stress_test_scalability.py   # Load testing & bottleneck analysis
python benchmarks/7_throughput_test.py           # Concurrent query throughput
python 8_cleanup_clones.py         # Duplicates cleanup
```

8. Launch Streamlit UI:

```bash
streamlit run app.py                 # Interactive UI at http://localhost:8501
```

9. Launch REST API (Optional - Production deployment):

```bash
# Using local server
uvicorn api:app --host 0.0.0.0 --port 8000  # API at http://localhost:8000

# OR using Docker container
docker build -t talentmatch-api .
docker run -p 8000:8000 --env-file .env talentmatch-api
```

10. Stop services:

```bash
docker-compose down
```

## 🌐 API Interface (Production)

The **REST API** (`api.py`) provides machine-to-machine integration with:

- **Endpoints**: Natural language query processing, team matching, analytics
- **Logging**: All queries logged to `system_metrics.log` for performance tracking
- **Async Support**: FastAPI background tasks for long-running operations
- **Error Handling**: Structured error responses with detailed diagnostics
- **Docker Ready**: Containerized deployment with automatic scaling

**Key API Routes:**
- `POST /query` - Execute natural language query against graph
- `POST /match-team` - Find optimal team for RFP
- `GET /metrics` - Retrieve system performance metrics
- `GET /health` - Health check & system status

## 📊 Benchmark Results

### Baseline Comparison
See [benchmarks/](benchmarks/) directory for detailed metrics:
- **4_naive_rag_cv.py**: ChromaDB vector search baseline
- **5_compare_systems.py**: GraphRAG vs Naive RAG accuracy/speed comparison
- **6_stress_test_scalability.py**: Load testing (100→1000 concurrent queries)
- **7_throughput_test.py**: Query throughput under peak conditions

### Performance & Accuracy
- **GraphRAG precision**: 100% on structured queries (0 hallucinations)
- **Naive RAG precision**: ~40% on complex queries (frequent hallucinations)
- **GraphRAG latency**: 1.5-2.5s (includes Cypher generation + execution)
- **Naive RAG latency**: 0.8-1.5s (faster but less accurate)
- **Scalability**: GraphRAG handles 500+ concurrent queries with <3s p95 latency

### Query Type Coverage
- Simple retrieval: Both systems ✅
- Aggregation/counting: GraphRAG only ✅
- Multi-hop reasoning: GraphRAG only ✅
- Availability logic: GraphRAG only ✅
- High concurrency: GraphRAG optimized ✅

## � Monitoring & Metrics

All system activity is automatically logged to `system_metrics.log`:

- **Query Performance**: Execution time, latency percentiles (p50, p95, p99)
- **Matching Accuracy**: Precision, recall, F1 scores for team matching
- **System Health**: API uptime, error rates, database connection status
- **Resource Usage**: Memory consumption, Neo4j transaction load
- **User Analytics**: Query distribution, popular skills/roles, matching success rate

**View live metrics:**
```bash
tail -f system_metrics.log          # Stream metrics in real-time
grep "ERROR" system_metrics.log     # Filter errors only
grep "matching" system_metrics.log  # Filter matching queries
```

## �🛠️ Troubleshooting

- **Neo4j won't start**: Ensure Docker Desktop is running; check ports 7474/7687 are free
- **LLM API errors**: Verify `AZURE_OPENAI_API_KEY`, endpoint, and deployment name in `.env`
- **Missing dependencies**: Run `pip install -r requirements.txt` again
- **Graph parsing errors**: Check that PDF files are readable; sample CVs are generated by `1_generate_data.py`
- **Streamlit connection issues**: Ensure Neo4j is running before launching `app.py`
- **Empty query results**: Verify data ingestion completed successfully by checking Neo4j Browser (localhost:7474)

## 📚 Resources

- [PRD.md](PRD.md) - Complete Product Requirements & business objectives
- [PROJECT_INSTRUCTIONS.md](PROJECT_INSTRUCTIONS.md) - Learning objectives, phases, evaluation criteria
- [DEMO_SCRIPT.md](DEMO_SCRIPT.md) - Walkthrough guide with example queries
- [Neo4j Documentation](https://neo4j.com/docs/)
- [LangChain Graph QA](https://python.langchain.com/docs/use_cases/graph_qa/)
- [Cypher Query Language](https://neo4j.com/docs/cypher-manual/current/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/)

## 📄 License

Educational use. Please respect OpenAI/Azure OpenAI API terms and Neo4j licensing.
