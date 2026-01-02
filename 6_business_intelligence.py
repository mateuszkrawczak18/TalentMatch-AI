import os
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_openai import AzureChatOpenAI
from datetime import datetime

load_dotenv()


class BusinessIntelligenceEngine:
    """
    GraphRAG-based Business Intelligence Engine for TalentMatch.
    Handles 6 types of queries:
    1. Counting Queries
    2. Filtering Queries  
    3. Aggregation Queries
    4. Multi-hop Reasoning
    5. Temporal Queries
    6. Complex Business Scenarios
    """

    def __init__(self):
        # Initialize Neo4j connection
        self.graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD")
        )

        # Initialize LLM for query analysis
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=1.0,
            max_retries=3,
            request_timeout=60
        )

    def classify_query(self, question: str) -> str:
        """
        Classify the query into one of 6 types using LLM.
        Returns: 'counting', 'filtering', 'aggregation', 'reasoning', 'temporal', 'scenario'
        """
        prompt = f"""
Classify this business intelligence query into ONE of these categories:

1. COUNTING - Questions about "how many", "count"
   Examples: "How many Python developers?", "Count available developers"

2. FILTERING - Questions asking for specific information about people OR finding people with criteria
   Examples: "What skills does John have?", "What technologies does Victoria know?", "Find developers with Python", "List people in NYC"
   KEY: Questions with "what skills/technologies does PERSON_NAME have/know" are FILTERING

3. AGGREGATION - Questions about "average", "total", "sum", "min", "max", statistics
   Examples: "Average years of experience?", "Total developers"

4. REASONING - Questions about relationships between people like "who worked together", "from same company"
   Examples: "Show me developers who worked together", "Who has the same skills as John?"
   KEY: NOT for asking about a single person's attributes

5. TEMPORAL - Questions about time, dates, "when", "available after"
   Examples: "Who becomes available next month?", "Current assignments"

6. SCENARIO - Complex "what-if", budget constraints, team composition, risk analysis
   Examples: "Best team for project under budget?", "Skills gap analysis"

Query: {question}

Respond with ONLY the category name (COUNTING, FILTERING, AGGREGATION, REASONING, TEMPORAL, or SCENARIO).
"""
        try:
            response = self.llm.invoke(prompt)
            category = response.content.strip().upper()
            
            # Map to internal names
            mapping = {
                'COUNTING': 'counting',
                'FILTERING': 'filtering',
                'AGGREGATION': 'aggregation',
                'REASONING': 'reasoning',
                'TEMPORAL': 'temporal',
                'SCENARIO': 'scenario'
            }
            return mapping.get(category, 'scenario')  # Default to scenario for complex queries
        except Exception as e:
            print(f"⚠️  Error classifying query: {e}. Defaulting to 'scenario'.")
            return 'scenario'

    def extract_json_from_response(self, text: str) -> Optional[Dict]:
        """Extract JSON from LLM response."""
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start == -1 or end == 0:
                return None
            return json.loads(text[start:end])
        except:
            return None

    # ==================== QUERY TYPE 1: COUNTING ====================
    def handle_counting_query(self, question: str) -> Dict[str, Any]:
        """
        Handle counting queries like:
        - "How many Python developers are available?"
        - "Count developers with AWS certifications"
        - "How many projects are currently active?"
        """
        print(f"🔢 COUNTING QUERY: {question}")

        # Use LLM to extract key information
        extraction_prompt = f"""
        Extract from this counting query:
        - What entity to count (Person, Skill, Project, etc.)
        - Any filter conditions (available, certified, etc.)
        
        Query: {question}
        
        Return JSON:
        {{
            "entity": "Person/Skill/Project/Company/University",
            "filters": {{"key": "value"}},
            "attribute_to_count": "skill_name or other attribute"
        }}
        """
        
        try:
            llm_response = self.llm.invoke(extraction_prompt)
            params = self.extract_json_from_response(llm_response.content) or {}
        except:
            params = {}

        # Build Cypher query based on extracted parameters
        entity = params.get('entity', 'Person')
        attribute = params.get('attribute_to_count', '')

        if 'python' in question.lower():
            # Specific case: Python developers available
            cypher = """
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WHERE toLower(s.id) = 'python'
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->()
            WITH p, sum(coalesce(r.allocation, 0.0)) as current_load
            WHERE current_load < 1.0
            RETURN count(DISTINCT p) as available_python_devs
            """
        elif 'aws' in question.lower() or 'certification' in question.lower():
            # AWS certifications
            cypher = """
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WHERE toLower(s.id) CONTAINS 'aws'
            RETURN count(DISTINCT p) as certified_developers
            """
        elif 'project' in question.lower() and 'active' in question.lower():
            # Active projects
            cypher = """
            MATCH (proj:Project {status: 'Active'})
            RETURN count(proj) as active_projects
            """
        else:
            # Generic counting
            cypher = f"""
            MATCH (n:{entity})
            RETURN count(n) as total_count
            """

        try:
            result = self.graph.query(cypher)
            count = result[0][list(result[0].keys())[0]] if result else 0
            
            return {
                'type': 'counting',
                'query': question,
                'result': count,
                'explanation': f"Found {count} matching items for: {question}",
                'cypher': cypher,
                'success': True
            }
        except Exception as e:
            return {
                'type': 'counting',
                'query': question,
                'result': None,
                'error': str(e),
                'success': False
            }

    # ==================== QUERY TYPE 2: FILTERING ====================
    def handle_filtering_query(self, question: str) -> Dict[str, Any]:
        """
        Handle filtering queries dynamically using LLM to generate Cypher.
        """
        print(f"🔍 FILTERING QUERY: {question}")

        cypher_generation_prompt = f"""
You are a Neo4j Cypher query expert. Generate a Cypher query to answer this filtering question.

Available node types: Person, Skill, Location, Company, Role, Project
Available relationships: HAS_SKILL, LOCATED_IN, WORKED_AT, HAS_ROLE, ASSIGNED_TO, REQUIRED_SKILL, AVAILABLE_IN

CRITICAL - Understand the question type:

1. If asking about a SPECIFIC PERSON's attributes (e.g., "What skills does Victoria Clark have?", "What technologies does John know?"):
   - Match the specific person: MATCH (p:Person) WHERE p.id = 'Victoria Clark'
   - Then get their skills: MATCH (p)-[:HAS_SKILL]->(s:Skill)
   - Return the skills as a list: RETURN collect(s.id) as skills

2. If asking to FIND PEOPLE with criteria (e.g., "Find developers with Python", "I need a Python expert", "List people in NYC"):
   - Match people with those criteria
   - Use FLEXIBLE matching with CONTAINS for better results
   - Return person names and key attributes: RETURN p.id as name, collect(s.id) as skills

Important rules:
- Person names are stored in p.id property (not p.name)
- For skill matching: Use CONTAINS for flexibility - WHERE toLower(s.id) CONTAINS 'python' (NOT exact match)
- For phrases like "I need X expert" or "I need someone with X" - extract the skill and find people with that skill
- "machine learning" can match skills like "Python", "TensorFlow", "ML", "Data Science" - use OR conditions
- For multiple skills (AND): Match each skill separately then intersect
- Show available developers first: OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->() WITH p, sum(coalesce(r.allocation, 0.0)) as current_load WHERE current_load < 1.0
- LIMIT 20 results when returning people

Examples:
- "I need a Python expert" → Find developers with Python skill
- "Find someone who knows databases" → Find developers with skills containing "sql", "postgres", "mysql", "mongo", etc.
- "I need a machine learning expert" → Find developers with Python (common for ML)

Question: {question}

Generate ONLY the Cypher query, nothing else.
"""

        try:
            llm_response = self.llm.invoke(cypher_generation_prompt)
            cypher = llm_response.content.strip()
            cypher = cypher.replace('```cypher', '').replace('```', '').strip()
            
            print(f"🔧 Generated Cypher: {cypher}")
            
            results = self.graph.query(cypher)
            
            return {
                'type': 'filtering',
                'query': question,
                'result': results,
                'explanation': f"Found {len(results)} result(s) for: {question}",
                'cypher': cypher,
                'success': True
            }
        except Exception as e:
            print(f"❌ Error: {e}")
            return {
                'type': 'filtering',
                'query': question,
                'result': None,
                'error': str(e),
                'success': False
            }

    # ==================== QUERY TYPE 3: AGGREGATION ====================
    def handle_aggregation_query(self, question: str) -> Dict[str, Any]:
        """
        Handle aggregation queries like:
        - "Average years of experience for machine learning projects"
        - "Total capacity available for Q4 projects"
        - "Sum of all developer billable hours"
        """
        print(f"📊 AGGREGATION QUERY: {question}")

        if 'average' in question.lower() and 'experience' in question.lower():
            # Average skills per developer as a proxy for experience
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
            # Average skills per developer
            cypher = """
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WITH p, count(DISTINCT s) as skill_count
            RETURN 
                round(avg(skill_count), 2) as average_skills_per_developer,
                count(p) as total_developers
            """
        elif 'total' in question.lower() and 'capacity' in question.lower():
            # Total available capacity
            cypher = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->()
            WITH p, count(r) as assignment_count
            RETURN 
                count(p) as total_developers,
                sum(CASE WHEN assignment_count = 0 THEN 1 ELSE 0 END) as available_developers,
                sum(CASE WHEN assignment_count > 0 THEN 1 ELSE 0 END) as assigned_developers
            """
        elif 'count' in question.lower() or 'sum' in question.lower():
            cypher = """
            MATCH (p:Person)
            RETURN count(p) as total_count
            """
        else:
            # Generic aggregation - show key stats
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
                assign_count as total_assignments,
                round(toFloat(skill_count) / dev_count, 2) as avg_skills_per_dev
            """

        try:
            result = self.graph.query(cypher)
            
            if result:
                data = result[0]
                # Format the result nicely
                formatted_result = {}
                for key, value in data.items():
                    if isinstance(value, float):
                        formatted_result[key] = round(value, 2)
                    else:
                        formatted_result[key] = value

                return {
                    'type': 'aggregation',
                    'query': question,
                    'result': formatted_result,
                    'explanation': f"Aggregation results for: {question}",
                    'cypher': cypher,
                    'success': True
                }
            else:
                return {
                    'type': 'aggregation',
                    'query': question,
                    'result': None,
                    'error': 'No data found',
                    'success': False
                }
        except Exception as e:
            return {
                'type': 'aggregation',
                'query': question,
                'result': None,
                'error': str(e),
                'success': False
            }

    # ==================== QUERY TYPE 4: REASONING ====================
    def handle_reasoning_query(self, question: str) -> Dict[str, Any]:
        """
        Handle multi-hop reasoning queries like:
        - "Find developers who worked together"
        - "Developers from same role or skill"
        - "Who has worked in the same companies?"
        """
        print(f"🧠 REASONING QUERY: {question}")

        if 'worked together' in question.lower():
            # Find pairs of developers who worked at same company (distributed across companies)
            cypher = """
            MATCH (p1:Person)-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(p2:Person)
            WHERE p1.id < p2.id
            WITH c, collect({dev1: p1.id, dev2: p2.id}) as pairs
            UNWIND pairs[0..5] as pair
            RETURN pair.dev1 as developer_1, pair.dev2 as developer_2, c.id as company
            ORDER BY company
            LIMIT 30
            """
        elif 'same university' in question.lower() or 'same school' in question.lower():
            # Find developers with same role (university data not available)
            cypher = """
            MATCH (p1:Person)-[:HAS_ROLE]->(r:Role)<-[:HAS_ROLE]-(p2:Person)
            WHERE p1.id < p2.id
            RETURN p1.id as developer_1, p2.id as developer_2, r.id as shared_role
            LIMIT 20
            """
        elif 'same' in question.lower() and 'company' in question.lower():
            # Developers from same company (distributed across companies)
            cypher = """
            MATCH (p1:Person)-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(p2:Person)
            WHERE p1.id < p2.id
            WITH c, collect({dev1: p1.id, dev2: p2.id}) as pairs
            UNWIND pairs[0..5] as pair
            RETURN pair.dev1 as developer_1, pair.dev2 as developer_2, c.id as company
            ORDER BY company
            LIMIT 30
            """
        elif 'same skill' in question.lower():
            # Developers with same skills
            cypher = """
            MATCH (p1:Person)-[:HAS_SKILL]->(s:Skill)<-[:HAS_SKILL]-(p2:Person)
            WHERE p1.id < p2.id
            RETURN p1.id as developer_1, p2.id as developer_2, s.id as shared_skill
            LIMIT 20
            """
        else:
            # Generic relationship query - developers who worked together (distributed)
            cypher = """
            MATCH (p1:Person)-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(p2:Person)
            WHERE p1.id < p2.id
            WITH c, collect({dev1: p1.id, dev2: p2.id}) as pairs
            UNWIND pairs[0..5] as pair
            RETURN pair.dev1 as person_1, c.id as company, pair.dev2 as person_2
            ORDER BY company
            LIMIT 30
            """

        try:
            results = self.graph.query(cypher)
            
            return {
                'type': 'reasoning',
                'query': question,
                'result': results,
                'explanation': f"Found {len(results)} relationships for: {question}",
                'cypher': cypher,
                'success': True
            }
        except Exception as e:
            return {
                'type': 'reasoning',
                'query': question,
                'result': None,
                'error': str(e),
                'success': False
            }

    # ==================== QUERY TYPE 5: TEMPORAL ====================
    def handle_temporal_query(self, question: str) -> Dict[str, Any]:
        """
        Handle temporal queries like:
        - "Who becomes available after current project ends?"
        - "Current project assignments"
        - "Developers finishing projects soon"
        """
        print(f"⏰ TEMPORAL QUERY: {question}")

        if 'available after' in question.lower() or 'becomes available' in question.lower():
            # Show current project assignments
            cypher = """
            MATCH (p:Person)-[r:ASSIGNED_TO]->(proj:Project)
            RETURN p.id as developer, proj.name as project, r.allocation as allocation_percent
            LIMIT 20
            """
        elif 'current' in question.lower() or 'assignment' in question.lower():
            # Current assignments
            cypher = """
            MATCH (p:Person)-[r:ASSIGNED_TO]->(proj:Project)
            RETURN p.id as developer, proj.name as project, r.allocation as allocation_percent
            LIMIT 20
            """
        elif 'finishing' in question.lower() or 'ends' in question.lower():
            # Show current assignments (proxying for "finishing soon")
            cypher = """
            MATCH (p:Person)-[r:ASSIGNED_TO]->(proj:Project)
            RETURN p.id as developer, proj.name as project, r.allocation as allocation_percent
            ORDER BY proj.name
            LIMIT 20
            """
        else:
            # Generic temporal - show assignments
            cypher = """
            MATCH (p:Person)-[r:ASSIGNED_TO]->(proj:Project)
            RETURN p.id as developer, proj.name as project, r.allocation as allocation_percent
            LIMIT 20
            """

        try:
            results = self.graph.query(cypher)
            
            return {
                'type': 'temporal',
                'query': question,
                'result': results,
                'explanation': f"Found {len(results)} temporal results for: {question}",
                'cypher': cypher,
                'success': True
            }
        except Exception as e:
            return {
                'type': 'temporal',
                'query': question,
                'result': None,
                'error': str(e),
                'success': False
            }

    # ==================== QUERY TYPE 6: COMPLEX SCENARIOS ====================
    def handle_scenario_query(self, question: str) -> Dict[str, Any]:
        """
        Handle complex business scenario queries like:
        - "Optimal team composition for FinTech RFP under budget constraints"
        - "Skills gaps analysis for upcoming project pipeline"
        - "Risk assessment: single points of failure in current assignments"
        """
        print(f"🎯 SCENARIO QUERY: {question}")

        if 'optimal team' in question.lower() or 'team composition' in question.lower():
            # Find available developers ranked by score
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
        elif 'skills gap' in question.lower() or 'gap analysis' in question.lower():
            # Analyze skills gaps
            cypher = """
            MATCH (p:Project)
            UNWIND p.required_skills as required_skill
            OPTIONAL MATCH (dev:Person)-[:HAS_SKILL]->(s:Skill)
            WHERE toLower(s.id) = toLower(required_skill)
            WITH required_skill, count(DISTINCT dev) as dev_count, p.name as project
            RETURN project, required_skill, dev_count as available_developers
            LIMIT 20
            """
        elif 'risk' in question.lower() or 'single point' in question.lower():
            # Risk assessment - identify critical people
            cypher = """
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WITH s, count(DISTINCT p) as expert_count
            WHERE expert_count <= 2
            RETURN s.id as skill, expert_count as expert_count
            ORDER BY expert_count ASC
            """
        else:
            # Generic scenario - show system overview
            cypher = """
            MATCH (p:Person)
            OPTIONAL MATCH (proj:Project)
            OPTIONAL MATCH (s:Skill)
            RETURN 
                count(DISTINCT p) as total_developers,
                count(DISTINCT proj) as total_projects,
                count(DISTINCT s) as total_skills
            """

        try:
            results = self.graph.query(cypher)
            
            return {
                'type': 'scenario',
                'query': question,
                'result': results,
                'explanation': f"Scenario analysis for: {question}",
                'cypher': cypher,
                'success': True
            }
        except Exception as e:
            return {
                'type': 'scenario',
                'query': question,
                'result': None,
                'error': str(e),
                'success': False
            }

    # ==================== MAIN ENTRY POINT ====================
    def answer_question(self, question: str) -> Dict[str, Any]:
        """
        Main entry point: Classify query and route to appropriate handler.
        """
        print(f"\n📝 Question: {question}")
        print("⏳ Processing...\n")

        # Classify the query
        query_type = self.classify_query(question)
        print(f"🏷️  Query Type: {query_type.upper()}")

        # Route to appropriate handler
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

        return result

    def format_result(self, result: Dict[str, Any]) -> str:
        """Format result for display."""
        if not result.get('success', False):
            return f"❌ Error: {result.get('error', 'Unknown error')}"

        query_type = result.get('type', 'unknown')
        answer = result.get('result')

        if query_type == 'counting':
            return f"✅ Answer: {answer}\n\n📊 Count: {answer}"

        elif query_type == 'filtering':
            if isinstance(answer, list) and len(answer) > 0:
                formatted = "\n".join([f"  • {row['name']} ({row.get('current_utilization_percent', 0):.0f}% utilized)" for row in answer])
                return f"✅ Found {len(answer)} developers:\n{formatted}"
            else:
                return "✅ No developers found matching criteria"

        elif query_type == 'aggregation':
            if isinstance(answer, dict):
                # Format nicely with readable labels
                formatted_lines = []
                for key, value in answer.items():
                    # Convert snake_case to Title Case
                    label = key.replace('_', ' ').title()
                    formatted_lines.append(f"  • {label}: {value}")
                return f"✅ Aggregation Results:\n" + "\n".join(formatted_lines)
            else:
                return f"✅ Result: {answer}"

        elif query_type == 'reasoning':
            if isinstance(answer, list) and len(answer) > 0:
                formatted = "\n".join([f"  • {row.get('developer_1')} ↔ {row.get('developer_2')} ({row.get('company') or row.get('university')})" for row in answer])
                return f"✅ Found {len(answer)} connections:\n{formatted}"
            else:
                return "✅ No connections found"

        elif query_type == 'temporal':
            if isinstance(answer, list) and len(answer) > 0:
                formatted = "\n".join([f"  • {row.get('developer')} from {row.get('project')} (ends: {row.get('project_ends', 'N/A')})" for row in answer[:10]])
                return f"✅ Found {len(answer)} temporal events:\n{formatted}"
            else:
                return "✅ No temporal events found"

        elif query_type == 'scenario':
            if isinstance(answer, list) and len(answer) > 0:
                formatted = "\n".join([f"  • {json.dumps(row)}" for row in answer[:5]])
                return f"✅ Scenario Analysis:\n{formatted}"
            else:
                return f"✅ Result: {answer}"

        return f"✅ {answer}"


# ==================== EXAMPLE USAGE ====================
if __name__ == "__main__":
    print("="*60)
    print("🤖 TalentMatch Business Intelligence Engine")
    print("="*60)

    engine = BusinessIntelligenceEngine()

    # Example queries for each type
    test_queries = [
        # Counting
        "How many Python developers are available?",
        
        # Filtering
        "Find developers with React experience",
        
        # Aggregation
        "What is the average years of experience for all developers?",
        
        # Reasoning
        "Show me developers who worked together",
        
        # Temporal
        "Who becomes available after their current project ends?",
        
        # Scenario
        "What's the optimal team composition for an upcoming project?"
    ]

    for question in test_queries:
        result = engine.answer_question(question)
        
        print("\n" + "="*60)
        if result.get('success'):
            formatted = engine.format_result(result)
            print(formatted)
        else:
            print(f"❌ Error: {result.get('error')}")
        
        print("\n📋 Query Type:", result.get('type'))
        print("="*60)
