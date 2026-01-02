# TalentMatch AI – GraphRAG Staffing Engine

Capstone project for Generative Technologies. This repository contains the end-to-end GraphRAG pipeline for staffing: synthetic CV/RFP generation, Neo4j graph build, team matching, and Naive RAG baseline comparison. Business requirements are defined in [PRD](PRD.md) and [PROJECT_INSTRUCTIONS](PROJECT_INSTRUCTIONS.md).

## Repository contents

- Data and graph: [1_generate_data.py](1_generate_data.py), [2_data_to_knowledge_graph.py](2_data_to_knowledge_graph.py)
- Matching and availability: [3_match_team.py](3_match_team.py)
- Baseline and comparisons: [4_naive_rag_cv.py](4_naive_rag_cv.py), [5_compare_systems.py](5_compare_systems.py)
- Business intelligence: [6_business_intelligence.py](6_business_intelligence.py)
- User interface: [7_chatbot_streamlit.py](7_chatbot_streamlit.py)
- Infrastructure: [docker-compose.yml](docker-compose.yml), [utils](utils/), [data](data/), [requirements.txt](requirements.txt)
- Product docs: [PRD.md](PRD.md), [PROJECT_INSTRUCTIONS.md](PROJECT_INSTRUCTIONS.md)
- Guides: [ARCHITECTURE_GUIDE.md](ARCHITECTURE_GUIDE.md), [TECHNOLOGY_STACK.md](TECHNOLOGY_STACK.md), [QUICK_START.md](QUICK_START.md), [PROJECT_STATUS.md](PROJECT_STATUS.md)

## Prerequisites

- Python 3.11+ (recommended)
- Docker Desktop (Neo4j)
- OpenAI or Azure OpenAI key for LLM/embeddings

## Setup and run

1. Create and activate a virtual environment:

```bash
python -m venv venv
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

8. Business intelligence (optional):

```bash
python 6_business_intelligence.py    # test query engine with sample questions
```

9. Launch chatbot UI:

```bash
streamlit run 7_chatbot_streamlit.py # interactive chatbot interface at http://localhost:8501
```

10. Stop Neo4j:

```bash
docker-compose down
```

## Notes and tips

- Neo4j UI: http://localhost:7474 (credentials in docker-compose or utils).
- Streamlit chatbot: http://localhost:8501 (after running step 9).
- Outputs (graph artifacts, comparisons) are stored under [data](data/).
- Quick environment check: `python test_setup.py`.
- For detailed system architecture, see [ARCHITECTURE_GUIDE.md](ARCHITECTURE_GUIDE.md).
- For quick project overview, see [QUICK_START.md](QUICK_START.md).
- For Grade A roadmap, see [PROJECT_STATUS.md](PROJECT_STATUS.md).
