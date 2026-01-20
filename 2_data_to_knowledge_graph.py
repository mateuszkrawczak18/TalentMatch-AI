import os
import time
import json
import random 
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
    certifications: List[str] = Field(description="List of certifications")
    experience: List[Experience] = Field(description="Work history")
    education: List[Education] = Field(description="Education history")
    summary: str = Field(description="Brief professional summary")

# Konfiguracja LLM
llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    temperature=1 
)

url = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
username = os.getenv("NEO4J_USERNAME", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password123")

try:
    graph = Neo4jGraph(url=url, username=username, password=password)
except Exception as e:
    print(f"⚠️ Initial connection check failed: {e}")
    graph = None

# --- FUNKCJA NORMALIZUJĄCA (FIX DLA LONDYNU) ---
def normalize_text(text: str) -> str:
    """
    Czyści surowy tekst z LLM:
    1. Usuwa kraj po przecinku (np. 'London, UK' -> 'London').
    2. Usuwa zbędne spacje i standaryzuje wielkość liter.
    """
    if not text: return "Unknown"
    # Rozdzielamy po przecinku i bierzemy tylko pierwszy człon (miasto)
    clean = text.split(',')[0]
    return clean.strip().title()

def extract_profile_from_cv(text: str):
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
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return chain.invoke({"text": text, "format_instructions": parser.get_format_instructions()})
        except Exception as e:
            print(f"   ⚠️ API Error (Attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(5) 
    return None

def ingest_cvs():
    if not graph:
        print("❌ Graph database connection not established.")
        return

    cv_folder = "data/cvs"
    if not os.path.exists(cv_folder):
        print(f"❌ Folder {cv_folder} does not exist.")
        return

    files = [f for f in os.listdir(cv_folder) if f.endswith(".pdf")]
    print(f"📂 Found {len(files)} CVs. Starting Ingestion with Normalization...")
    
    for i, filename in enumerate(files, 1):
        path = os.path.join(cv_folder, filename)
        print(f"[{i}/{len(files)}] Processing: {filename}...")
        
        try:
            loader = PyPDFLoader(path)
            pages = loader.load()
            text = "\n".join([p.page_content for p in pages])
            
            data = extract_profile_from_cv(text)
            
            if data:
                hourly_rate = random.randint(60, 180)
                
                # --- NORMALIZACJA KLUCZOWYCH PÓL ---
                clean_location = normalize_text(data.get("location", "Remote"))
                candidate_name = data["name"].strip()

                # 1. Tworzenie węzła Person i Location (ZNORMALIZOWANEGO)
                graph.query("""
                    MERGE (p:Person {name: $name})
                    SET p.id = $name,  
                        p.role = $role, 
                        p.seniority = $seniority, 
                        p.summary = $summary,
                        p.location = $location,
                        p.rate = $rate
                    MERGE (l:Location {name: $clean_loc})
                    SET l.id = $clean_loc
                    MERGE (p)-[:LOCATED_IN]->(l)
                """, {
                    "name": candidate_name,
                    "role": data["role"],
                    "seniority": data["seniority"],
                    "summary": data["summary"],
                    "location": data["location"], # zostawiamy oryginał jako atrybut
                    "rate": hourly_rate,
                    "clean_loc": clean_location # znormalizowany węzeł
                })
                
                # 2. Tworzenie węzłów Skill
                for skill in data.get("skills", []):
                    graph.query("""
                        MATCH (p:Person {name: $person})
                        MERGE (s:Skill {name: $skill})
                        SET s.id = $skill
                        MERGE (p)-[:HAS_SKILL]->(s)
                    """, {"person": candidate_name, "skill": skill.strip()})
                    
                # 3. Tworzenie węzłów Company (ZNORMALIZOWANYCH)
                for exp in data.get("experience", []):
                    clean_company = normalize_text(exp["company"])
                    graph.query("""
                        MATCH (p:Person {name: $person})
                        MERGE (c:Company {name: $company})
                        SET c.id = $company
                        MERGE (p)-[:WORKED_AT {role: $role, years: $years}]->(c)
                    """, {
                        "person": candidate_name, 
                        "company": clean_company, 
                        "role": exp["role"], 
                        "years": exp["years"]
                    })

                # 4. Tworzenie węzłów University (ZNORMALIZOWANYCH)
                for edu in data.get("education", []):
                    clean_uni = normalize_text(edu["university"])
                    graph.query("""
                        MATCH (p:Person {name: $person})
                        MERGE (u:University {name: $uni})
                        SET u.id = $uni
                        MERGE (p)-[:STUDIED_AT {degree: $degree}]->(u)
                    """, {
                        "person": candidate_name, 
                        "uni": clean_uni, 
                        "degree": edu["degree"]
                    })

                # 5. Tworzenie węzłów Certification
                for cert in data.get("certifications", []):
                    graph.query("""
                        MATCH (p:Person {name: $person})
                        MERGE (c:Certification {name: $cert})
                        SET c.id = $cert
                        MERGE (p)-[:HAS_CERT]->(c)
                    """, {"person": candidate_name, "cert": cert.strip()})
            else:
                print(f"⏩ Skipping {filename} (Empty data).")
                
        except Exception as e:
            print(f"❌ Critical error: {filename}: {e}")

    print("✅ Full Graph Ingestion Complete. All locations unified.")

if __name__ == "__main__":
    ingest_cvs()