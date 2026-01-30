"""
Schema initialization for TalentMatch-AI (PRD 4.3)
- Creates id uniqueness constraints for core entities
- Adds helpful indexes for lookups
- Safe to run multiple times (IF NOT EXISTS)
"""
import os
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")


CONSTRAINTS = [
    "CREATE CONSTRAINT person_id_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT skill_id_unique IF NOT EXISTS FOR (s:Skill) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT company_id_unique IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT rfp_id_unique IF NOT EXISTS FOR (r:RFP) REQUIRE r.id IS UNIQUE",
    "CREATE CONSTRAINT university_id_unique IF NOT EXISTS FOR (u:University) REQUIRE u.id IS UNIQUE",
    "CREATE CONSTRAINT cert_id_unique IF NOT EXISTS FOR (c:Certification) REQUIRE c.id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX person_name_idx IF NOT EXISTS FOR (p:Person) ON (p.name)",
    "CREATE INDEX skill_id_idx IF NOT EXISTS FOR (s:Skill) ON (s.id)",
    "CREATE INDEX project_status_idx IF NOT EXISTS FOR (p:Project) ON (p.status)",
    "CREATE INDEX project_end_date_idx IF NOT EXISTS FOR (p:Project) ON (p.end_date)",
    "CREATE INDEX assigned_to_end_date_idx IF NOT EXISTS FOR ()-[r:ASSIGNED_TO]-() ON (r.end_date)",
]


def ensure_schema() -> None:
    print("🔧 Ensuring Neo4j schema (constraints & indexes)...")
    try:
        graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)
    except Exception as exc:  # pragma: no cover - network
        print(f"❌ Could not connect to Neo4j: {exc}")
        return

    for stmt in CONSTRAINTS + INDEXES:
        try:
            graph.query(stmt)
            print(f"✅ Applied: {stmt}")
        except Exception as exc:  # pragma: no cover - Neo4j version differences
            print(f"⚠️ Skipped '{stmt}': {exc}")

    print("🏁 Schema check complete. Safe to rerun anytime.")


if __name__ == "__main__":
    ensure_schema()
