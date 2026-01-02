import os
import time
import json
import random  # <--- WAŻNE: Import do losowania stawek
from typing import List
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_openai import AzureChatOpenAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

load_dotenv()

# --- KONFIGURACJA ZGODNA Z PRD ---

# Definicja struktur danych (Pydantic) dla precyzyjnej ekstrakcji
class Experience(BaseModel):
    company: str = Field(description="Name of the company")
    role: str = Field(description="Job title/role")
    years: int = Field(description="Years worked there")

class Education(BaseModel):
    university: str = Field(description="Name of the university/college")
    degree: str = Field(description="Degree obtained (e.g., BS, MS)")

class CandidateProfile(BaseModel):
    name: str = Field(description="Full name of the candidate")
    role: str = Field(description="Current primary role (e.g. DevOps Engineer)")
    seniority: str = Field(description="Seniority level: Junior, Mid, Senior, Lead")
    location: str = Field(description="City and Country")
    skills: List[str] = Field(description="List of technical skills")
    certifications: List[str] = Field(description="List of certifications (e.g. AWS Solutions Architect)")
    experience: List[Experience] = Field(description="Work history")
    education: List[Education] = Field(description="Education history")
    summary: str = Field(description="Brief professional summary")

# Konfiguracja LLM
llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    temperature=0
)

# Konfiguracja Neo4j
url = os.getenv("NEO4J_URI", "bolt://localhost:7687")
username = os.getenv("NEO4J_USERNAME", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password123")
graph = Neo4jGraph(url=url, username=username, password=password)

def extract_profile_from_cv(text: str):
    """Używa LLM do ekstrakcji profilu z mechanizmem RETRY (ponawiania)."""
    parser = JsonOutputParser(pydantic_object=CandidateProfile)
    
    prompt = ChatPromptTemplate.from_template(
        """
        You are an expert HR Data Parser. Extract structured data from the CV text below.
        
        CRITICAL REQUIREMENTS:
        1. Extract specific companies worked at.
        2. Extract universities attended.
        3. Extract certifications.
        4. Infer seniority (Junior/Mid/Senior) if not explicitly stated.
        
        CV TEXT:
        {text}
        
        {format_instructions}
        """
    )
    
    chain = prompt | llm | parser
    
    # MECHANIZM RETRY (Naprawia Connection Error)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return chain.invoke({"text": text, "format_instructions": parser.get_format_instructions()})
        except Exception as e:
            print(f"   ⚠️ API Error (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print("   ⏳ Retrying in 5 seconds...")
                time.sleep(5) 
            else:
                print("   ❌ Failed after 3 attempts.")
                return None

def ingest_cvs():
    cv_folder = "data/cvs"
    if not os.path.exists(cv_folder):
        print(f"❌ Folder {cv_folder} does not exist. Run 1_generate_data.py first.")
        return

    files = [f for f in os.listdir(cv_folder) if f.endswith(".pdf")]
    print(f"📂 Found {len(files)} CVs. Starting Ingestion (Text-based IDs + Rates)...")
    
    for i, filename in enumerate(files, 1):
        path = os.path.join(cv_folder, filename)
        print(f"[{i}/{len(files)}] Processing: {filename}...")
        
        try:
            loader = PyPDFLoader(path)
            pages = loader.load()
            text = "\n".join([p.page_content for p in pages])
            
            data = extract_profile_from_cv(text)
            
            if data:
                # [FIX] Generujemy losową stawkę godzinową (60-180 USD)
                # To jest kluczowe dla Scenario 1 (Average Rate)
                hourly_rate = random.randint(60, 180)

                # 1. Tworzenie węzła Person i Location
                graph.query("""
                    MERGE (p:Person {name: $name})
                    SET p.id = $name,  
                        p.role = $role, 
                        p.seniority = $seniority, 
                        p.summary = $summary,
                        p.location = $location,
                        p.rate = $rate  // <--- ZAPISUJEMY STAWKĘ W BAZIE
                    MERGE (l:Location {name: $location})
                    SET l.id = $location
                    MERGE (p)-[:LOCATED_IN]->(l)
                """, {**data, "rate": hourly_rate})
                
                # 2. Tworzenie węzłów Skill
                for skill in data.get("skills", []):
                    graph.query("""
                        MATCH (p:Person {name: $person})
                        MERGE (s:Skill {name: $skill})
                        SET s.id = $skill
                        MERGE (p)-[:HAS_SKILL]->(s)
                    """, {"person": data["name"], "skill": skill})
                    
                # 3. Tworzenie węzłów Company
                for exp in data.get("experience", []):
                    graph.query("""
                        MATCH (p:Person {name: $person})
                        MERGE (c:Company {name: $company})
                        SET c.id = $company
                        MERGE (p)-[:WORKED_AT {role: $role, years: $years}]->(c)
                    """, {"person": data["name"], "company": exp["company"], "role": exp["role"], "years": exp["years"]})

                # 4. Tworzenie węzłów University
                for edu in data.get("education", []):
                    graph.query("""
                        MATCH (p:Person {name: $person})
                        MERGE (u:University {name: $uni})
                        SET u.id = $uni
                        MERGE (p)-[:STUDIED_AT {degree: $degree}]->(u)
                    """, {"person": data["name"], "uni": edu["university"], "degree": edu["degree"]})

                # 5. Tworzenie węzłów Certification
                for cert in data.get("certifications", []):
                    graph.query("""
                        MATCH (p:Person {name: $person})
                        MERGE (c:Certification {name: $cert})
                        SET c.id = $cert
                        MERGE (p)-[:HAS_CERT]->(c)
                    """, {"person": data["name"], "cert": cert})
            else:
                print(f"⏩ Skipping {filename} (Empty data returned).")
                
        except Exception as e:
            print(f"❌ Critical error processing file {filename}: {e}")

    print("✅ Full Graph Ingestion Complete.")

if __name__ == "__main__":
    ingest_cvs()