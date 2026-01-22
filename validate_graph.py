import os
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph

load_dotenv()

graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
    username=os.getenv("NEO4J_USERNAME", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "password123"),
)

CHECKS = [
    ("People count > 0", "MATCH (p:Person) RETURN count(p) AS c", lambda r: r[0]["c"] > 0),
    ("Each person has >=1 skill", """
        MATCH (p:Person)
        WHERE NOT (p)-[:HAS_SKILL]->(:Skill)
        RETURN count(p) AS missing
    """, lambda r: r[0]["missing"] == 0),
    ("No duplicate Skill ids", """
        MATCH (s:Skill)
        WITH s.id AS id, count(*) AS c
        WHERE id IS NOT NULL AND c > 1
        RETURN count(*) AS dup
    """, lambda r: r[0]["dup"] == 0),
    ("Allocation never > 1.0", """
        MATCH (:Person)-[r:ASSIGNED_TO]->(:Project)
        WITH r, coalesce(r.allocation,0.0) AS a
        WHERE a > 1.0
        RETURN count(*) AS bad
    """, lambda r: r[0]["bad"] == 0),
    ("YearsExperience present for most", """
        MATCH (p:Person)
        RETURN
          sum(CASE WHEN p.years_of_experience IS NULL OR p.years_of_experience = 0 THEN 1 ELSE 0 END) AS missing,
          count(p) AS total
    """, lambda r: (r[0]["missing"] / max(r[0]["total"], 1)) < 0.5),
]

def main():
    print("🔎 Graph Validation")
    ok_all = True
    for name, cypher, rule in CHECKS:
        res = graph.query(cypher)
        ok = rule(res)
        print(("✅" if ok else "❌"), name, "|", res[0] if res else res)
        ok_all = ok_all and ok
    print("\nRESULT:", "PASS ✅" if ok_all else "FAIL ❌")
    raise SystemExit(0 if ok_all else 1)

if __name__ == "__main__":
    main()
