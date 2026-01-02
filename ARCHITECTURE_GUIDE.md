# TalentMatch AI - Complete Project Architecture & Technologies Guide

## 🏗️ Project Overview

**TalentMatch AI** is an enterprise staffing intelligence system that uses **GraphRAG** (Graph-based Retrieval Augmented Generation) to intelligently match programmers to projects. It demonstrates how graph-based AI is superior to traditional vector-based RAG for structured business queries.

---

## 📊 Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INPUT SOURCES                               │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   PDF CVs (30)   │  │   PDF RFPs (3)   │  │ Project Assign.  │  │
│  │  (Unstructured)  │  │  (Unstructured)  │  │    (YAML/JSON)   │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
└───────────┼────────────────────┼───────────────────┼──────────────┘
            │                    │                   │
            ▼                    ▼                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PROCESSING ENGINES                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FILE 1: 1_generate_data.py - DATA GENERATION               │   │
│  │  ✓ Synthetic CV generation using LLM                        │   │
│  │  ✓ RFP document creation                                    │   │
│  │  Output: 30 PDF CVs + 3 PDF RFPs                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FILE 2: 2_data_to_knowledge_graph.py - ETL PIPELINE        │   │
│  │  ✓ PDF parsing (PyPDFLoader)                                │   │
│  │  ✓ Entity extraction using LLM (LLMGraphTransformer)        │   │
│  │  ✓ Relationship creation                                    │   │
│  │  Output: Neo4j Knowledge Graph (Nodes + Relationships)      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FILE 3: 3_match_team.py - INTELLIGENT MATCHING ENGINE      │   │
│  │  ✓ RFP parsing & requirement extraction                     │   │
│  │  ✓ Multi-factor scoring algorithm                           │   │
│  │  ✓ Real-time availability calculation                       │   │
│  │  Output: Ranked candidate recommendations + assignments     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FILE 4: 4_naive_rag_cv.py - TRADITIONAL RAG (BASELINE)     │   │
│  │  ✓ Vector embeddings (ChromaDB)                             │   │
│  │  ✓ Semantic search                                          │   │
│  │  Output: Text similarity-based results                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FILE 5: 5_compare_systems.py - EVALUATION & COMPARISON     │   │
│  │  ✓ Run both systems on same queries                         │   │
│  │  ✓ Compare accuracy & performance                           │   │
│  │  Output: Comparison metrics & analysis                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FILE 6: 6_business_intelligence.py - QUERY ENGINE (NEW)    │   │
│  │  ✓ 6 query types (Counting, Filtering, Aggregation, etc)   │   │
│  │  ✓ Cypher query generation & execution                      │   │
│  │  Output: Natural language answers to complex questions       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DATABASE & STORAGE LAYER                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Neo4j Graph Database (Docker)                              │   │
│  │  ✓ Nodes: Person, Skill, Project, Company, Location        │   │
│  │  ✓ Relationships: HAS_SKILL, ASSIGNED_TO, WORKED_AT, etc   │   │
│  │  ✓ Port: 7474 (Browser), 7687 (Bolt protocol)              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  ChromaDB (Vector Store)                                    │   │
│  │  ✓ Stores vector embeddings of CV documents                │   │
│  │  ✓ For Naive RAG baseline comparison                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  File System                                                │   │
│  │  ✓ data/cvs/ - Generated CV PDFs                           │   │
│  │  ✓ data/rfps/ - Generated RFP PDFs                         │   │
│  │  ✓ neo4j_data/ - Neo4j persistent volume                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📁 File-by-File Breakdown

### **FILE 1: 1_generate_data.py** 🔨

**Purpose:** Generate realistic synthetic data to avoid using real employee data

| Aspect           | Details                                                                       |
| ---------------- | ----------------------------------------------------------------------------- |
| **What it does** | Creates 30 fake CVs and 3 RFP documents with plausible content                |
| **Key Classes**  | `GraphRAGDataGenerator`                                                       |
| **Technologies** | Faker (fake names), Azure OpenAI LLM, ReportLab (PDF generation)              |
| **Input**        | Configuration in `utils/config.toml`                                          |
| **Output**       | PDF files in `data/cvs/` and `data/rfps/`                                     |
| **Dependencies** | Faker, reportlab, langchain_openai                                            |
| **How it fits**  | **Step 1 of pipeline** - Creates realistic test data without privacy concerns |

**Key Methods:**

- `generate_cv_content()` - Uses LLM to write realistic CV text for fake developer
- `create_professional_pdf()` - Formats CV content into professional PDF
- `generate_rfps()` - Creates 3 sample project RFPs
- `generate_all_data()` - Orchestrates entire generation process

**Technology Stack Used:**

```
🤖 Azure OpenAI LLM
    ↓ (generates CV content)
📝 ReportLab
    ↓ (formats as PDF)
📄 PDF Files (output)
```

---

### **FILE 2: 2_data_to_knowledge_graph.py** 🧠

**Purpose:** Transform unstructured PDF data into a queryable knowledge graph

| Aspect           | Details                                                                         |
| ---------------- | ------------------------------------------------------------------------------- |
| **What it does** | Reads PDFs, extracts entities/relationships, builds Neo4j graph                 |
| **Key Classes**  | None (functional approach with Neo4jGraph)                                      |
| **Technologies** | PyPDFLoader, LLMGraphTransformer, Neo4j, Azure OpenAI                           |
| **Input**        | PDF files from `data/cvs/`                                                      |
| **Output**       | Neo4j graph with nodes (Person, Skill, Company, etc)                            |
| **Dependencies** | langchain_community, langchain_neo4j, langchain_experimental                    |
| **How it fits**  | **Step 2 of pipeline** - Core GraphRAG engine that creates structured knowledge |

**Key Steps:**

1. **Connect to Neo4j** - Establish database connection
2. **Clear old data** - `MATCH (n) DETACH DELETE n` (fresh start)
3. **Initialize LLM** - Azure OpenAI for entity extraction
4. **Configure Transformer** - LLMGraphTransformer with allowed node types:
   - Person, Skill, Location, Company, University, Role
5. **Batch processing** - Process 5 pages at a time
6. **Store in Neo4j** - `graph.add_graph_documents()`

**Example Entity Extraction:**

```
Text: "John works as Python developer at Acme Inc in NYC"
        ↓ LLM processes
Entities:
  - Person(id="John")
  - Skill(id="Python")
  - Company(id="Acme Inc")
  - Location(id="NYC")
Relationships:
  - John -[:HAS_SKILL]-> Python
  - John -[:WORKED_AT]-> Acme Inc
  - John -[:LOCATED_IN]-> NYC
```

**Technology Stack Used:**

```
📄 PDF Files
    ↓ (PyPDFLoader)
📝 Text Content
    ↓ (LLMGraphTransformer + Azure OpenAI)
🧠 Entities & Relationships
    ↓ (graph.add_graph_documents)
🗄️ Neo4j Database
```

**Graph Schema Created:**

```
NODES:
- Person {id, name, location}
- Skill {id, category}
- Company {id, name}
- Location {id, name}
- University {id, name}
- Project {id, name, required_skills}

RELATIONSHIPS:
- HAS_SKILL (Person -> Skill)
- WORKED_AT (Person -> Company)
- LOCATED_IN (Person/Company -> Location)
- STUDIED_AT (Person -> University)
- ASSIGNED_TO (Person -> Project)
```

---

### **FILE 3: 3_match_team.py** 👥

**Purpose:** Intelligently match developers to projects using multi-factor scoring

| Aspect           | Details                                                     |
| ---------------- | ----------------------------------------------------------- |
| **What it does** | Analyzes RFP requirements, scores developers, assigns teams |
| **Key Classes**  | `TeamMatcher`                                               |
| **Technologies** | PyPDFLoader, Azure OpenAI LLM, Neo4j (Cypher queries)       |
| **Input**        | PDF RFPs from `data/rfps/` + Neo4j graph                    |
| **Output**       | Team assignments + scored candidates                        |
| **Dependencies** | langchain_community, langchain_neo4j, langchain_openai      |
| **How it fits**  | **Step 3 of pipeline** - Business logic: matching algorithm |

**Key Methods:**

1. `analyze_rfp()` - Extracts requirements from RFP PDF using LLM

   - Required skills
   - Team size
   - Location preference
   - Budget/allocation

2. `find_and_assign_team()` - Two-stage matching algorithm:

   - **STAGE 1 (Strict Match):** Skills + Location + Availability
   - **STAGE 2 (Fallback):** Just availability (for gaps)
   - Scoring: `(skill_count × 10) + location_score + (availability × 20)`

3. `create_project_node()` - Creates Project node in Neo4j

**Matching Algorithm:**

```
Input: RFP with required skills [Python, AWS], team_size=5, location="NYC"

STAGE 1 - STRICT MATCH:
MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
WHERE s.id IN ['python', 'aws']
  AND (p)-[:LOCATED_IN]->(loc)
  AND loc.id CONTAINS 'NYC'
  AND (availability < 100%)
→ Returns: [Dev1(score=85), Dev2(score=72), Dev3(score=68)]

STAGE 2 - FALLBACK (if < 5 found):
MATCH (p:Person)  # No skills filter
WHERE (availability < 100%)
→ Returns: [Dev4(score=10), Dev5(score=10)]

OUTPUT:
✓ Dev1, Dev2, Dev3 (matched on skills)
✓ Dev4, Dev5 (filled gaps)
Assigned: Dev1 -[:ASSIGNED_TO]-> Project1
```

**Technology Stack Used:**

```
📄 RFP PDF
    ↓ (PyPDFLoader + Azure LLM)
📋 Extracted Requirements
    ↓ (Cypher Queries)
🗄️ Neo4j Graph
    ↓ (Scoring Algorithm)
👥 Ranked Candidates
    ↓ (ASSIGNED_TO relationships)
✅ Final Team Assignment
```

---

### **FILE 4: 4_naive_rag_cv.py** 📚

**Purpose:** Implement traditional vector-based RAG as a baseline comparison

| Aspect           | Details                                                               |
| ---------------- | --------------------------------------------------------------------- |
| **What it does** | Embeds CV text, creates vector search, answers questions semantically |
| **Key Classes**  | `NaiveRAGSystem`                                                      |
| **Technologies** | ChromaDB, Azure OpenAI Embeddings, RecursiveCharacterTextSplitter     |
| **Input**        | PDF CVs from `data/cvs/`                                              |
| **Output**       | Text results from semantic similarity search                          |
| **Dependencies** | langchain_chroma, langchain_openai, chromadb                          |
| **How it fits**  | **Alternative approach** - Demonstrates RAG limitations vs GraphRAG   |

**How it Works:**

```
Step 1: LOAD PDFs
  ↓
Step 2: CHUNK TEXT (RecursiveCharacterTextSplitter)
  PDF text → chunks of ~500 chars
  ↓
Step 3: CREATE EMBEDDINGS (Azure OpenAI)
  Text chunk → 1536-dim vector
  ↓
Step 4: STORE IN CHROMADB
  Vector index (in-memory or disk)
  ↓
Step 5: QUERY
  Question → embedding → cosine similarity search
  → Top-K most similar chunks returned
```

**Limitations (why GraphRAG is better):**

```
Traditional RAG Problem:
Q: "How many Python developers are available?"
A: Returns text chunks mentioning "Python" and "available"
   But can't COUNT or aggregate properly
   (No understanding of structure)

GraphRAG Solution:
Q: Same question
A: Uses Cypher: MATCH (p)-[:HAS_SKILL]->(s:Skill)
                WHERE s.id='Python'
                RETURN count(p)
   Returns: 14 (precise answer)
```

**Technology Stack Used:**

```
📄 PDF Files
    ↓ (PyPDFLoader + TextSplitter)
📝 Text Chunks
    ↓ (Azure OpenAI Embeddings)
🧮 Vector Embeddings
    ↓ (ChromaDB)
🔍 Vector Index
    ↓ (Similarity Search)
📋 Top-K Similar Texts
```

---

### **FILE 5: 5_compare_systems.py** ⚖️

**Purpose:** Compare GraphRAG vs Naive RAG on same queries

| Aspect           | Details                                                         |
| ---------------- | --------------------------------------------------------------- |
| **What it does** | Runs both systems, measures accuracy/speed, reports differences |
| **Key Classes**  | None (orchestration script)                                     |
| **Technologies** | Dynamic imports, time measurement, results analysis             |
| **Input**        | Both systems initialized + test queries                         |
| **Output**       | Comparison metrics (accuracy, latency, correctness)             |
| **Dependencies** | 3_match_team.py, 4_naive_rag_cv.py                              |
| **How it fits**  | **Evaluation step** - Proves GraphRAG superiority               |

**What it Compares:**

```
Query Type: COUNTING
Q: "How many Python developers are available?"

GraphRAG:
- Time: 150ms
- Result: 14 (precise count)
- Accuracy: 100%

Naive RAG:
- Time: 200ms
- Result: "Found mentions of Python in 8 CVs" (text match)
- Accuracy: 50% (not actual count)
```

**Comparison Dimensions:**

- **Accuracy** - Correct vs incorrect answers
- **Latency** - Response time comparison
- **Query Complexity** - Simple vs complex (GraphRAG excels at complex)
- **Explainability** - Can show the Cypher query used

**Technology Stack Used:**

```
🏃 Run GraphRAG (3_match_team.py)
    ↓ measure time
💾 Store Results
    ↓
🏃 Run Naive RAG (4_naive_rag_cv.py)
    ↓ measure time
💾 Store Results
    ↓
📊 Compare & Report
```

---

### **FILE 6: 6_business_intelligence.py** 🤖 (NEW)

**Purpose:** Query engine for 6 types of complex business intelligence queries

| Aspect           | Details                                                                    |
| ---------------- | -------------------------------------------------------------------------- |
| **What it does** | Classifies questions, generates Cypher, executes in Neo4j, formats results |
| **Key Classes**  | `BusinessIntelligenceEngine`                                               |
| **Technologies** | Azure OpenAI (classification), Neo4j (Cypher), LangChain                   |
| **Input**        | Natural language questions                                                 |
| **Output**       | Structured answers with explanations                                       |
| **Dependencies** | langchain_neo4j, langchain_openai                                          |
| **How it fits**  | **Query interface** - Makes GraphRAG accessible via natural language       |

**6 Query Types Handled:**

```
1️⃣ COUNTING QUERIES
   "How many Python developers are available?"
   Cypher: MATCH (p)-[:HAS_SKILL]->(s:Skill {id:'python'})
           WHERE available RETURN count(p)

2️⃣ FILTERING QUERIES
   "Find developers with React experience"
   Cypher: MATCH (p)-[:HAS_SKILL]->(s:Skill {id:'react'})
           RETURN p.id, current_load

3️⃣ AGGREGATION QUERIES
   "What's average experience for ML developers?"
   Cypher: MATCH (p)-[:ASSIGNED_TO]->(:Project)
           WHERE 'ML' IN project_skills
           RETURN avg(p.experience)

4️⃣ REASONING QUERIES
   "Show developers who worked together"
   Cypher: MATCH (p1)-[:WORKED_AT]->(c)<-[:WORKED_AT]-(p2)
           WHERE p1 < p2
           RETURN p1, p2, c

5️⃣ TEMPORAL QUERIES
   "Who becomes available after their projects end?"
   Cypher: MATCH (p)-[r:ASSIGNED_TO]->(proj)
           RETURN p.id, proj.end_date

6️⃣ SCENARIO QUERIES
   "Optimal team for FinTech under budget?"
   Cypher: Complex multi-step reasoning with filters
```

**Architecture:**

```
Natural Language Input
    ↓
classify_query() [Azure LLM]
    ↓ (determines type)
Route to Handler
    ├─ handle_counting_query()
    ├─ handle_filtering_query()
    ├─ handle_aggregation_query()
    ├─ handle_reasoning_query()
    ├─ handle_temporal_query()
    └─ handle_scenario_query()
    ↓
Generate Cypher
    ↓
Execute in Neo4j
    ↓
Format Results
    ↓
Return Answer
```

**Technology Stack Used:**

```
🤖 Azure OpenAI (Query Classification)
    ↓
📋 Cypher Query Templates
    ↓
🗄️ Neo4j (Execution)
    ↓
📊 Result Formatting
    ↓
✅ Natural Language Answer
```

---

## 🛠️ Infrastructure & Configuration

### **docker-compose.yml**

Runs Neo4j in Docker container

```yaml
Services:
- neo4j:5.11.0
  Ports: 7474 (Browser), 7687 (Bolt protocol)
  Auth: neo4j/password123
  Volume: ./neo4j_data (persistent storage)
  Plugins: apoc (for graph algorithms)
```

### **requirements.txt**

Python dependencies organized by purpose:

```
Core: LangChain framework
Graph: Neo4j integration
Vector: ChromaDB for embeddings
PDF: PyPDF, reportlab for documents
LLM: Azure OpenAI API
Utils: Faker, python-dotenv, toml
```

### **.env File**

Credentials and configuration:

```
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=...
AZURE_DEPLOYMENT_NAME=gpt-5-nano
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password123
```

---

## 🔄 Complete Data Flow (End-to-End)

```
PHASE 1: DATA GENERATION
1_generate_data.py
  ↓ Creates: 30 synthetic CVs + 3 RFPs (PDFs)

PHASE 2: KNOWLEDGE GRAPH BUILDING
2_data_to_knowledge_graph.py
  ↓ Reads: PDFs
  ↓ Processes: LLMGraphTransformer (entity extraction)
  ↓ Stores: Neo4j (nodes + relationships)

PHASE 3: TEAM MATCHING
3_match_team.py
  ↓ Reads: RFP PDFs + Neo4j graph
  ↓ Analyzes: LLM extracts requirements
  ↓ Matches: Cypher queries with scoring
  ↓ Assigns: Creates ASSIGNED_TO relationships
  ↓ Output: Team recommendations

PHASE 4: BASELINE COMPARISON
4_naive_rag_cv.py
  ↓ Embeds: CV text into vectors (ChromaDB)
  ↓ Searches: Semantic similarity

5_compare_systems.py
  ↓ Compares: GraphRAG vs Naive RAG
  ↓ Reports: Accuracy, latency, quality

PHASE 5: BUSINESS INTELLIGENCE
6_business_intelligence.py
  ↓ Takes: Natural language questions
  ↓ Classifies: With Azure LLM
  ↓ Executes: Cypher queries in Neo4j
  ↓ Returns: Structured answers
```

---

## 🎯 Key Technologies & Their Roles

| Technology              | Purpose                         | How it fits                                          |
| ----------------------- | ------------------------------- | ---------------------------------------------------- |
| **Azure OpenAI LLM**    | Text generation & understanding | Generates CVs, extracts entities, classifies queries |
| **Neo4j**               | Graph database                  | Stores knowledge graph, executed Cypher queries      |
| **LangChain**           | AI orchestration framework      | Connects components, manages chains                  |
| **LLMGraphTransformer** | Entity extraction               | Core of GraphRAG (unstructured → structured)         |
| **ChromaDB**            | Vector database                 | Baseline RAG system for comparison                   |
| **PyPDFLoader**         | PDF parsing                     | Reads CV and RFP documents                           |
| **ReportLab**           | PDF generation                  | Creates synthetic CV documents                       |
| **Faker**               | Fake data generation            | Generates realistic names, etc                       |
| **Docker**              | Containerization                | Runs Neo4j consistently                              |
| **Python**              | Programming language            | Ties everything together                             |

---

## 💡 How Components Interact

```
User Question
    ↓
6_business_intelligence.py
    ├─ Classifies with Azure LLM
    └─ Routes to appropriate handler
    ↓
Handler (based on type)
    ├─ Generates Cypher query
    └─ Executes via LangChain Neo4jGraph
    ↓
Neo4j Database
    ├─ Traverses graph
    ├─ Applies filters
    └─ Returns results
    ↓
Business Intelligence Engine
    ├─ Formats results
    └─ Explains findings
    ↓
User Answer (precise, explainable, structured)
```

---

## 🚀 Project Value Proposition

**Problem:** Traditional RAG (vector search) can't handle:

- Counting ("How many Python devs?")
- Filtering with AND/OR conditions
- Aggregations (averages, sums)
- Multi-hop reasoning (who worked together?)
- Complex business logic

**Solution:** GraphRAG via Neo4j

- Exact counts and aggregations ✓
- Complex filtering ✓
- Relationship reasoning ✓
- Business intelligence queries ✓

**Proof:** Files 4 & 5 demonstrate GraphRAG > Traditional RAG

---

## 📚 File Dependencies & Execution Order

```
Prerequisite: docker-compose up -d  (start Neo4j)

1. 1_generate_data.py
   └─ Creates data/cvs/*.pdf, data/rfps/*.pdf

2. 2_data_to_knowledge_graph.py
   └─ Depends on: outputs from file 1
   └─ Creates: Neo4j graph

3. 3_match_team.py
   └─ Depends on: Neo4j graph from file 2
   └─ Creates: Project nodes + assignments

4. 4_naive_rag_cv.py
   └─ Depends on: data/cvs/*.pdf from file 1
   └─ Creates: Vector embeddings

5. 5_compare_systems.py
   └─ Depends on: files 3 & 4
   └─ Creates: Comparison report

6. 6_business_intelligence.py
   └─ Depends on: Neo4j graph from file 2
   └─ Standalone: Can run after graph is built
```

---

## ✨ What's Next (For Completion)

To make the project fully functional for production:

1. **7_chatbot_streamlit.py** - Create UI for BI engine
2. **8_what_if_scenarios.py** - Simulation engine
3. **API layer** - REST endpoints for integration
4. **Documentation** - User guides, API specs
5. **Testing suite** - Unit & integration tests

---

Generated: 2025-12-31
