import os
import time
import json
import random
import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_openai import AzureChatOpenAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

load_dotenv()

# ----------------------------
# Pydantic schema (LLM output)
# ----------------------------

class Experience(BaseModel):
    company: str = Field(description="Name of the company")
    role: str = Field(description="Job title/role")
    years: int = Field(description="Years worked there")


class Education(BaseModel):
    university: str = Field(description="Name of the university/college")
    degree: str = Field(description="Degree obtained (e.g., BS, MS)")
    graduation_year: Optional[int] = Field(default=None, description="Graduation year if present")
    gpa: Optional[float] = Field(default=None, description="GPA if present")

class CandidateProfile(BaseModel):
    name: str = Field(description="Full name of the candidate")
    role: str = Field(description="Current primary role (e.g. DevOps Engineer)")
    seniority: str = Field(description="Seniority level: Junior, Mid, Senior, Lead")
    location: str = Field(description="City and Country OR City")
    skills: List[str] = Field(description="List of technical skills")
    certifications: List[str] = Field(description="List of certifications")
    experience: List[Experience] = Field(description="Work history")
    education: List[Education] = Field(description="Education history")
    summary: str = Field(description="Brief professional summary")

    # ✅ Contact info
    email: Optional[str] = Field(default=None, description="Primary email if available")
    phone: Optional[str] = Field(default=None, description="Phone number if available")

    # ✅ NEW: supports your Aggregation query (avg years of experience)
    years_of_experience: Optional[int] = Field(
        default=None,
        description="Total years of professional experience (integer). Prefer META: YearsExperience if present."
    )
    
    # ✅ NEW: timezone for filtering
    timezone: str = Field(
        default="UTC",
        description="Timezone, e.g., PT, ET, CET, GMT, UTC"
    )
    
    # ✅ NEW: graduation year for temporal queries
    graduation_year: int = Field(
        default=2020,
        description="Graduation year from highest education"
    )

    # ✅ NEW: GPA for STUDIED_AT relationship
    gpa: Optional[float] = Field(default=None, description="GPA if present")

# ----------------------------
# LLM & Graph setup
# ----------------------------

llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
)

url = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
username = os.getenv("NEO4J_USERNAME", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password123")

try:
    graph = Neo4jGraph(url=url, username=username, password=password)
except Exception as e:
    print(f"⚠️ Initial connection check failed: {e}")
    graph = None

# ----------------------------
# Helpers
# ----------------------------

def normalize_text(text: str) -> str:
    """
    Cleans raw text:
    - takes only text before comma (e.g. 'London, UK' -> 'London')
    - trims and Title-cases
    - handles Remote/Unknown safely
    """
    if not text or not isinstance(text, str):
        return "Unknown"

    clean = text.strip()
    if not clean:
        return "Unknown"

    # Keep Remote as-is (common in your dataset)
    if clean.lower() == "remote":
        return "Remote"

    # Split by comma (city, country)
    clean = clean.split(",")[0].strip()

    # Avoid strange casing
    return clean.title() if clean else "Unknown"

def extract_years_experience_from_meta(text: str) -> Optional[int]:
    """
    ✅ Deterministic extractor:
    Looks for e.g. "META: ... | YearsExperience: 7 | ..."
    Returns int or None.
    """
    if not text:
        return None

    # robust: allow spaces
    m = re.search(r"YearsExperience\s*:\s*(\d+)", text, re.IGNORECASE)
    if not m:
        return None

    try:
        val = int(m.group(1))
        if 0 <= val <= 60:
            return val
    except Exception:
        return None
    return None

def extract_timezone_from_meta(text: str) -> str:
    """
    ✅ Extract timezone from META line.
    Returns timezone string (e.g., ET, CET, GMT, UTC) or "UTC" as default.
    """
    if not text:
        return "UTC"
    
    m = re.search(r"Timezone\s*:\s*(\w+)", text, re.IGNORECASE)
    if m:
        return m.group(1)
    return "UTC"

def extract_graduation_year_from_meta(text: str) -> Optional[int]:
    """
    ✅ Extract graduation year from EDUCATION section.
    Looks for "GraduationYear: YYYY" pattern.
    """
    if not text:
        return None
    
    m = re.search(r"GraduationYear\s*:\s*(\d{4})", text, re.IGNORECASE)
    if m:
        try:
            year = int(m.group(1))
            if 1990 <= year <= 2030:
                return year
        except Exception:
            pass
    return None

def clean_list(values: List[str]) -> List[str]:
    """Strip, drop empty, unique-preserve-order."""
    seen = set()
    out = []
    for v in values or []:
        if not v or not isinstance(v, str):
            continue
        s = v.strip()
        if not s:
            continue
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        out.append(s)
    return out


def compute_years_from_experience(experiences: List[Experience]) -> int:
    """Aggregate total years from experience entries."""
    total = 0
    for exp in experiences or []:
        try:
            years_val = exp.get("years") if isinstance(exp, dict) else getattr(exp, "years", 0)
            total += int(years_val or 0)
        except Exception:
            continue
    return total


def derive_dates_from_years(years: int) -> Tuple[str, str]:
    """Heuristic start/end date generator from a years count."""
    safe_years = max(0, years)
    end = datetime.now().date() - timedelta(days=random.randint(0, 180))
    start = end - timedelta(days=safe_years * 365)
    return start.isoformat(), end.isoformat()


def random_proficiency() -> int:
    return random.randint(3, 5)


def extract_projects_from_text(text: str) -> List[str]:
    projects: List[str] = []
    for line in (text or "").splitlines():
        if "project" not in line.lower():
            continue
        match = re.search(r"project\s*[:\-]\s*(.+)", line, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name and name not in projects:
                projects.append(name[:80])
    return projects[:3]

# ----------------------------
# LLM extraction
# ----------------------------

def extract_profile_from_cv(text: str):
    parser = JsonOutputParser(pydantic_object=CandidateProfile)
    prompt = ChatPromptTemplate.from_template(
        """
You are an expert HR Data Parser. Extract structured data from the CV text below.

CRITICAL REQUIREMENTS:
1. Extract specific companies worked at (2 entries if possible).
2. Extract universities attended (at least 1 if present).
3. Extract certifications (can be empty list).
4. Infer seniority (Junior/Mid/Senior/Lead) if not explicitly stated.
5. Extract total years of experience as an integer.
   - If META contains "YearsExperience: X" use X.
   - Otherwise infer a reasonable integer (do NOT output floats).
6. Extract timezone if present (e.g., "Timezone: CET").
7. Extract graduation_year if present (e.g., "GraduationYear: 2019"), otherwise infer from context.
   - Otherwise infer a reasonable integer (do NOT output floats).

CV TEXT:
{text}

{format_instructions}
"""
    )
    chain = prompt | llm | parser

    max_retries = 3
    for attempt in range(max_retries):
        try:
            return chain.invoke({
                "text": text,
                "format_instructions": parser.get_format_instructions()
            })
        except Exception as e:
            print(f"   ⚠️ API Error (Attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(3)

    return None

# ----------------------------
# Ingestion
# ----------------------------

def ingest_cvs():
    if not graph:
        print("❌ Graph database connection not established.")
        return

    cv_folder = "data/cvs"
    if not os.path.exists(cv_folder):
        print(f"❌ Folder {cv_folder} does not exist.")
        return

    files = [f for f in os.listdir(cv_folder) if f.endswith(".pdf")]
    print(f"📂 Found {len(files)} CVs. Starting Ingestion with YearsExperience support...")

    for i, filename in enumerate(files, 1):
        path = os.path.join(cv_folder, filename)
        print(f"[{i}/{len(files)}] Processing: {filename}...")

        try:
            loader = PyPDFLoader(path)
            pages = loader.load()
            text = "\n".join([p.page_content for p in pages])

            # ✅ Deterministic: parse META years before LLM (generator guarantees it)
            meta_years = extract_years_experience_from_meta(text)
            meta_timezone = extract_timezone_from_meta(text)
            meta_grad_year = extract_graduation_year_from_meta(text)

            data = extract_profile_from_cv(text)

            if not data:
                print(f"⏩ Skipping {filename} (Empty data).")
                continue

            # sanitize basic fields
            candidate_name = (data.get("name") or "").strip()
            if not candidate_name:
                print(f"⏩ Skipping {filename} (Missing name).")
                continue

            hourly_rate = random.randint(60, 180)

            raw_location = data.get("location", "Remote")
            clean_location = normalize_text(raw_location)

            experiences = data.get("experience", []) or []

            # ✅ years_of_experience priority: META -> LLM -> sum(experience)
            years_of_experience = meta_years
            if years_of_experience is None:
                y = data.get("years_of_experience", None)
                if isinstance(y, int) and 0 <= y <= 60:
                    years_of_experience = y
            total_years_derived = compute_years_from_experience(experiences)
            if years_of_experience is None and total_years_derived:
                years_of_experience = total_years_derived
            
            # ✅ timezone priority: META -> LLM -> UTC
            timezone = meta_timezone or data.get("timezone", "UTC")
            
            # ✅ graduation_year priority: META -> LLM -> None
            graduation_year = meta_grad_year
            if graduation_year is None:
                gy = data.get("graduation_year", None)
                if isinstance(gy, int) and 1990 <= gy <= 2030:
                    graduation_year = gy

            # ✅ Synthetic performance score (0-10): based on years_of_experience and seniority
            seniority = data.get("seniority", "Unknown").lower()
            base_score = 5.0
            if seniority == "senior":
                base_score = 8.5
            elif seniority == "lead":
                base_score = 9.5
            elif seniority == "mid":
                base_score = 7.0
            elif seniority == "junior":
                base_score = 5.5
            
            # Adjust by years of experience (max +1.5)
            yoe_bonus = min(1.5, (years_of_experience or 0) / 10.0) if years_of_experience else 0
            performance_score = min(10.0, base_score + yoe_bonus)
            
            # Mark as TopPerformer if score >= 8.0
            is_top_performer = performance_score >= 8.0

            # Normalize lists
            skills = clean_list(data.get("skills", []))
            certs = clean_list(data.get("certifications", []))
            email = data.get("email")
            phone = data.get("phone")
            # unify years_experience naming for new schema while keeping legacy property
            person_years_experience = years_of_experience

            # 1) Person + Location
            graph.query(
                """
MERGE (p:Person {name: $name})
SET p.id = $name,
    p.role = $role,
    p.seniority = $seniority,
    p.summary = $summary,
    p.location = $raw_location,
    p.rate = $rate,
    p.years_of_experience = $yoe,
    p.years_experience = $yoe,
    p.performance_score = $perf_score,
    p.timezone = $timezone,
    p.graduation_year = $grad_year,
    p.email = $email,
    p.phone = $phone
MERGE (l:Location {name: $clean_loc})
SET l.id = $clean_loc
MERGE (p)-[:LOCATED_IN]->(l)
""",
                {
                    "name": candidate_name,
                    "role": data.get("role", "Unknown"),
                    "seniority": data.get("seniority", "Unknown"),
                    "summary": data.get("summary", ""),
                    "raw_location": raw_location,
                    "rate": hourly_rate,
                    "yoe": person_years_experience,
                    "perf_score": round(performance_score, 2),  # ✅ NEW
                    "timezone": timezone,  # ✅ NEW
                    "grad_year": graduation_year,  # ✅ NEW
                    "clean_loc": clean_location,
                    "email": email,
                    "phone": phone,
                },
            )
            
            # Add TopPerformer label if score >= 8.0
            if is_top_performer:
                graph.query(
                    "MATCH (p:Person {name: $name}) SET p:TopPerformer",
                    {"name": candidate_name}
                )

            # 2) Skills
            for skill in skills:
                rel_years = None
                if person_years_experience:
                    rel_years = max(1, int(person_years_experience * random.uniform(0.3, 1.0)))
                graph.query(
                    """
MATCH (p:Person {name: $person})
MERGE (s:Skill {name: $skill})
SET s.id = $skill
MERGE (p)-[hs:HAS_SKILL]->(s)
SET hs.proficiency = $proficiency,
    hs.years_experience = coalesce($rel_years, hs.years_experience)
""",
                    {
                        "person": candidate_name,
                        "skill": skill,
                        "proficiency": random_proficiency(),
                        "rel_years": rel_years,
                    },
                )

            # 3) Companies (normalized)
            for exp in data.get("experience", []) or []:
                company = normalize_text(exp.get("company", "Unknown"))
                role = (exp.get("role") or "Unknown").strip()
                years = exp.get("years", 0)
                try:
                    years = int(years)
                except Exception:
                    years = 0

                start_date, end_date = derive_dates_from_years(years)

                graph.query(
                    """
MATCH (p:Person {name: $person})
MERGE (c:Company {name: $company})
SET c.id = $company
MERGE (p)-[wa:WORKED_AT {role: $role}]->(c)
SET wa.years = $years,
    wa.start_date = date($start_date),
    wa.end_date = date($end_date)
""",
                    {
                        "person": candidate_name,
                        "company": company,
                        "role": role,
                        "years": years,
                        "start_date": start_date,
                        "end_date": end_date,
                    },
                )

            # 4) Universities (normalized)
            top_level_gpa = data.get("gpa")
            for edu in data.get("education", []) or []:
                uni = normalize_text(edu.get("university", "Unknown"))
                degree = (edu.get("degree") or "Unknown").strip()
                edu_grad_year = edu.get("graduation_year") or graduation_year
                edu_gpa = edu.get("gpa") or top_level_gpa

                graph.query(
                    """
MATCH (p:Person {name: $person})
MERGE (u:University {name: $uni})
SET u.id = $uni
MERGE (p)-[st:STUDIED_AT {degree: $degree}]->(u)
SET st.graduation_year = $grad_year,
    st.gpa = $gpa
""",
                    {
                        "person": candidate_name,
                        "uni": uni,
                        "degree": degree,
                        "grad_year": edu_grad_year,
                        "gpa": edu_gpa,
                    },
                )

            # 5) Certifications
            for cert in certs:
                earned_date = (datetime.now().date() - timedelta(days=random.randint(30, 1800))).isoformat()
                expiry_date = None
                if random.random() > 0.5:
                    expiry_date = (datetime.fromisoformat(earned_date).date() + timedelta(days=365 * random.randint(1, 3))).isoformat()
                score = None
                if random.random() > 0.6:
                    score = random.randint(70, 100)

                graph.query(
                    """
MATCH (p:Person {name: $person})
MERGE (c:Certification {name: $cert})
SET c.id = $cert,
    c.provider = $provider,
    c.expiry_date = CASE WHEN $expiry_date IS NULL THEN NULL ELSE date($expiry_date) END
MERGE (p)-[e:EARNED]->(c)
SET e.date_earned = date($earned_date),
    e.score = $score
""",
                    {
                        "person": candidate_name,
                        "cert": cert,
                        "provider": "Unknown",
                        "earned_date": earned_date,
                        "expiry_date": expiry_date,
                        "score": score,
                    },
                )

            # 6) Optional WORKED_ON links if projects are detected in CV text
            for proj_name in extract_projects_from_text(text):
                proj_start, proj_end = derive_dates_from_years(random.randint(1, 3))
                graph.query(
                    """
MATCH (p:Person {name: $person})
MERGE (proj:Project {title: $title})
SET proj.id = $title,
    proj.status = coalesce(proj.status, 'Historical')
MERGE (p)-[wo:WORKED_ON]->(proj)
SET wo.role = coalesce($role, 'Contributor'),
    wo.contribution = 'CV Extracted',
    wo.start_date = date($start_date),
    wo.end_date = date($end_date)
""",
                    {
                        "person": candidate_name,
                        "title": proj_name,
                        "role": data.get("role"),
                        "start_date": proj_start,
                        "end_date": proj_end,
                    },
                )

        except Exception as e:
            print(f"❌ Critical error: {filename}: {e}")

    print("✅ Full Graph Ingestion Complete (YearsExperience enabled).")

if __name__ == "__main__":
    ingest_cvs()
