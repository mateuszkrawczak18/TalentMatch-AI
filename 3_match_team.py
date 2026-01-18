import os
import glob
import json
import time
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import AzureChatOpenAI
from langchain_neo4j import Neo4jGraph
from typing import List, Dict

# Ładowanie zmiennych środowiskowych (.env)
load_dotenv()

class TeamMatcher:
    def __init__(self):
        # 1. Połączenie z Neo4j (Używamy 127.0.0.1 dla stabilności na Windows)
        self.graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password123")
        )
        
        # 2. Konfiguracja LLM (Dostosowana do gpt-5-nano / o1)
        # Temp=1 wymagane przez modele reasoning w Azure
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=1,
            max_retries=3,
            request_timeout=120
        )

    def extract_json_from_text(self, text: str) -> Dict:
        """Parsuje odpowiedź LLM, wyciągając czysty JSON."""
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start == -1 or end == 0: return {}
            
            json_str = text[start:end]
            return json.loads(json_str)
        except json.JSONDecodeError:
            print("⚠️ JSON Decode Error. Raw text:", text[:100] + "...")
            return {}
        except Exception as e:
            print(f"⚠️ Parser Error: {e}")
            return {}

    def reset_assignments(self):
        """
        SMART RESET:
        Usuwa tylko projekty z RFP (te, które NIE są 'Ongoing').
        Zachowuje 'Ongoing' projekty stworzone przez skrypt 2b_ingest_projects.py.
        """
        print("🧹 Cleaning up previous RFP assignments (Preserving 'Ongoing' projects)...")
        try:
            # 1. Usuń relacje ASSIGNED_TO tylko dla projektów, które NIE są Ongoing
            self.graph.query("""
                MATCH (:Person)-[r:ASSIGNED_TO]->(p:Project)
                WHERE p.status <> 'Ongoing' OR p.status IS NULL
                DELETE r
            """)
            
            # 2. Usuń same węzły Projektów (tylko te z RFP)
            self.graph.query("""
                MATCH (p:Project)
                WHERE p.status <> 'Ongoing' OR p.status IS NULL
                DETACH DELETE p
            """)
            print("✅ System ready. 'Ongoing' projects preserved.")
        except Exception as e:
            print(f"⚠️ Warning during reset: {e}")

    def analyze_rfp(self, pdf_path: str) -> Dict:
        """Czyta plik PDF RFP i wyciąga wymagania."""
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
                    "project_name": "Name of project",
                    "required_skills": ["Skill1", "Skill2"],
                    "team_size": 5,
                    "location": "City Name" (or null if remote allowed),
                    "allocation_needed": 1.0
                }}
                
                If allocation is not specified, assume 1.0 (Full Time).
                
                RFP Content:
                {content[:4000]} 
                """
                
                response = self.llm.invoke(prompt)
                data = self.extract_json_from_text(response.content)
                
                if not data:
                    print("⚠️ Empty JSON received from LLM.")
                    continue

                if not data.get('allocation_needed'): data['allocation_needed'] = 1.0
                if not data.get('team_size'): data['team_size'] = 5
                
                return data
                
            except Exception as e:
                print(f"   ⚠️ Error processing RFP (Attempt {attempt+1}/{max_retries}): {e}")
                time.sleep(2)
        
        print("❌ Failed to analyze RFP after multiple attempts.")
        return None

    def create_project_node(self, reqs: Dict):
        """Tworzy węzeł Projektu w grafie."""
        query = """
        MERGE (p:Project {name: $name})
        SET p.location = $location, 
            p.required_skills = $skills,
            p.status = 'New RFP'
        RETURN p
        """
        self.graph.query(query, {
            "name": reqs['project_name'],
            "location": reqs.get('location', 'Remote'),
            "skills": reqs.get('required_skills', [])
        })
        print(f"🏗️  Created Project Node: {reqs['project_name']}")

    def find_and_assign_team(self, reqs: Dict):
        """
        Główna logika rekrutacji z DEDUPLIKACJĄ.
        """
        skills = reqs.get('required_skills', [])
        team_size = reqs.get('team_size', 5)
        location = reqs.get('location')
        allocation_needed = reqs.get('allocation_needed', 1.0)
        project_name = reqs['project_name']
        
        print(f"   🔍 Looking for {team_size} people. Req. Allocation: {allocation_needed*100}%")

        # --- KROK 1: STRICT MATCH ---
        query_strict = """
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
        WHERE toLower(s.name) IN [skill IN $skills | toLower(skill)]
        
        OPTIONAL MATCH (p)-[:LOCATED_IN]->(l:Location)
        OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(any_project:Project)
        
        WITH p, l, count(s) as skill_count, collect(s.name) as skills_found, sum(coalesce(r.allocation, 0.0)) as current_load
        
        WHERE current_load + $needed_alloc <= 1.0
        
        WITH p, l, skill_count, skills_found, current_load,
             CASE 
                WHEN $location IS NULL THEN 10 
                WHEN l IS NOT NULL AND toLower(l.name) CONTAINS toLower($location) THEN 50
                WHEN l IS NOT NULL AND toLower(l.name) CONTAINS 'remote' THEN 5
                ELSE 0 
             END as loc_score
        
        WITH p, l, skills_found, current_load,
             (skill_count * 10) + loc_score + ((1.0 - current_load) * 20) as final_score
        
        RETURN DISTINCT p.name as name, coalesce(l.name, 'Unknown') as city, final_score, skills_found, current_load
        ORDER BY final_score DESC
        LIMIT $limit
        """
        
        strict_params = {
            "skills": skills, 
            "limit": team_size * 2, # Pobieramy więcej, żeby mieć z czego odsiać duplikaty
            "location": location,
            "needed_alloc": allocation_needed
        }
        
        try:
            raw_candidates = self.graph.query(query_strict, strict_params)
        except Exception as e:
            print(f"❌ Neo4j Error (Strict Query): {e}")
            raw_candidates = []
        
        # 🔥 DEDUPLIKACJA (Python)
        candidates = []
        seen_names = set()
        
        for cand in raw_candidates:
            if cand['name'] not in seen_names:
                seen_names.add(cand['name'])
                candidates.append(cand)
                if len(candidates) >= team_size:
                    break
        
        # --- KROK 2: FALLBACK ---
        missing_count = team_size - len(candidates)
        
        if missing_count > 0:
            print(f"   ⚠️ Only found {len(candidates)} perfect matches. Looking for {missing_count} available candidates (Fallback)...")
            
            query_fallback = """
            MATCH (p:Person)
            WHERE NOT p.name IN $excluded
            
            OPTIONAL MATCH (p)-[:LOCATED_IN]->(l:Location)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(any_project:Project)
            
            WITH p, l, sum(coalesce(r.allocation, 0.0)) as current_load
            
            WHERE current_load + $needed_alloc <= 1.0
            
            RETURN DISTINCT p.name as name, coalesce(l.name, 'Unknown') as city, 10.0 as final_score, [] as skills_found, current_load
            LIMIT $limit
            """
            
            try:
                fallback_results = self.graph.query(query_fallback, {
                    "excluded": list(seen_names),
                    "needed_alloc": allocation_needed,
                    "limit": missing_count * 2
                })
                
                for cand in fallback_results:
                    if cand['name'] not in seen_names:
                        seen_names.add(cand['name'])
                        candidates.append(cand)
                        if len(candidates) >= team_size:
                            break
                            
            except Exception as e:
                print(f"❌ Neo4j Error (Fallback Query): {e}")

        # --- KROK 3: ZAPISYWANIE ---
        final_team = []
        if candidates:
            for member in candidates:
                assign_query = """
                MATCH (p:Person {name: $name}), (proj:Project {name: $proj_name})
                MERGE (p)-[r:ASSIGNED_TO]->(proj)
                SET r.allocation = $alloc, r.role = 'Developer', r.assigned_at = datetime()
                """
                try:
                    self.graph.query(assign_query, {
                        "name": member['name'],
                        "proj_name": project_name,
                        "alloc": allocation_needed
                    })
                    member['new_load'] = member['current_load'] + allocation_needed
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
            skills = member.get('skills_found', [])
            skills_info = str(skills) if skills else "0 (Fallback)"
            
            print(f"{i}. {member['name']} ({member['city']})")
            print(f"   📊 Score: {member['final_score']} | Skills: {skills_info}")
            print(f"   🔋 Load: {member['current_load']*100:.0f}% -> {member['new_load']*100:.0f}% (Busy)")
        print("\n")

def print_visualization_link():
    print("\n" + "="*60)
    print("👀 VISUALIZE YOUR GRAPH")
    print("="*60)
    print("1. Open Neo4j Browser: http://localhost:7474")
    print("2. Run this Cypher query to see ALL PROJECTS (Ongoing + New):")
    print("   MATCH (p:Person)-[r:ASSIGNED_TO]->(pr:Project) RETURN p, r, pr")
    print("\n💡 TIP: If you see numbers on nodes, click the Node Label (e.g. Person) and select 'name' in the bottom caption bar.")
    print("="*60 + "\n")

if __name__ == "__main__":
    matcher = TeamMatcher()
    
    # 1. SMART RESET
    matcher.reset_assignments()
    
    # 2. Pobranie plików RFP
    rfp_files = glob.glob("data/rfps/*.pdf")
    
    if rfp_files:
        print(f"📂 Found {len(rfp_files)} RFPs. Processing sequentially...")
        
        for rfp_file in rfp_files:
            reqs = matcher.analyze_rfp(rfp_file)
            
            if reqs:
                matcher.create_project_node(reqs)
                team = matcher.find_and_assign_team(reqs)
                matcher.print_report(reqs['project_name'], team)
            
            time.sleep(2)
        
        print_visualization_link()
            
    else:
        print("❌ No RFPs found in data/rfps/")