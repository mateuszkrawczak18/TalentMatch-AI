# TalentMatch AI – GraphRAG Staffing Engine

Capstone project for Generative Technologies. This repository contains the end-to-end GraphRAG pipeline for staffing: synthetic CV/RFP generation, Neo4j graph build, team matching, and Naive RAG baseline comparison. Business requirements are defined in [PRD](PRD.md) and [PROJECT_INSTRUCTIONS](PROJECT_INSTRUCTIONS.md).

## Repository contents
- Data and graph: [1_generate_data.py](1_generate_data.py), [2_data_to_knowledge_graph.py](2_data_to_knowledge_graph.py)
- Matching and availability: [3_match_team.py](3_match_team.py)
- Baseline and comparisons: [4_naive_rag_cv.py](4_naive_rag_cv.py), [5_compare_systems.py](5_compare_systems.py)
- Infrastructure: [docker-compose.yml](docker-compose.yml), [utils](utils/), [data](data/), [requirements.txt](requirements.txt)
- Product docs: [PRD.md](PRD.md), [PROJECT_INSTRUCTIONS.md](PROJECT_INSTRUCTIONS.md)

## Prerequisites
- Python 3.11+ (recommended)
- Docker Desktop (Neo4j)
- OpenAI or Azure OpenAI key for LLM/embeddings

## Setup and run
1) Create and activate a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate   # Windows
source venv/bin/activate # Mac/Linux
```

2) Install dependencies:
```bash
pip install -r requirements.txt
```

3) Set environment variables in `.env`:
```bash
OPENAI_API_KEY=your_api_key_here
```
If using Azure OpenAI, add endpoint/deployment variables as expected by `utils/config`.

4) Start Neo4j (from the Project directory):
```bash
docker-compose up -d
```

5) Data and graph pipeline:
```bash
python 1_generate_data.py            # generate synthetic CVs/RFPs
python 2_data_to_knowledge_graph.py  # ETL into Neo4j
```

6) Team matching and queries:
```bash
python 3_match_team.py               # scoring: skills + experience + availability
```

7) Baseline and comparison:
```bash
python 4_naive_rag_cv.py             # vector baseline
python 5_compare_systems.py          # GraphRAG vs Naive RAG
```

8) Stop Neo4j:
```bash
docker-compose down
```

## Notes and tips
- Neo4j UI: http://localhost:7474 (credentials in docker-compose or utils).
- Outputs (graph artifacts, comparisons) are stored under [data](data/).
- Quick environment check: `python test_setup.py`.
- Extend the TalentMatch AI implementation per PRD/PROJECT_INSTRUCTIONS (e.g., RFP parser, availability, business queries) in `src/` as needed.

