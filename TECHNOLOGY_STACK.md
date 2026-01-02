# TalentMatch AI - Technology Stack Diagram & Dependencies

## 🏛️ Complete Technology Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TIER 1: LLM & AI                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Azure OpenAI API (gpt-5-nano model)                               │
│  ├─ Used by: Files 1, 2, 3, 6                                      │
│  ├─ Functions:                                                      │
│  │  ├─ CV content generation (File 1)                             │
│  │  ├─ Entity extraction (File 2 - LLMGraphTransformer)           │
│  │  ├─ RFP requirement analysis (File 3)                          │
│  │  └─ Query classification (File 6)                              │
│  ├─ Temperature: 1.0 (fixed for gpt-5-nano)                       │
│  └─ Cost: Pay per token                                            │
│                                                                      │
│  LangChain Framework (orchestration layer)                         │
│  ├─ Connects all AI components                                     │
│  ├─ Manages LLM chains & prompts                                   │
│  ├─ Handles document loading & processing                          │
│  └─ Version: >= 0.1.16                                             │
│                                                                      │
│  LLMGraphTransformer (Entity extraction)                           │
│  ├─ Converts unstructured text → knowledge graph                  │
│  ├─ Extracts entities (Person, Skill, Company, etc)               │
│  ├─ Identifies relationships                                       │
│  └─ CRITICAL for GraphRAG                                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                   TIER 2: DATABASE & STORAGE                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Neo4j Graph Database (5.11.0)                                     │
│  ├─ Purpose: Knowledge graph storage & query                       │
│  ├─ Running: Docker container                                      │
│  ├─ Ports: 7474 (browser UI), 7687 (Bolt/Python)                  │
│  ├─ Data Format:                                                    │
│  │  ├─ NODES: Person, Skill, Company, Location, etc               │
│  │  └─ RELATIONSHIPS: HAS_SKILL, ASSIGNED_TO, WORKED_AT, etc     │
│  ├─ Queried with: Cypher query language                            │
│  ├─ Plugin: APOC (advanced graph algorithms)                       │
│  └─ Storage: Persistent volume ./neo4j_data                        │
│                                                                      │
│  ChromaDB (Vector Database)                                        │
│  ├─ Purpose: Store vector embeddings (Naive RAG baseline)         │
│  ├─ Used by: File 4 only                                           │
│  ├─ Format: Vector embeddings (1536-dim vectors)                  │
│  ├─ Storage: Persistent or in-memory                               │
│  └─ For comparison: Shows why GraphRAG > Vector RAG                │
│                                                                      │
│  File System                                                        │
│  ├─ data/cvs/ → PDF files (CVs)                                   │
│  ├─ data/rfps/ → PDF files (RFPs)                                 │
│  └─ neo4j_data/ → Neo4j persistent storage                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                  TIER 3: DOCUMENT PROCESSING                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  PDF Generation                                                     │
│  ├─ ReportLab (PDF engine)                                         │
│  │  ├─ Creates professional PDF documents                          │
│  │  ├─ Used by: File 1 (generate synthetic CVs)                   │
│  │  └─ Output: /data/cvs/*.pdf                                     │
│  └─ Faker (fake data)                                              │
│     ├─ Generates realistic names, company names                    │
│     ├─ Used by: File 1                                             │
│     └─ Ensures no real PII in test data                            │
│                                                                      │
│  PDF Processing                                                     │
│  ├─ PyPDFLoader                                                     │
│  │  ├─ Reads PDF files                                             │
│  │  ├─ Extracts text content                                       │
│  │  └─ Used by: Files 2, 3, 4                                      │
│  │                                                                   │
│  └─ Unstructured (document parsing)                                │
│     ├─ Advanced PDF processing                                     │
│     ├─ Handles complex layouts                                     │
│     └─ Version: >= 0.13.0                                          │
│                                                                      │
│  Text Splitting                                                     │
│  ├─ RecursiveCharacterTextSplitter                                │
│  │  ├─ Breaks long documents into chunks                           │
│  │  ├─ Used by: File 4 (for Naive RAG)                            │
│  │  └─ Chunk size: ~500 characters                                 │
│  └─ TikToken (token counting)                                      │
│     ├─ Counts tokens for API billing                               │
│     └─ Helps optimize prompt sizes                                 │
│                                                                      │
│  Embeddings                                                         │
│  ├─ Azure OpenAI Embeddings (text-embedding-3-small)              │
│  │  ├─ Converts text → vectors (1536-dim)                         │
│  │  ├─ Used by: File 4 (Naive RAG)                                │
│  │  └─ For similarity search                                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                 TIER 4: UTILITIES & CONFIGURATION                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Python Environment                                                │
│  ├─ Version: 3.11+ (recommended)                                   │
│  ├─ Virtual Environment (venv)                                     │
│  │  ├─ Isolates dependencies                                       │
│  │  └─ Activated: source venv/bin/activate                        │
│  └─ Package Manager: pip                                           │
│                                                                      │
│  Configuration Management                                          │
│  ├─ python-dotenv                                                  │
│  │  ├─ Loads .env file                                             │
│  │  ├─ Manages secrets (API keys, passwords)                      │
│  │  └─ Example: AZURE_OPENAI_API_KEY                              │
│  │                                                                   │
│  └─ TOML (configuration files)                                     │
│     ├─ Stores config in utils/config.toml                         │
│     ├─ Defines generation parameters                               │
│     └─ Example: num_programmers = 30                               │
│                                                                      │
│  Containerization                                                   │
│  ├─ Docker (container runtime)                                     │
│  ├─ docker-compose.yml (orchestration)                             │
│  │  ├─ Defines Neo4j service                                       │
│  │  ├─ Sets environment variables                                  │
│  │  ├─ Maps ports and volumes                                      │
│  │  └─ Command: docker-compose up -d                              │
│  └─ Benefits:                                                       │
│     ├─ No need to install Neo4j locally                            │
│     ├─ Reproducible environment                                    │
│     └─ Easy to reset (docker-compose down)                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│              TIER 5: APPLICATION CODE (Your Python)                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Pipeline Scripts (Sequential Execution)                           │
│  ├─ 1_generate_data.py             [Data generation]              │
│  ├─ 2_data_to_knowledge_graph.py   [ETL to Neo4j]                │
│  ├─ 3_match_team.py                [Matching engine]              │
│  ├─ 4_naive_rag_cv.py              [Vector baseline]              │
│  ├─ 5_compare_systems.py           [Evaluation]                   │
│  └─ 6_business_intelligence.py     [Query engine] (NEW)           │
│                                                                      │
│  Future Components (To Build)                                      │
│  ├─ 7_chatbot_streamlit.py         [UI/Frontend]                  │
│  ├─ 8_what_if_scenarios.py         [Simulation]                   │
│  └─ api/main.py                    [REST API]                     │
│                                                                      │
│  Utilities & Configuration                                         │
│  ├─ utils/config.toml              [Settings]                     │
│  ├─ test_setup.py                  [Diagnostics]                  │
│  ├─ .env                           [Secrets]                      │
│  └─ requirements.txt               [Dependencies]                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Dependencies Tree (How Components Use Each Other)

```
File 1: 1_generate_data.py
├─ Imports: Faker, ReportLab, Azure OpenAI
├─ Output: PDF CVs + RFPs
└─ Dependencies: None (generates from scratch)

File 2: 2_data_to_knowledge_graph.py
├─ Imports: PyPDFLoader, LLMGraphTransformer, Neo4j, Azure OpenAI
├─ Input: CVs from File 1
├─ Output: Neo4j graph
└─ Dependencies: File 1 outputs, Docker Neo4j running

File 3: 3_match_team.py
├─ Imports: PyPDFLoader, Neo4j, Azure OpenAI
├─ Input: RFPs from File 1, Neo4j graph from File 2
├─ Output: Team assignments
└─ Dependencies: Files 1 & 2, Docker Neo4j running

File 4: 4_naive_rag_cv.py
├─ Imports: PyPDFLoader, ChromaDB, Azure OpenAI Embeddings
├─ Input: CVs from File 1
├─ Output: Vector embeddings in ChromaDB
└─ Dependencies: File 1 outputs

File 5: 5_compare_systems.py
├─ Imports: File 3 (TeamMatcher), File 4 (NaiveRAGSystem)
├─ Input: Test queries
├─ Output: Comparison metrics
└─ Dependencies: Files 1, 2, 3, 4 all completed

File 6: 6_business_intelligence.py
├─ Imports: Neo4j, Azure OpenAI
├─ Input: Natural language questions
├─ Output: Structured answers
└─ Dependencies: File 2 (Neo4j graph), Docker Neo4j running
```

---

## 🔌 Technology Usage by File

| File                         | Azure OpenAI | Neo4j | LangChain | ChromaDB | ReportLab | Docker |
| ---------------------------- | :----------: | :---: | :-------: | :------: | :-------: | :----: |
| 1_generate_data.py           |      ✅      |  ❌   |    ✅     |    ❌    |    ✅     |   ❌   |
| 2_data_to_knowledge_graph.py |      ✅      |  ✅   |    ✅     |    ❌    |    ❌     |   ✅   |
| 3_match_team.py              |      ✅      |  ✅   |    ✅     |    ❌    |    ❌     |   ✅   |
| 4_naive_rag_cv.py            |      ✅      |  ❌   |    ✅     |    ✅    |    ❌     |   ❌   |
| 5_compare_systems.py         |      ❌      |  ✅   |    ❌     |    ✅    |    ❌     |   ✅   |
| 6_business_intelligence.py   |      ✅      |  ✅   |    ✅     |    ❌    |    ❌     |   ✅   |

---

## 🎯 Technology Roles & Impact

### **Azure OpenAI** 🤖

- **Role:** Intelligence layer (understanding & generation)
- **Cost:** Major (per token)
- **Impact:** Without it:
  - Can't generate realistic CVs
  - Can't extract entities from PDFs
  - Can't classify queries
  - Can't analyze RFPs
- **Mitigation:** Consider mock LLM for testing

### **Neo4j** 🗄️

- **Role:** Knowledge storage & query engine
- **Cost:** Free (open source)
- **Impact:** Without it:
  - No GraphRAG (the core innovation!)
  - Can't do relationship reasoning
  - Can't do complex filtering
  - Would fall back to traditional RAG

### **LangChain** 🔗

- **Role:** Integration framework (glue between components)
- **Cost:** Free
- **Impact:** Without it:
  - Would need to write LLM integrations manually
  - No document loading abstractions
  - Much more boilerplate code
  - Higher complexity

### **ChromaDB** 📊

- **Role:** Vector database (for baseline comparison)
- **Cost:** Free
- **Impact:** Without it:
  - Can't compare to traditional RAG
  - Can't prove GraphRAG superiority
  - Missing evaluation evidence

### **Docker** 🐳

- **Role:** Environment isolation & reproducibility
- **Cost:** Free
- **Impact:** Without it:
  - Neo4j harder to set up
  - Different machines have different configs
  - Harder to reset/clean state

---

## 🔄 Data Flow Through Technologies

```
User wants to know: "How many Python developers are available?"

Step 1: RECEIVE QUESTION
  User Input → String

Step 2: CLASSIFY (File 6)
  String → Azure OpenAI LLM
  ↓
  "This is a COUNTING query"

Step 3: GENERATE QUERY (File 6)
  Handler selects Cypher template
  ↓
  MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
  WHERE toLower(s.id) = 'python'
  RETURN count(p)

Step 4: EXECUTE (File 6)
  Cypher → LangChain Neo4jGraph
  ↓
  Neo4j (Docker container)
  ↓
  Graph traversal + count

Step 5: RETURN RESULT
  Neo4j result → Application
  ↓
  Format with LangChain
  ↓
  "14 Python developers are available"

Step 6: COMPARE (File 4)
  Same question → Traditional RAG (ChromaDB)
  ↓
  Vector search → Text chunks containing "Python"
  ↓
  "Found Python mentioned in 8 CVs" (imprecise)

CONCLUSION: GraphRAG (14) > Naive RAG (8 mentions)
```

---

## 💰 Cost Analysis

| Component        | Type        | Cost                     |
| ---------------- | ----------- | ------------------------ |
| Azure OpenAI API | Usage-based | ~$0.01-0.50/query        |
| Neo4j            | Open source | Free                     |
| LangChain        | Open source | Free                     |
| ChromaDB         | Open source | Free                     |
| Docker Desktop   | Free tier   | Free                     |
| Python libraries | Open source | Free                     |
| **Total**        |             | **Minimal (Azure only)** |

---

## ⚡ Performance Characteristics

| Technology   | Latency         | Throughput         | Scalability       |
| ------------ | --------------- | ------------------ | ----------------- |
| Azure OpenAI | 500ms-2s        | 1-10 req/min       | Limited by quota  |
| Neo4j        | 10-100ms        | 100-1000 query/sec | 500+ nodes easily |
| ChromaDB     | 50-200ms        | 10-100 search/sec  | Good              |
| Docker       | Instant startup | N/A                | Good              |

---

## 🔐 Security & Configuration

### **Secrets (in .env)**

```
AZURE_OPENAI_API_KEY      [Secret] - Never commit
AZURE_OPENAI_ENDPOINT     [Semi-secret]
NEO4J_PASSWORD            [Secret] - Default: password123
NEO4J_USERNAME            [Semi-secret] - Default: neo4j
```

### **Best Practices**

- ✅ Use `.env` for secrets
- ✅ Add `.env` to `.gitignore`
- ✅ Use `.env.example` for template
- ✅ Rotate API keys regularly
- ✅ Use least-privilege for DB users

---

## 🚀 How to Run the Complete Stack

```bash
# 1. Setup
python -m venv venv
source venv/bin/activate        # Mac/Linux
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your Azure credentials

# 3. Start Database
docker-compose up -d

# 4. Run Pipeline
python 1_generate_data.py               # 2-3 min
python 2_data_to_knowledge_graph.py    # 5-10 min (API calls)
python 3_match_team.py                  # 1-2 min
python 4_naive_rag_cv.py                # 1 min
python 5_compare_systems.py             # 1 min

# 5. Query
python 6_business_intelligence.py       # Interactive queries

# 6. Cleanup
docker-compose down
```

**Total Runtime:** ~15-20 minutes (depending on Azure API speed)

---

Generated: 2025-12-31
