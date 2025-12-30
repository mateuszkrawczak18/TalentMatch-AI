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
        # Połączenie z Neo4j
        self.graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD")
        )
        # Konfiguracja LLM do analizy RFP
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0,
            max_retries=5,      
            request_timeout=120 
        )

    def extract_json_from_text(self, text: str) -> Dict:
        """Parsuje odpowiedź LLM, wyciągając czysty JSON."""
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start == -1 or end == 0: return {}
            return json.loads(text[start:end])
        except: return {}

    def reset_assignments(self):
        """Czyści stan projektu (usuwa projekty i przypisania) przed nowym uruchomieniem."""
        print("🧹 Resetting project assignments and deleting old Project nodes...")
        try:
            self.graph.query("MATCH (p:Project) DETACH DELETE p")
            self.graph.query("MATCH (:Person)-[r:ASSIGNED_TO]->() DELETE r")
            print("✅ System ready for fresh matching.")
        except Exception as e:
            print(f"⚠️ Warning during reset: {e}")

    def analyze_rfp(self, pdf_path: str) -> Dict:
        """Czyta plik PDF RFP i wyciąga wymagania (Skille, Lokalizacja, Wielkość zespołu)."""
        print(f"\n📄 Analyzing RFP: {os.path.basename(pdf_path)}...")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                loader = PyPDFLoader(pdf_path)
                pages = loader.load()
                content = "\n".join([p.page_content for p in pages])
                
                prompt = f"""
                Extract structured data from this RFP.
                JSON Format:
                {{
                    "project_name": "Name of project",
                    "required_skills": ["Skill1", "Skill2"],
                    "team_size": 5,
                    "location": "City Name" (or null if remote allowed),
                    "allocation_needed": 0.5 (Assume 0.5 for part-time, 1.0 for full-time. Default to 1.0 if not specified)
                }}
                RFP Content: {content[:4000]} 
                """
                response = self.llm.invoke(prompt)
                data = self.extract_json_from_text(response.content)
                
                # Defaulty, jeśli LLM czegoś nie znajdzie
                if not data.get('allocation_needed'): data['allocation_needed'] = 1.0
                if not data.get('team_size'): data['team_size'] = 5
                return data
                
            except Exception as e:
                print(f"   ⚠️ Connection error (Attempt {attempt+1}/{max_retries}). Retrying in 5s...")
                time.sleep(5)
        
        print("❌ Failed to analyze RFP after multiple attempts.")
        return None

    def create_project_node(self, reqs: Dict):
        """Tworzy węzeł Projektu w grafie."""
        query = """
        MERGE (p:Project {name: $name})
        SET p.location = $location, 
            p.required_skills = $skills,
            p.status = 'Active'
        RETURN p
        """
        self.graph.query(query, {
            "name": reqs['project_name'],
            "location": reqs.get('location', 'Remote'),
            "skills": reqs['required_skills']
        })
        print(f"🏗️  Created Project Node: {reqs['project_name']}")

    def find_and_assign_team(self, reqs: Dict):
        """
        Główna logika rekrutacji:
        1. Strict Match: Szuka osób ze skillami, w lokalizacji i z wolnym czasem.
        2. Fallback: Jeśli brakuje ludzi, dobiera kogokolwiek wolnego (Juniorzy/Inni).
        3. Assign: Zapisuje relację ASSIGNED_TO w bazie.
        """
        skills = reqs.get('required_skills', [])
        team_size = reqs.get('team_size', 5)
        location = reqs.get('location')
        allocation_needed = reqs.get('allocation_needed', 1.0)
        project_name = reqs['project_name']
        
        print(f"   🔍 Looking for {team_size} people. Req. Allocation: {allocation_needed*100}%")

        # --- KROK 1: STRICT MATCH (Idealni kandydaci) ---
        # Szukamy po relacji :HAS_SKILL i :LOCATED_IN (tylko miasta, ignorujemy uczelnie :EDUCATED_AT)
        query_strict = """
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
        WHERE toLower(s.id) IN [skill IN $skills | toLower(skill)]
        
        // Pobieramy miasto (jeśli istnieje)
        OPTIONAL MATCH (p)-[:LOCATED_IN]->(l:Location)
        
        // Sprawdzamy obecne obciążenie pracą
        OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(other_proj:Project)
        
        WITH p, l, count(s) as skill_count, collect(s.id) as skills_found, sum(coalesce(r.allocation, 0.0)) as current_load
        
        // Filtr dostępności
        WHERE current_load + $needed_alloc <= 1.0
        
        // Punktacja Lokalizacji
        WITH p, l, skill_count, skills_found, current_load,
             CASE 
                WHEN $location IS NULL THEN 10 
                WHEN l IS NOT NULL AND toLower(l.id) CONTAINS toLower($location) THEN 50
                WHEN l IS NOT NULL AND toLower(l.id) CONTAINS 'remote' THEN 5
                ELSE 0 
             END as loc_score
        
        // Algorytm Punktacji Końcowej
        WITH p, l, skills_found, current_load,
             (skill_count * 10) + loc_score + ((1.0 - current_load) * 20) as final_score
        
        // DISTINCT zapobiega duplikatom, jeśli ktoś ma np. 2 relacje do miast (chociaż po fixie w pliku 2 nie powinien)
        RETURN DISTINCT p.id as name, coalesce(l.id, 'Unknown') as city, final_score, skills_found, current_load
        ORDER BY final_score DESC
        LIMIT $limit
        """
        
        strict_params = {
            "skills": skills, 
            "limit": team_size, 
            "location": location,
            "needed_alloc": allocation_needed
        }
        
        try:
            candidates = self.graph.query(query_strict, strict_params)
        except Exception as e:
            print(f"❌ Neo4j Error (Strict Query): {e}")
            candidates = []
        
        # --- KROK 2: FALLBACK (Uzupełnianie braków) ---
        missing_count = team_size - len(candidates)
        
        if missing_count > 0:
            print(f"   ⚠️ Only found {len(candidates)} perfect matches. Looking for {missing_count} available candidates (Fallback)...")
            
            # Wykluczamy tych, których już znaleźliśmy
            excluded_names = [c['name'] for c in candidates]
            
            query_fallback = """
            MATCH (p:Person)
            WHERE NOT p.id IN $excluded
            
            OPTIONAL MATCH (p)-[:LOCATED_IN]->(l:Location)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(other_proj:Project)
            
            WITH p, l, sum(coalesce(r.allocation, 0.0)) as current_load
            
            WHERE current_load + $needed_alloc <= 1.0
            
            RETURN DISTINCT p.id as name, coalesce(l.id, 'Unknown') as city, 10.0 as final_score, [] as skills_found, current_load
            LIMIT $limit
            """
            
            try:
                fallback_candidates = self.graph.query(query_fallback, {
                    "excluded": excluded_names,
                    "needed_alloc": allocation_needed,
                    "limit": missing_count
                })
                candidates.extend(fallback_candidates)
            except Exception as e:
                print(f"❌ Neo4j Error (Fallback Query): {e}")

        # --- KROK 3: ZAPISANIE WYNIKÓW (State Update) ---
        final_team = []
        if candidates:
            for member in candidates:
                assign_query = """
                MATCH (p:Person {id: $name}), (proj:Project {name: $proj_name})
                MERGE (p)-[r:ASSIGNED_TO]->(proj)
                SET r.allocation = $alloc, r.role = 'Developer', r.assigned_at = datetime()
                """
                try:
                    self.graph.query(assign_query, {
                        "name": member['name'],
                        "proj_name": project_name,
                        "alloc": allocation_needed
                    })
                    # Aktualizujemy load do raportu
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
            is_fallback = len(member['skills_found']) == 0
            skills_info = f"{len(member['skills_found'])}" if not is_fallback else "0 (Fallback)"
            
            print(f"{i}. {member['name']} ({member['city']})")
            print(f"   📊 Score: {member['final_score']} | Skills: {skills_info}")
            print(f"   🔋 Load: {member['current_load']*100:.0f}% -> {member['new_load']*100:.0f}% (Busy)")
        print("\n")

def print_visualization_link():
    """Wyświetla link i instrukcję do wizualizacji w Neo4j Browser"""
    print("\n" + "="*60)
    print("👀 VISUALIZE YOUR GRAPH")
    print("="*60)
    print("1. Open Neo4j Browser: http://localhost:7474")
    print("   (Use credentials from .env, typically neo4j/password123)")
    print("\n2. Run this Cypher query to see the TEAM ASSIGNMENTS:")
    print("   MATCH (p:Person)-[r:ASSIGNED_TO]->(pr:Project) RETURN p, r, pr")
    print("\n3. Or run this to see the WHOLE GRAPH:")
    print("   MATCH (n) RETURN n LIMIT 50")
    print("="*60 + "\n")

if __name__ == "__main__":
    matcher = TeamMatcher()
    
    # 1. Reset stanu bazy
    matcher.reset_assignments()
    
    # 2. Pobranie plików RFP
    rfp_files = glob.glob("data/rfps/*.pdf")
    
    if rfp_files:
        print(f"📂 Found {len(rfp_files)} RFPs. Processing sequentially...")
        
        for rfp_file in rfp_files:
            # A. Analiza wymagań
            reqs = matcher.analyze_rfp(rfp_file)
            
            if reqs:
                # B. Stworzenie projektu w bazie
                matcher.create_project_node(reqs)
                
                # C. Znalezienie i przypisanie zespołu (Strict + Fallback)
                team = matcher.find_and_assign_team(reqs)
                
                # D. Raport
                matcher.print_report(reqs['project_name'], team)
            
            # Pauza dla czytelności logów
            time.sleep(2)
        
        # 3. Wyświetlenie linku do wizualizacji na samym końcu
        print_visualization_link()
            
    else:
        print("❌ No RFPs found in data/rfps/")