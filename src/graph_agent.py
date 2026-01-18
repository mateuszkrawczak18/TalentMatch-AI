import os
import time
from datetime import date
from dotenv import load_dotenv

# --- FIX: Wracamy do langchain_community, aby uniknąć błędu Pydantic validation ---
from langchain_community.graphs import Neo4jGraph
from langchain_openai import AzureChatOpenAI
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate

load_dotenv()

class TalentAgent:
    def __init__(self):
        # 1. Połączenie z Neo4j
        self.graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password123")
        )
        # Odświeżenie schematu
        self.graph.refresh_schema()

        # 2. Model LLM
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0,                   
            max_retries=5,
            request_timeout=60
        )

        # 3. PROMPT GENERUJĄCY KOD CYPHER
        cypher_template = """Task: Generate Cypher statement to query a graph database.
        
        Definition of Schema:
        - Nodes: Person, Skill, Project, Location, Company, University, Certification
        - Relationships: 
          - (:Person)-[:HAS_SKILL]->(:Skill)
          - (:Person)-[:ASSIGNED_TO {{role, allocation, start_date}}]->(:Project)
          - (:Person)-[:LOCATED_IN]->(:Location)
          - (:Person)-[:WORKED_AT {{role, years}}]->(:Company)
          - (:Person)-[:STUDIED_AT {{degree}}]->(:University)
          - (:Person)-[:HAS_CERT]->(:Certification)
        
        Instructions:
        1. Use ONLY the provided schema.
        2. Do not include preambles.
        3. For "Availability", check if a person is NOT assigned to a Project.
        4. Keep queries concise.
        5. CRITICAL: When listing people based on criteria, ALWAYS return the proving attributes (p.seniority, s.name, p.rate).
        6. NO SLICING: Do NOT limit lists using syntax like [0..2] or [0..5]. Return ALL matching nodes.
        7. NO DATE FILTERING: Do NOT use 'start_date', 'date()', or check timeframes unless the user explicitly asks for a specific date in the question.
        8. RETURN FULL LISTS: If the user asks for people/projects, generate a query that returns ALL of them.
        9. OR LOGIC: If the user asks about multiple projects (e.g. "Project A and Project B"), use "OR" logic or the "IN" operator for project names. Do NOT match the same person to multiple projects simultaneously unless explicitly asked.
        
        Examples:
        
        Q: Who is assigned to Project Alpha and Project Beta?
        A: MATCH (p:Person)-[:ASSIGNED_TO]->(proj:Project)
           WHERE proj.name IN ['Project Alpha', 'Project Beta']
           RETURN p.name, proj.name as project

        Q: Find Senior Python Developers.
        A: MATCH (p:Person)-[:HAS_SKILL]->(s:Skill) 
           WHERE p.seniority = 'Senior' AND s.name = 'Python' 
           RETURN p.name, p.rate, p.seniority, collect(s.name) as skills

        Q: What is the average hourly rate of Senior Python Developers?
        A: MATCH (p:Person)-[:HAS_SKILL]->(s:Skill) 
           WHERE p.seniority = 'Senior' AND s.name = 'Python' 
           RETURN avg(p.rate) as average_rate

        Q: Who has worked with Jacob Young?
        A: MATCH (p1:Person {{name: 'Jacob Young'}})-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(p2:Person)
           RETURN p2.name, c.name as context, 'Company' as type
           UNION
           MATCH (p1:Person {{name: 'Jacob Young'}})-[:ASSIGNED_TO]->(proj:Project)<-[:ASSIGNED_TO]-(p2:Person)
           RETURN p2.name, proj.name as context, 'Project' as type

        Q: Who is currently available?
        A: MATCH (p:Person) 
           WHERE NOT (p)-[:ASSIGNED_TO]->(:Project) 
           RETURN p.name, p.role, p.seniority, p.rate
        
        User Question: {question}"""
        
        cypher_prompt = PromptTemplate(
            template=cypher_template, 
            input_variables=["question"]
        )

        # 4. PROMPT QA
        qa_template = """You are an HR Staffing Assistant.
        You have queried the Neo4j database and received the following JSON data in the "Context" section.
        
        CRITICAL RULES:
        1. The data in "Context" IS the correct answer. Use it directly.
        2. If the Context lists people/projects, list ALL of them in your answer using bullet points. Do not summarize or count them if a list is requested.
        3. If the Context is a list of people for an "availability" question, assume these ARE the available people.
        4. Do NOT say "The provided context does not include..." or "I cannot determine...".
        5. If the Context is empty, assume there are no results matching the criteria.

        Question: {question}
        Context: {context}

        Helpful Answer:"""
        
        qa_prompt = PromptTemplate(
            template=qa_template, 
            input_variables=["context", "question"]
        )

        self.chain = GraphCypherQAChain.from_llm(
            llm=self.llm,
            graph=self.graph,
            verbose=True,
            cypher_prompt=cypher_prompt,
            qa_prompt=qa_prompt,
            allow_dangerous_requests=True,
            validate_cypher=True,
            top_k=100
        )

    def ask(self, question: str):
        try:
            response = self.chain.invoke({"query": question})
            return response['result']
        except Exception as e:
            if "temperature" in str(e):
                self.llm.temperature = 1
                try:
                    response = self.chain.invoke({"query": question})
                    return response['result']
                except Exception as e2:
                    return f"System Error (Retry failed): {str(e2)}"
            
            return f"System Error: {str(e)}"