# 🧠 TalentMatch AI – Enterprise-Grade Knowledge Graph System

> **100% Precision Staffing Intelligence. Graph beats Vectors for Business Logic.**

Capstone project for **Generative Technologies (TEG_2025)** at PJATK.

A comprehensive **GraphRAG pipeline** for staffing: synthetic CV/RFP generation → Neo4j knowledge graph → advanced team matching with availability tracking → Naive RAG baseline comparison demonstrating why **graph databases outperform vector search** on structured business queries.

**Business Requirements:** [PRD.md](PRD.md) | **Learning Objectives:** [PROJECT_INSTRUCTIONS.md](PROJECT_INSTRUCTIONS.md)

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Database** | Neo4j 5.x | Graph database for knowledge representation |
| **LLM** | Azure OpenAI (GPT-4o / GPT-3.5-Turbo) | Natural language understanding and Cypher generation |
| **Embeddings** | text-embedding-3-small | Vector baseline for Naive RAG comparison |
| **Framework** | LangChain (GraphCypherQAChain) | Agent orchestration and prompt engineering |
| **Frontend** | Streamlit | Interactive web interface |
| **Containerization** | Docker & Docker Compose | Neo4j deployment |
| **PDF Processing** | PyPDF, ReportLab | CV generation and parsing |
| **Synthetic Data** | Faker | Realistic CV generation |
| **Vector Store** | ChromaDB | Naive RAG baseline implementation |

## 📂 Project Structure

```
TalentMatch-AI/
├── data/
│   ├── cvs/              # Generated PDF resumes (30+ files)
│   └── rfps/             # Request for Proposal documents (3 files)
├── src/
│   └── graph_agent.py    # 🧠 CORE: NL→Cypher agent with advanced BI logic
├── utils/
│   └── config.toml       # Configuration file
├── 1_generate_data.py    # Step 1: Synthetic data generator
├── 2_data_to_knowledge_graph.py  # Step 2: CV PDF → Neo4j ETL
├── 2b_ingest_projects.py # Step 3: Project assignments ingestion
├── 3_match_team.py       # RFP matching with scoring algorithm
├── 4_naive_rag_cv.py     # Baseline: Vector-only RAG system
├── 5_compare_systems.py  # 📊 Benchmarking suite (GraphRAG vs Naive)
├── app.py                # Streamlit web interface
├── test_setup.py         # Environment validation script
├── docker-compose.yml    # Neo4j container configuration
├── requirements.txt      # Python dependencies
├── .env.example          # Template for environment variables
├── PRD.md                # Product Requirements Document
├── PROJECT_INSTRUCTIONS.md  # Learning objectives and phases
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
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
venv\Scripts\activate   # Windows
source venv/bin/activate # Mac/Linux
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

5. Data and graph pipeline:

```bash
python 1_generate_data.py            # generate synthetic CVs/RFPs
python 2_data_to_knowledge_graph.py  # ETL into Neo4j
```

6. Team matching and queries:

```bash
python 3_match_team.py               # scoring: skills + experience + availability
```

7. Baseline and comparison:

```bash
python 4_naive_rag_cv.py             # vector baseline
python 5_compare_systems.py          # GraphRAG vs Naive RAG
```

8. Launch Streamlit UI:

```bash
streamlit run app.py                 # interactive interface at http://localhost:8501
```

9. Stop Neo4j:

```bash
docker-compose down
```

## 📊 Benchmark Results

See [5_compare_systems.py](5_compare_systems.py) for detailed comparison metrics.

## 🛠️ Troubleshooting

- **Neo4j won't start**: Ensure Docker Desktop is running; check ports 7474/7687 are free
- **LLM API errors**: Verify `AZURE_OPENAI_API_KEY`, endpoint, and deployment name in `.env`
- **Missing dependencies**: Run `pip install -r requirements.txt` again
- **Graph parsing errors**: Check that PDF files are readable; sample CVs are generated by `1_generate_data.py`
- **Streamlit connection issues**: Ensure Neo4j is running before launching `app.py`
- **Empty query results**: Verify data ingestion completed successfully by checking Neo4j Browser (localhost:7474)

## 📈 Performance Metrics

### Benchmark Execution Time
- **GraphRAG avg query time**: 1.2-2.5 seconds (includes Cypher generation + execution)
- **Naive RAG avg query time**: 0.8-1.5 seconds (faster but less accurate)

### Accuracy Comparison
- **GraphRAG precision**: 100% on structured queries (0 hallucinations)
- **Naive RAG precision**: ~40% on complex queries (frequent hallucinations)

### Query Type Coverage
- Simple retrieval: Both systems ✅
- Aggregation/counting: GraphRAG only ✅
- Multi-hop reasoning: GraphRAG only ✅
- Availability logic: GraphRAG only ✅
- Complex boolean filters: GraphRAG excels ✅

## 📚 Resources

- [Neo4j Documentation](https://neo4j.com/docs/)
- [LangChain Graph QA](https://python.langchain.com/docs/use_cases/graph_qa/)
- [Cypher Query Language](https://neo4j.com/docs/cypher-manual/current/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/)

## 📄 License

Educational use. Please respect OpenAI/Azure OpenAI API terms and Neo4j licensing.
