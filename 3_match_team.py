import os
import glob
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import AzureChatOpenAI
from langchain_neo4j import Neo4jGraph
from typing import List, Dict, Optional

load_dotenv()

class TeamMatcher:
    def __init__(self):
        self.graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password123")
        )

        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            max_retries=3,
            request_timeout=120
        )

    def extract_json_from_text(self, text: str) -> Dict:
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start == -1 or end == 0:
                return {}
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            print("⚠️ JSON Decode Error. Raw text:", text[:140] + "...")
            return {}
        except Exception as e:
            print(f"⚠️ Parser Error: {e}")
            return {}

    def _normalize_location(self, loc: Optional[str]) -> Optional[str]:
        if loc is None:
            return None
        s = str(loc).strip()
        if not s:
            return None
        # Normalizacje typowych śmieci z LLM
        bad = ["remote not allowed", "not allowed", "n/a", "unknown"]
        if s.lower() in bad:
            return None
        # bierzemy tylko miasto przed przecinkiem
        if "," in s:
            s = s.split(",")[0].strip()
        return s

    def reset_assignments(self):
        """
        SMART RESET:
        - usuwa tylko projekty NIE-ONGOING (czyli te z poprzednich RFP)
        - zachowuje projekty Ongoing + ich assignments (z 2b_ingest_projects.py)
        """
        print("🧹 Cleaning up previous RFP assignments (Preserving 'Ongoing' projects)...")
        try:
            # Usuń relacje ASSIGNED_TO tylko dla projektów, które NIE są Ongoing
            self.graph.query("""
                MATCH (:Person)-[r:ASSIGNED_TO]->(p:Project)
                WHERE coalesce(p.status,'') <> 'Ongoing'
                DELETE r
            """)

            # Usuń same projekty, które NIE są Ongoing
            self.graph.query("""
                MATCH (p:Project)
                WHERE coalesce(p.status,'') <> 'Ongoing'
                DETACH DELETE p
            """)

            print("✅ System ready. 'Ongoing' projects preserved.")
        except Exception as e:
            print(f"⚠️ Warning during reset: {e}")

    def analyze_rfp(self, pdf_path: str) -> Optional[Dict]:
        print(f"\n📄 Analyzing RFP: {os.path.basename(pdf_path)}...")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                loader = PyPDFLoader(pdf_path)
                pages = loader.load()
                content = "\n".join([p.page_content for p in pages])

                prompt = f"""
You are an expert IT Project Manager. Extract structured requirements from this RFP.

Output ONLY valid JSON in this format:
{{
    "rfp_title": "Name of RFP",
    "project_title": "Project title to execute the RFP",
    "description": "Short summary of the scope",
    "requirements": "One sentence of key requirements",
    "required_skills": ["Skill1", "Skill2"],
    "team_size": 5,
    "location": "City Name" (or null if remote allowed),
    "allocation_needed": 1.0,
    "duration_months": 3,
    "budget": 120000,
    "deadline": "2026-03-31"
}}

Rules:
- If allocation is not specified, assume 1.0 (Full Time).
- If duration is not specified, assume 3 months.
- If budget is missing, estimate a reasonable integer budget in USD.
- If deadline is missing, set deadline to today + 45 days (ISO date).
- For location: if RFP says Remote Not Allowed, return a City (not that phrase).
- required_skills must be a JSON array of strings (not a single string).

RFP Content:
{content[:4500]}
"""

                response = self.llm.invoke(prompt)
                data = self.extract_json_from_text(response.content)

                if not data:
                    print("⚠️ Empty JSON received from LLM.")
                    continue

                # Defaults / cleanup
                if not data.get("allocation_needed"):
                    data["allocation_needed"] = 1.0
                if not data.get("team_size"):
                    data["team_size"] = 5
                if not data.get("duration_months"):
                    data["duration_months"] = 3

                if not data.get("deadline"):
                    data["deadline"] = (datetime.utcnow().date() + timedelta(days=45)).isoformat()
                if not data.get("budget"):
                    data["budget"] = 120000

                if not data.get("project_title"):
                    data["project_title"] = data.get("rfp_title") or data.get("project_name") or "New Project"
                if not data.get("rfp_title"):
                    data["rfp_title"] = data.get("project_title")
                if not data.get("description"):
                    data["description"] = "RFP extracted project"
                if not data.get("requirements"):
                    data["requirements"] = ", ".join(data.get("required_skills", []))

                loc = self._normalize_location(data.get("location"))
                data["location"] = loc  # None oznacza remote allowed

                # Ensure list
                if isinstance(data.get("required_skills"), str):
                    # split by comma if needed
                    skills = [s.strip() for s in data["required_skills"].split(",") if s.strip()]
                    data["required_skills"] = skills

                return data

            except Exception as e:
                print(f"   ⚠️ Error processing RFP (Attempt {attempt+1}/{max_retries}): {e}")
                time.sleep(2)

        print("❌ Failed to analyze RFP after multiple attempts.")
        return None

    def create_rfp_and_project(self, reqs: Dict, rfp_id: str):
        """Creates RFP + Project nodes and connects REQUIRES/NEEDS relationships."""
        duration_months = int(reqs.get("duration_months", 3))
        start_date = datetime.utcnow().date().isoformat()
        computed_end = (datetime.utcnow().date() + timedelta(days=30 * duration_months)).isoformat()
        end_date = reqs.get("end_date") or reqs.get("deadline") or computed_end
        project_id = reqs.get("project_id") or f"{rfp_id}::proj"
        project_title = reqs.get("project_title") or reqs.get("project_name") or "Project"
        rfp_title = reqs.get("rfp_title") or project_title

        query = """
        MERGE (r:RFP {id: $rfp_id})
        SET r.title = $rfp_title,
            r.description = $description,
            r.requirements = $requirements,
            r.budget = $budget,
            r.deadline = CASE WHEN $deadline IS NULL THEN NULL ELSE date($deadline) END

        MERGE (p:Project {id: $project_id})
        SET p.title = $project_title,
            p.name = coalesce(p.name, $project_title),
            p.description = $description,
            p.status = 'New RFP',
            p.start_date = date($start_date),
            p.end_date = CASE WHEN $end_date IS NULL THEN NULL ELSE date($end_date) END,
            p.budget = $budget

        MERGE (r)-[:CREATES]->(p)
        """

        self.graph.query(
            query,
            {
                "rfp_id": rfp_id,
                "rfp_title": rfp_title,
                "description": reqs.get("description"),
                "requirements": reqs.get("requirements"),
                "budget": reqs.get("budget"),
                "deadline": reqs.get("deadline"),
                "project_id": project_id,
                "project_title": project_title,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        for skill in reqs.get("required_skills", []):
            self.graph.query(
                """
MERGE (s:Skill {id: $skill})
ON CREATE SET s.name = coalesce(s.name, $skill)
WITH s
MATCH (r:RFP {id: $rfp_id})
MATCH (p:Project {id: $project_id})
MERGE (r)-[n:NEEDS]->(s)
SET n.required_count = coalesce($required_count, 1),
    n.experience_level = coalesce($experience_level, 'Any')
MERGE (p)-[req:REQUIRES]->(s)
SET req.minimum_level = 1,
    req.preferred_level = 3
""",
                {
                    "skill": skill,
                    "rfp_id": rfp_id,
                    "project_id": project_id,
                    "required_count": reqs.get("team_size", 1),
                    "experience_level": "Any",
                },
            )

        print(
            f"🏗️  Created RFP '{rfp_title}' with Project '{project_title}' (duration {duration_months} months)"
        )

    def find_and_assign_team(self, reqs: Dict, project_ref: str, simulate_only: bool = False):
        skills = reqs.get("required_skills", [])
        team_size = int(reqs.get("team_size", 5))
        location = reqs.get("location")  # None => remote allowed
        allocation_needed = float(reqs.get("allocation_needed", 1.0))
        project_title = reqs.get("project_title") or reqs.get("project_name")

        print(f"   🔍 Looking for {team_size} people. Req. Allocation: {allocation_needed*100:.0f}%")
        if simulate_only:
            print("   🎭 SIMULATION MODE: No database writes will be performed")

        # ---------- STRICT MATCH ----------
        query_strict = """
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
        WHERE toLower(coalesce(s.id,s.name,'')) IN [skill IN $skills | toLower(skill)]

        OPTIONAL MATCH (p)-[:LOCATED_IN]->(l:Location)
        OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)

        WITH p, l,
             count(s) as skill_count,
             collect(coalesce(s.id,s.name)) as skills_found,
             sum(coalesce(r.allocation_percentage, coalesce(r.allocation, 0.0))) as current_load

        WHERE current_load + $needed_alloc <= 1.0

        WITH p, l, skills_found, current_load,
             CASE
                WHEN $location IS NULL THEN 10
                WHEN l IS NOT NULL AND toLower(l.name) CONTAINS toLower($location) THEN 50
                WHEN l IS NOT NULL AND toLower(l.name) CONTAINS 'remote' THEN 5
                ELSE 0
             END as loc_score,
             skill_count

        WITH p, l, skills_found, current_load,
             (skill_count * 10) + loc_score + ((1.0 - current_load) * 20) as final_score

        RETURN DISTINCT
            p.name as name,
            coalesce(l.name, 'Unknown') as city,
            final_score,
            skills_found,
            current_load
        ORDER BY final_score DESC
        LIMIT $limit
        """

        strict_params = {
            "skills": skills,
            "limit": team_size * 2,
            "location": location,
            "needed_alloc": allocation_needed
        }

        try:
            raw_candidates = self.graph.query(query_strict, strict_params)
        except Exception as e:
            print(f"❌ Neo4j Error (Strict Query): {e}")
            raw_candidates = []

        # ---------- DEDUP ----------
        candidates = []
        seen_names = set()
        for cand in raw_candidates:
            if cand["name"] not in seen_names:
                seen_names.add(cand["name"])
                candidates.append(cand)
                if len(candidates) >= team_size:
                    break

        # ---------- FALLBACK ----------
        missing_count = team_size - len(candidates)

        if missing_count > 0:
            print(f"   ⚠️ Only found {len(candidates)} perfect matches. Looking for {missing_count} available candidates (Fallback)...")

            query_fallback = """
            MATCH (p:Person)
            WHERE NOT p.name IN $excluded

            OPTIONAL MATCH (p)-[:LOCATED_IN]->(l:Location)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)

            WITH p, l, sum(coalesce(r.allocation_percentage, coalesce(r.allocation, 0.0))) as current_load
            WHERE current_load + $needed_alloc <= 1.0

            RETURN DISTINCT
                p.name as name,
                coalesce(l.name, 'Unknown') as city,
                10.0 as final_score,
                [] as skills_found,
                current_load
            LIMIT $limit
            """

            try:
                fallback_results = self.graph.query(query_fallback, {
                    "excluded": list(seen_names),
                    "needed_alloc": allocation_needed,
                    "limit": missing_count * 2
                })

                for cand in fallback_results:
                    if cand["name"] not in seen_names:
                        seen_names.add(cand["name"])
                        candidates.append(cand)
                        if len(candidates) >= team_size:
                            break

            except Exception as e:
                print(f"❌ Neo4j Error (Fallback Query): {e}")

        # ---------- ASSIGN ----------
        final_team = []
        if candidates:
            for member in candidates:
                if simulate_only:
                    # ✅ Simulation mode: just compute new load, don't write to DB
                    member["new_load"] = float(member["current_load"]) + allocation_needed
                    member["simulated"] = True
                    final_team.append(member)
                else:
                    # ✅ Real mode: assign to database with date() (temporal consistency)
                    assign_query = """
                    MATCH (p:Person {name: $name}), (proj:Project {id: $proj_id})
                    MERGE (p)-[r:ASSIGNED_TO]->(proj)
                    SET r.allocation = $alloc,
                        r.allocation_percentage = $alloc,
                        r.role = 'Developer',
                        r.assigned_at = date(),
                        r.start_date = date(),
                        r.end_date = proj.end_date
                    """
                    try:
                        self.graph.query(assign_query, {
                            "name": member["name"],
                            "proj_id": project_ref,
                            "alloc": allocation_needed
                        })
                        member["new_load"] = float(member["current_load"]) + allocation_needed
                        final_team.append(member)
                    except Exception as e:
                        print(f"❌ Error assigning {member['name']}: {e}")

        return final_team

    def print_report(self, project_name, team):
        print(f"\n{'='*60}")
        print(f"🚀 TEAM ASSIGNED TO: {project_name}")
        print(f"{'='*60}")

        if not team:
            print("❌ Could not find ANY available candidates (Strict or Fallback).")
            return

        for i, member in enumerate(team, 1):
            skills = member.get("skills_found", [])
            skills_info = str(skills) if skills else "0 (Fallback)"

            print(f"{i}. {member['name']} ({member['city']})")
            print(f"   📊 Score: {member['final_score']} | Skills: {skills_info}")
            print(f"   🔋 Load: {member['current_load']*100:.0f}% -> {member['new_load']*100:.0f}%")

        print("\n")

def print_visualization_link():
    print("\n" + "="*60)
    print("👀 VISUALIZE YOUR GRAPH")
    print("="*60)
    print("1. Open Neo4j Browser: http://localhost:7474")
    print("2. Run this Cypher query to see ALL PROJECTS (Ongoing + New):")
    print("   MATCH (p:Person)-[r:ASSIGNED_TO]->(pr:Project) RETURN p, r, pr")
    print("="*60 + "\n")

if __name__ == "__main__":
    matcher = TeamMatcher()

    # 1) SMART RESET
    matcher.reset_assignments()

    # 2) Load RFP PDFs
    rfp_files = glob.glob("data/rfps/*.pdf")

    if rfp_files:
        print(f"📂 Found {len(rfp_files)} RFPs. Processing sequentially...")

        for rfp_file in rfp_files:
            reqs = matcher.analyze_rfp(rfp_file)

            if reqs:
                rfp_id = os.path.splitext(os.path.basename(rfp_file))[0]
                reqs["rfp_id"] = rfp_id
                reqs["project_id"] = f"{rfp_id}::proj"
                matcher.create_rfp_and_project(reqs, rfp_id)
                team = matcher.find_and_assign_team(reqs, project_ref=reqs["project_id"])
                matcher.print_report(reqs.get("project_title", reqs.get("project_name", "Project")), team)

            time.sleep(1)

        print_visualization_link()
    else:
        print("❌ No RFPs found in data/rfps/")
