import os
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_openai import AzureChatOpenAI

load_dotenv()

class BusinessIntelligenceEngine:
    """
    GraphRAG-based Business Intelligence Engine for TalentMatch.
    Configured for Azure OpenAI (PJATK Environment).
    
    Hybrid Temperature Strategy:
    - llm_logic (Temp=1): Required for Azure Reasoning models (gpt-5-nano/o1).
    - llm_creative (Temp=1): Consistent setting for natural language generation.
    
    Handles 6 types of queries defined in PRD.
    """

    def __init__(self):
        # 1. Konfiguracja Neo4j
        # Używamy 127.0.0.1 dla stabilności na Windows
        self.graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password123")
        )

        # 2. LLM LOGICZNY (Do kodu i klasyfikacji)
        # ZMIANA: temperature=1 (Wymagane przez modele reasoning w Azure)
        self.llm_logic = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=1 
        )

        # 3. LLM KREATYWNY (Do odpowiedzi dla człowieka)
        # ZMIANA: temperature=1
        self.llm_creative = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=1 
        )

    def classify_query(self, question: str) -> str:
        """Classify the query into one of 6 types using LOGIC model."""
        prompt = f"""
Classify this business intelligence query into ONE of these categories:

1. COUNTING - Questions about "how many", "count"
   Examples: "How many Python developers?", "Count available developers"

2. FILTERING - Questions asking for specific information about people OR finding people with criteria
   Examples: "What skills does John have?", "Find developers with Python", "List people in NYC"

3. AGGREGATION - Questions about "average", "total", "sum", "min", "max", statistics
   Examples: "Average years of experience?", "Total developers"

4. REASONING - Questions about relationships between people like "who worked together"
   Examples: "Show me developers who worked together", "Who has the same skills as John?"

5. TEMPORAL - Questions about time, dates, "when", "available after"
   Examples: "Who becomes available next month?", "Current assignments"

6. SCENARIO - Complex "what-if", budget constraints, team composition
   Examples: "Best team for project under budget?", "Skills gap analysis"

Query: {question}

Respond with ONLY the category name (COUNTING, FILTERING, AGGREGATION, REASONING, TEMPORAL, or SCENARIO).
"""
        try:
            response = self.llm_logic.invoke(prompt)
            category = response.content.strip().upper()
            mapping = {
                'COUNTING': 'counting',
                'FILTERING': 'filtering',
                'AGGREGATION': 'aggregation',
                'REASONING': 'reasoning',
                'TEMPORAL': 'temporal',
                'SCENARIO': 'scenario'
            }
            return mapping.get(category, 'scenario')
        except Exception as e:
            print(f"⚠️ Error classifying query: {e}")
            return 'scenario'

    def extract_json_from_response(self, text: str) -> Optional[Dict]:
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start == -1 or end == 0: return None
            return json.loads(text[start:end])
        except:
            return None

    # ==================== QUERY HANDLERS (Full Logic) ====================

    def handle_counting_query(self, question: str) -> Dict[str, Any]:
        print(f"🔢 COUNTING QUERY: {question}")
        
        # Use LLM to extract key information
        extraction_prompt = f"""
        Extract from this counting query:
        - What entity to count (Person, Skill, Project, etc.)
        - Any filter conditions (available, certified, etc.)
        
        Query: {question}
        
        Return JSON:
        {{
            "entity": "Person/Skill/Project",
            "attribute_to_count": "skill_name"
        }}
        """
        try:
            llm_response = self.llm_logic.invoke(extraction_prompt)
            params = self.extract_json_from_response(llm_response.content) or {}
        except:
            params = {}

        entity = params.get('entity', 'Person')

        if 'python' in question.lower():
            cypher = """
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WHERE toLower(s.id) = 'python'
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->()
            WITH p, sum(coalesce(r.allocation, 0.0)) as current_load
            WHERE current_load < 1.0
            RETURN count(DISTINCT p) as result
            """
        elif 'aws' in question.lower() or 'certification' in question.lower():
            cypher = """
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WHERE toLower(s.id) CONTAINS 'aws'
            RETURN count(DISTINCT p) as result
            """
        elif 'project' in question.lower() and 'active' in question.lower():
            cypher = """
            MATCH (proj:Project {status: 'Active'})
            RETURN count(proj) as result
            """
        else:
            cypher = f"MATCH (n:{entity}) RETURN count(n) as result"

        try:
            result = self.graph.query(cypher)
            count = result[0]['result'] if result else 0
            return {'type': 'counting', 'result': count, 'cypher': cypher, 'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def handle_filtering_query(self, question: str) -> Dict[str, Any]:
        print(f"🔍 FILTERING QUERY: {question}")

        cypher_generation_prompt = f"""
        You are a Neo4j Cypher expert. Generate a query for: "{question}"
        Nodes: Person (id), Skill (id), Project, Company.
        Relationships: HAS_SKILL, ASSIGNED_TO, WORKED_AT.
        
        Rules:
        - Use CONTAINS for skills (toLower(s.id) CONTAINS 'python')
        - Return: p.id as name, collect(s.id) as skills
        - LIMIT 20
        
        Output ONLY the Cypher query.
        """
        try:
            resp = self.llm_logic.invoke(cypher_generation_prompt)
            cypher = resp.content.replace('```cypher','').replace('```','').strip()
            results = self.graph.query(cypher)
            return {'type': 'filtering', 'result': results, 'cypher': cypher, 'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def handle_aggregation_query(self, question: str) -> Dict[str, Any]:
        print(f"📊 AGGREGATION QUERY: {question}")

        if 'average' in question.lower() and 'experience' in question.lower():
            cypher = """
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WITH p, count(DISTINCT s) as skill_count
            RETURN 
                count(p) as total_developers,
                round(avg(skill_count), 2) as avg_skills_per_developer,
                max(skill_count) as max_skills,
                min(skill_count) as min_skills
            """
        elif ('average' in question.lower() and 'skill' in question.lower()) or 'avg' in question.lower():
            cypher = """
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WITH p, count(DISTINCT s) as skill_count
            RETURN 
                round(avg(skill_count), 2) as average_skills_per_developer,
                count(p) as total_developers
            """
        elif 'total' in question.lower() and 'capacity' in question.lower():
            cypher = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->()
            WITH p, count(r) as assignment_count
            RETURN 
                count(p) as total_developers,
                sum(CASE WHEN assignment_count = 0 THEN 1 ELSE 0 END) as available_developers,
                sum(CASE WHEN assignment_count > 0 THEN 1 ELSE 0 END) as assigned_developers
            """
        else:
            cypher = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->()
            WITH count(DISTINCT p) as dev_count,
                 count(DISTINCT s) as skill_count,
                 count(DISTINCT r) as assign_count
            RETURN 
                dev_count as total_developers,
                skill_count as total_unique_skills,
                assign_count as total_assignments
            """

        try:
            result = self.graph.query(cypher)
            data = result[0] if result else {}
            # Format floats
            formatted = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in data.items()}
            return {'type': 'aggregation', 'result': formatted, 'cypher': cypher, 'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def handle_reasoning_query(self, question: str) -> Dict[str, Any]:
        print(f"🧠 REASONING QUERY: {question}")

        if 'worked together' in question.lower():
            cypher = """
            MATCH (p1:Person)-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(p2:Person)
            WHERE p1.id < p2.id
            WITH c, collect({dev1: p1.id, dev2: p2.id}) as pairs
            UNWIND pairs[0..5] as pair
            RETURN pair.dev1 as developer_1, pair.dev2 as developer_2, c.id as company
            LIMIT 30
            """
        elif 'same university' in question.lower():
            cypher = """
            MATCH (p1:Person)-[:HAS_ROLE]->(r:Role)<-[:HAS_ROLE]-(p2:Person)
            WHERE p1.id < p2.id
            RETURN p1.id as developer_1, p2.id as developer_2, r.id as shared_role
            LIMIT 20
            """
        elif 'same skill' in question.lower():
            cypher = """
            MATCH (p1:Person)-[:HAS_SKILL]->(s:Skill)<-[:HAS_SKILL]-(p2:Person)
            WHERE p1.id < p2.id
            RETURN p1.id as developer_1, p2.id as developer_2, s.id as shared_skill
            LIMIT 20
            """
        else:
            cypher = """
            MATCH (p1:Person)-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(p2:Person)
            WHERE p1.id < p2.id
            RETURN p1.id as person_1, c.id as company, p2.id as person_2
            LIMIT 30
            """

        try:
            results = self.graph.query(cypher)
            return {'type': 'reasoning', 'result': results, 'cypher': cypher, 'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def handle_temporal_query(self, question: str) -> Dict[str, Any]:
        print(f"⏰ TEMPORAL QUERY: {question}")

        if 'available after' in question.lower() or 'becomes available' in question.lower():
            cypher = """
            MATCH (p:Person)-[r:ASSIGNED_TO]->(proj:Project)
            RETURN p.id as developer, proj.name as project, r.allocation as allocation_percent
            LIMIT 20
            """
        else:
            cypher = """
            MATCH (p:Person)-[r:ASSIGNED_TO]->(proj:Project)
            RETURN p.id as developer, proj.name as project, r.allocation as allocation_percent
            LIMIT 20
            """
        
        try:
            results = self.graph.query(cypher)
            return {'type': 'temporal', 'result': results, 'cypher': cypher, 'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def handle_scenario_query(self, question: str) -> Dict[str, Any]:
        print(f"🎯 SCENARIO QUERY: {question}")

        if 'optimal team' in question.lower() or 'team composition' in question.lower():
            cypher = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->()
            WITH p, sum(coalesce(r.allocation, 0.0)) as current_load
            WHERE current_load < 1.0
            OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
            WITH p, current_load, count(DISTINCT s) as skill_count
            RETURN p.id as developer, current_load * 100 as utilization, skill_count as skill_count,
                   ((1.0 - current_load) * 100 + skill_count * 5) as recommendation_score
            ORDER BY recommendation_score DESC
            LIMIT 15
            """
        elif 'skills gap' in question.lower():
            cypher = """
            MATCH (p:Project)
            UNWIND p.required_skills as required_skill
            OPTIONAL MATCH (dev:Person)-[:HAS_SKILL]->(s:Skill)
            WHERE toLower(s.id) = toLower(required_skill)
            WITH required_skill, count(DISTINCT dev) as dev_count, p.name as project
            RETURN project, required_skill, dev_count as available_developers
            LIMIT 20
            """
        else:
            cypher = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->()
            WITH p, sum(coalesce(r.allocation, 0.0)) as load
            WHERE load < 1.0
            RETURN p.id as developer, (1.0 - load) * 100 as available_capacity
            ORDER BY available_capacity DESC
            LIMIT 10
            """

        try:
            results = self.graph.query(cypher)
            return {'type': 'scenario', 'result': results, 'cypher': cypher, 'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==================== NATURAL LANGUAGE GENERATION ====================

    def generate_natural_answer(self, question: str, data: Any) -> str:
        """Uses CREATIVE model (Temp 1) to explain data to user."""
        if not data:
            return "I couldn't find any data matching your criteria."
            
        prompt = f"""
        You are an HR Assistant for TalentMatch AI. 
        The user asked: "{question}"
        
        The database returned this structured data:
        {str(data)}
        
        Task: Write a helpful, professional answer based ONLY on this data.
        - Don't mention "JSON", "list of dicts" or "database queries".
        - If it's a list of people, summarize it (e.g., "I found 3 developers...").
        - Be concise but friendly.
        """
        try:
            return self.llm_creative.invoke(prompt).content.strip()
        except:
            return str(data)

    # ==================== MAIN ENTRY POINT ====================

    def answer_question(self, question: str) -> Dict[str, Any]:
        """Main entry point: Classify -> Route -> Execute -> Explain."""
        print(f"\n📝 Question: {question}")
        
        # 1. Classify (Logic Model)
        query_type = self.classify_query(question)
        print(f"🏷️  Type: {query_type}")

        # 2. Route to handler
        handlers = {
            'counting': self.handle_counting_query,
            'filtering': self.handle_filtering_query,
            'aggregation': self.handle_aggregation_query,
            'reasoning': self.handle_reasoning_query,
            'temporal': self.handle_temporal_query,
            'scenario': self.handle_scenario_query
        }
        
        handler = handlers.get(query_type, self.handle_scenario_query)
        result = handler(question)

        # 3. Generate Natural Answer (Creative Model) if successful
        if result.get('success'):
            raw_data = result.get('result')
            natural_answer = self.generate_natural_answer(question, raw_data)
            result['natural_answer'] = natural_answer
            
        return result

    def format_result(self, result: Dict[str, Any]) -> str:
        """Format result for Streamlit."""
        if not result.get('success'):
            return f"❌ Error: {result.get('error')}"
        
        # Prefer natural answer if available
        if 'natural_answer' in result:
            return result['natural_answer']
            
        # Fallback formatting
        data = result.get('result')
        if isinstance(data, list):
            if not data: return "No results found."
            rows = []
            for item in data:
                rows.append(", ".join([f"{k}: {v}" for k,v in item.items()]))
            return "\n\n".join(rows)
        return str(data)

# Test lokalny
if __name__ == "__main__":
    engine = BusinessIntelligenceEngine()
    print(engine.answer_question("Find Python developers"))