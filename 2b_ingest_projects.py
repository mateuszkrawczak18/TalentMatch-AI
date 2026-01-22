import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph

load_dotenv()

# -----------------------
# CONFIG
# -----------------------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

# Demo load profile:
# - some fully busy (allocation=1.0)
# - some partially busy (allocation=0.5)
TARGET_FULLY_BUSY = 6
TARGET_PARTIAL_BUSY = 4  # together: 10 "not on bench" but only some truly unavailable

PROJECTS_DATA = [
    {"name": "Legacy System Migration", "end_days": 120, "description": "Refactor mainframe stack to cloud."},
    {"name": "Cybersecurity Audit", "end_days": 30, "description": "Security controls and pen-testing."},
    {"name": "Mobile App Refresh", "end_days": 180, "description": "UX overhaul for mobile clients."},
    {"name": "HR Portal Update", "end_days": 60, "description": "New onboarding flows & SSO."},
    {"name": "Cloud Infrastructure Setup", "end_days": 90, "description": "Greenfield AWS landing zone."},
]

def ingest_projects():
    print("🚀 Starting Project Simulation (Ongoing projects + Busy/Partial load)...")

    try:
        graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return

    # ==========================================
    # 1) CLEAN RESET (projects + assignments)
    # NOTE: This resets ALL projects/assignments.
    # Run this before RFP matcher if you want a clean base.
    # ==========================================
    print("🧹 [1/4] Cleaning ALL old assignments and projects...")
    graph.query("MATCH (:Person)-[r:ASSIGNED_TO]->() DELETE r")
    graph.query("MATCH (p:Project) DETACH DELETE p")

    # ==========================================
    # 2) CREATE ONGOING PROJECTS (with date end_date)
    # ==========================================
    print("🏗️  [2/4] Creating ONGOING projects...")

    for p in PROJECTS_DATA:
        start_date = datetime.now().date().isoformat()
        end_date = (datetime.now() + timedelta(days=p["end_days"])).date().isoformat()
        budget = random.randint(50000, 250000)
        graph.query(
            """
            MERGE (proj:Project {id: $id})
            SET proj.title = $title,
                proj.name = coalesce(proj.name, $title),
                proj.description = $description,
                proj.status = 'Active',
                proj.start_date = date($start_date),
                proj.end_date = date($end_date),
                proj.budget = $budget
            """,
            params={
                "id": p["name"],
                "title": p["name"],
                "description": p.get("description"),
                "start_date": start_date,
                "end_date": end_date,
                "budget": budget,
            },
        )

    # ==========================================
    # 3) LOAD PEOPLE
    # ==========================================
    people_result = graph.query("MATCH (p:Person) RETURN p.name as name ORDER BY p.name")
    all_people = [r["name"] for r in people_result]

    if not all_people:
        print("❌ No people found! Run '2_data_to_knowledge_graph.py' first.")
        return

    total_people = len(all_people)
    print(f"👥 Found {total_people} people in graph.")

    # Ensure we do not exceed available people
    target_total_assigned = min(TARGET_FULLY_BUSY + TARGET_PARTIAL_BUSY, total_people)
    fully_busy_count = min(TARGET_FULLY_BUSY, target_total_assigned)
    partial_busy_count = min(TARGET_PARTIAL_BUSY, target_total_assigned - fully_busy_count)

    print(f"🎯 [3/4] Assigning load profile:")
    print(f"   - Fully busy (allocation=1.0): {fully_busy_count}")
    print(f"   - Partially busy (allocation=0.5): {partial_busy_count}")
    print(f"   - Bench (allocation=0.0): {total_people - (fully_busy_count + partial_busy_count)}")

    # Randomize selection
    random.shuffle(all_people)
    fully_busy_people = all_people[:fully_busy_count]
    partial_busy_people = all_people[fully_busy_count : fully_busy_count + partial_busy_count]
    bench_people = all_people[fully_busy_count + partial_busy_count :]

    # ==========================================
    # 4) ASSIGNMENTS (ASSIGNED_TO end_date as date)
    # ==========================================
    print("🧩 [4/4] Creating assignments...")

    def assign_person(person_name: str, allocation: float):
        project_def = random.choice(PROJECTS_DATA)

        graph.query(
            """
            MATCH (p:Person {name: $person})
            MATCH (proj:Project {id: $project_name})
            MERGE (p)-[r:ASSIGNED_TO]->(proj)
            SET r.allocation = $allocation,  // legacy
                r.allocation_percentage = $allocation,
                r.role = 'Developer',
                r.assigned_at = date(),
                r.start_date = date(),
                r.end_date = proj.end_date
            """,
            params={
                "person": person_name,
                "project_name": project_def["name"],
                "allocation": allocation,
            },
        )

    for person in fully_busy_people:
        assign_person(person, 1.0)

    for person in partial_busy_people:
        assign_person(person, 0.5)

    # ==========================================
    # SUMMARY
    # ==========================================
    print("\n✅ Simulation Complete.")
    print(f"📊 Final Stats:")
    print(f"   - Total Staff: {total_people}")
    print(f"   - Fully busy (1.0): {len(fully_busy_people)}")
    print(f"   - Partially busy (0.5): {len(partial_busy_people)}")
    print(f"   - Bench (0.0): {len(bench_people)}")

    print("\n🔎 Quick sanity queries you can run in Neo4j Browser:")
    print("1) People load distribution:")
    print("""
MATCH (p:Person)
OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
WITH p, sum(coalesce(r.allocation,0.0)) as load
RETURN
  sum(CASE WHEN load = 0.0 THEN 1 ELSE 0 END) as bench,
  sum(CASE WHEN load > 0.0 AND load < 1.0 THEN 1 ELSE 0 END) as partial,
  sum(CASE WHEN load >= 1.0 THEN 1 ELSE 0 END) as busy
""")
    print("2) Upcoming availability (based on r.end_date):")
    print("""
MATCH (p:Person)-[r:ASSIGNED_TO]->(proj:Project)
RETURN p.name, proj.name, r.allocation, r.end_date
ORDER BY r.end_date ASC
LIMIT 20
""")

if __name__ == "__main__":
    ingest_projects()