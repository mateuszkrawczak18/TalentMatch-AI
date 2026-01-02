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

        # 2. Model LLM (Wersja Stabilna)
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0,
            max_retries=5,       # Ponawianie przy błędach sieci
            request_timeout=60   # Dłuższy czas na odpowiedź
        )

        # 3. PROMPT GENERUJĄCY KOD CYPHER
        # Używamy {{ }} dla właściwości w schemacie
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
        
        Context:
        - Current Date: {today}
        
        Instructions:
        1. Use ONLY the provided schema.
        2. Do not include preambles.
        3. For "Availability", check if a person is NOT assigned to a Project.
        4. Keep queries concise.
        5. CRITICAL: When listing people based on criteria (e.g. Senior Python), ALWAYS return the proving attributes (p.seniority, s.name, p.rate) in the result so I can verify the match.
        
        Examples:
        
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
            input_variables=["question", "today"]
        )

        # 4. PROMPT QA
        qa_template = """You are an intelligent IT Staffing Consultant.
        
        Context (Database Results):
        {context}
        
        User Question:
        {question}
        
        Instructions:
        - Answer based ONLY on the provided context.
        - If the user asks for specific roles/skills and the context contains data, assume it is correct.
        - Format lists of people nicely (bullet points).
        - If the context is empty, say "No matching candidates found."
        
        Answer:"""
        
        qa_prompt = PromptTemplate(
            template=qa_template, 
            input_variables=["context", "question"]
        )

        self.chain = GraphCypherQAChain.from_llm(
            self.llm,
            graph=self.graph,
            verbose=True,
            cypher_prompt=cypher_prompt,
            qa_prompt=qa_prompt,
            allow_dangerous_requests=True
        )

    def ask(self, question: str):
        try:
            today_str = date.today().isoformat()
            response = self.chain.invoke({"query": question, "today": today_str})
            return response['result']
        except Exception as e:
            error_msg = str(e)
            if "Connection error" in error_msg:
                return "⚠️ Network Issue: Could not connect to Azure OpenAI. Please try again."
            return f"System Error: {error_msg}"