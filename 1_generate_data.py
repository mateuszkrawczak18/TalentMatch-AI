import os
import re
import toml
import random
import time
from pathlib import Path
from typing import Optional, List, Dict

from dotenv import load_dotenv
from faker import Faker
from langchain_openai import AzureChatOpenAI

# --- REPORTLAB ---
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY

load_dotenv()

fake = Faker("en_US")

# Optional deterministic generation
SEED = os.getenv("DATA_SEED")
if SEED:
    try:
        seed_int = int(SEED)
        random.seed(seed_int)
        Faker.seed(seed_int)
    except Exception:
        pass


def _safe_filename(name: str) -> str:
    name = name.strip().replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9_\-]", "", name)
    return name


class GraphRAGDataGenerator:
    def __init__(self, config_path: str = "utils/config.toml"):
        self.config_path = config_path
        self._ensure_config()
        
        # Deterministic generation via seed
        seed = int(self.config.get("generation", {}).get("seed", 42))
        random.seed(seed)
        Faker.seed(seed)


        # Slightly lower temp for repeatable, parse-friendly CVs
        # (You can raise if you want more variety)
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            max_retries=5,
            request_timeout=60,
        )

    def _ensure_config(self):
        Path("utils").mkdir(parents=True, exist_ok=True)

        if not os.path.exists(self.config_path):
            default = {
                "generation": {
                    "seed": 42,
                    "num_programmers": 30,
                    "num_projects": 5,
                    "num_rfps": 3,
                    "output_dir": "data",
                }
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                toml.dump(default, f)

        self.config = toml.load(self.config_path)
        if "generation" not in self.config:
            self.config["generation"] = {}
        self.config["generation"].setdefault("num_programmers", 30)
        self.config["generation"].setdefault("num_rfps", 3)
        self.config["generation"].setdefault("output_dir", "data")

    def ensure_directories(self):
        output_dir = Path(self.config["generation"]["output_dir"])
        dirs = [output_dir / "cvs", output_dir / "rfps"]
        print("\n📁 Checking data directories...")
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        print("✅ Directories ready.")

    # -------------------------
    # CV GENERATION
    # -------------------------

    def generate_cv_content(
        self,
        name: str,
        fixed_role: Optional[str] = None,
        fixed_city: Optional[str] = None,
        fixed_skills: Optional[List[str]] = None,
    ) -> str:
        """
        Generates CV text that is:
        - consistent, easy to parse
        - includes: NAME, ROLE, META, SUMMARY, TECHNICAL SKILLS, CERTIFICATIONS, EXPERIENCE, EDUCATION
        """

        roles: Dict[str, List[str]] = {
            "Frontend Developer": ["React", "TypeScript", "JavaScript", "Tailwind", "Redux", "Next.js"],
            "Backend Developer": ["Python", "Django", "FastAPI", "PostgreSQL", "Docker", "Java", "Spring Boot"],
            "DevOps Engineer": ["AWS", "Kubernetes", "Terraform", "CI/CD", "Linux", "Azure"],
            "Data Scientist": ["Python", "PyTorch", "Pandas", "NLP", "Machine Learning", "RAG", "LLM"],
            "Security Engineer": ["Penetration Testing", "Network Security", "Python", "OWASP", "Cryptography"],
        }

        selected_role = fixed_role or random.choice(list(roles.keys()))
        core_skills = roles[selected_role][:]

        # Skills: keep fixed_skills intact, add some from core_skills
        if fixed_skills:
            skills_to_use = list(dict.fromkeys([s.strip() for s in fixed_skills if s.strip()]))  # unique
            remaining = [s for s in core_skills if s not in skills_to_use]
            if remaining:
                skills_to_use += random.sample(remaining, k=min(len(remaining), 3))
        else:
            skills_to_use = random.sample(core_skills, k=min(len(core_skills), 6))

        cities = ["New York", "London", "Berlin", "Remote", "San Francisco", "Toronto"]
        city = fixed_city or random.choice(cities)

        # Timezone mapping for temporal queries
        tz_map = {"New York": "ET", "London": "GMT", "Berlin": "CET", "Remote": "UTC", "San Francisco": "PT", "Toronto": "ET"}
        timezone = tz_map.get(city, "UTC")
        
        # Graduation year for temporal analysis
        grad_year = random.randint(2012, 2024)
        
        # Useful for aggregation queries (your BI engine reads years_of_experience)
        years_exp = random.randint(1, 12)
        seniority = (
            "Junior" if years_exp <= 2
            else "Mid" if years_exp <= 5
            else "Senior" if years_exp <= 9
            else "Lead"
        )

        # Rates for later aggregation queries
        rate = random.randint(50, 200)

        # Certifications (help counting/filtering queries)
        cert_pool = [
            "AWS Certified Solutions Architect",
            "AWS Certified Developer",
            "CKA Kubernetes Administrator",
            "Azure Fundamentals",
            "Scrum Master",
            "CompTIA Security+",
        ]
        certs = random.sample(cert_pool, k=random.randint(0, 2))
        
        # Real company names for realistic CVs
        company_pool = [
            "Google", "Microsoft", "Amazon", "Meta", "Apple", "Netflix", "Adobe",
            "Spotify", "Airbnb", "Uber", "Lyft", "Twitter", "LinkedIn", "Salesforce",
            "Oracle", "IBM", "Cisco", "Intel", "NVIDIA", "Tesla", "SpaceX",
        ]
        company_1 = random.choice(company_pool)
        company_2 = random.choice([c for c in company_pool if c != company_1])
        
        # University names
        university_pool = [
            "MIT", "Stanford University", "UC Berkeley", "Harvard University",
            "Carnegie Mellon University", "Georgia Tech", "University of Washington",
            "Cornell University", "Columbia University", "Princeton University",
        ]
        university = random.choice(university_pool)

        print(f"   🤖 Generating Content for: {name} ({selected_role}, {seniority})...")

        # IMPORTANT: Keep format stable: “NAME:”, “ROLE:”, “META:” then sections
        prompt = f"""
You are a professional Resume Writer. Generate a clean, structured CV in ENGLISH.
Do NOT add markdown code fences. Use exactly the headings below.

STRUCTURE (MUST FOLLOW EXACTLY):
NAME: {name}
ROLE: {selected_role}
META: Location: {city} | Timezone: {timezone} | Rate: ${rate}/h | YearsExperience: {years_exp} | Seniority: {seniority}

### SUMMARY
Write 2 concise sentences.

### TECHNICAL SKILLS
List 8-10 skills as comma-separated values.
You MUST include: {", ".join(skills_to_use)}.
Add a few relevant extras.

### CERTIFICATIONS
If none, write: None
Otherwise list as comma-separated values.

### PROFESSIONAL EXPERIENCE
Write exactly 2 entries in this exact pattern:
Company: {company_1} | Role: {selected_role} | Years: {random.randint(2, 5)}
- Bullet sentence 1
- Bullet sentence 2

Company: {company_2} | Role: {selected_role} | Years: {random.randint(1, 4)}
- Bullet sentence 1
- Bullet sentence 2

### EDUCATION
Write 1 entry:
University: {university} | Degree: {random.choice(['BS', 'MS'])} | GraduationYear: {grad_year}

CONSTRAINTS:
- Keep it realistic, consistent and parse-friendly.
- Avoid unusual symbols.
- Use EXACTLY the company names provided: {company_1} and {company_2}.
- Use EXACTLY the university name provided: {university}.
- Certifications must match: {", ".join(cert_pool)} (or None).
CERTIFICATIONS TO USE (if any): {", ".join(certs) if certs else "None"}
"""

        # Retry with basic validation
        max_retries = 3
        backoff = 2
        last = None
        for attempt in range(max_retries):
            try:
                response = self.llm.invoke(prompt)
                text = (response.content or "").strip()
                last = text

                if text.startswith("NAME:") and "### TECHNICAL SKILLS" in text and "### PROFESSIONAL EXPERIENCE" in text:
                    return text

            except Exception:
                pass

            time.sleep(backoff)
            backoff *= 2

        # Fallback minimal CV if LLM fails
        fallback = f"""NAME: {name}
ROLE: {selected_role}
META: Location: {city} | Timezone: {timezone} | Rate: ${rate}/h | YearsExperience: {years_exp} | Seniority: {seniority}

### SUMMARY
Experienced {seniority} {selected_role} with a strong track record of delivery. Focused on quality, reliability and teamwork.

### TECHNICAL SKILLS
{", ".join(skills_to_use)}

### CERTIFICATIONS
None

### PROFESSIONAL EXPERIENCE
Company: {company_1} | Role: {selected_role} | Years: 2
- Delivered features and improvements.
- Collaborated with cross-functional teams.

Company: {company_2} | Role: {selected_role} | Years: 3
- Built and maintained systems.
- Improved reliability and performance.

### EDUCATION
University: {university} | Degree: BS | GraduationYear: {grad_year}
"""
        return last or fallback

    def create_professional_pdf(self, content: str, filename: str, folder: Path):
        output_path = folder / filename
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50,
        )
        styles = getSampleStyleSheet()

        style_name = ParagraphStyle(
            "CV_Name",
            parent=styles["Heading1"],
            fontSize=22,
            textColor=colors.darkblue,
            spaceAfter=5,
            alignment=TA_LEFT,
        )
        style_role = ParagraphStyle(
            "CV_Role",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=colors.gray,
            spaceAfter=2,
            alignment=TA_LEFT,
        )
        style_meta = ParagraphStyle(
            "CV_Meta",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.black,
            spaceAfter=20,
            alignment=TA_LEFT,
        )
        style_section = ParagraphStyle(
            "CV_Section",
            parent=styles["Heading3"],
            fontSize=12,
            textColor=colors.darkblue,
            spaceBefore=15,
            spaceAfter=5,
            borderPadding=5,
            borderWidth=0,
            borderBottomWidth=1,
            borderColor=colors.lightgrey,
        )
        style_body = ParagraphStyle(
            "CV_Body",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
        )
        style_bullet = ParagraphStyle(
            "CV_Bullet",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            leftIndent=20,
            firstLineIndent=0,
            spaceAfter=2,
        )

        story = []
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("NAME:"):
                story.append(Paragraph(line.replace("NAME:", "").strip(), style_name))
            elif line.startswith("ROLE:"):
                story.append(Paragraph(line.replace("ROLE:", "").strip(), style_role))
            elif line.startswith("META:"):
                story.append(Paragraph(line.replace("META:", "").strip(), style_meta))
            elif line.startswith("###"):
                story.append(Paragraph(line.replace("###", "").strip(), style_section))
            elif line.startswith("-") or line.startswith("•"):
                story.append(Paragraph(f"• {line[1:].strip()}", style_bullet))
            else:
                story.append(Paragraph(line, style_body))

        doc.build(story)

    # -------------------------
    # RFP GENERATION
    # -------------------------

    def generate_rfps(self, rfp_dir: Path):
        rfps_data = [
            {
                "filename": "RFP_001_FinTech.pdf",
                "title": "FinTech AI Platform",
                "desc": "Build a secure banking platform with ML-driven fraud detection and an API layer.",
                "skills": ["Python", "Machine Learning", "AWS", "Security"],
                "team": 5,
                "loc": "New York",
                "allocation": 1.0,
                "budget_per_hour": 650,  # for scenario questions
                "duration_months": 3,
            },
            {
                "filename": "RFP_002_ECom.pdf",
                "title": "E-Commerce Migration",
                "desc": "Migrate a monolith to microservices and modernize CI/CD.",
                "skills": ["Java", "Spring Boot", "Kubernetes", "Docker"],
                "team": 4,
                "loc": "London",
                "allocation": 1.0,
                "budget_per_hour": 520,
                "duration_months": 4,
            },
            {
                "filename": "RFP_003_Health.pdf",
                "title": "Healthcare Portal",
                "desc": "Build a patient portal frontend with strong UX and accessibility standards.",
                "skills": ["React", "TypeScript", "UX/UI"],
                "team": 4,
                "loc": "Berlin",
                "allocation": 0.75,
                "budget_per_hour": 480,
                "duration_months": 3,
            },
        ]

        target = int(self.config["generation"].get("num_rfps", 3))
        rfps_data = rfps_data[:target]

        print("\n📄 Checking RFPs...")
        for rfp in rfps_data:
            path = rfp_dir / rfp["filename"]
            if path.exists():
                print(f"  ⏭️  Skipping existing RFP: {rfp['filename']}")
                continue

            try:
                print(f"  🆕 Generating RFP: {rfp['filename']}...")

                content = f"""NAME: REQUEST FOR PROPOSAL
ROLE: {rfp['title']}
META: Location: {rfp['loc']} | Team Size: {rfp['team']} | DurationMonths: {rfp['duration_months']} | AllocationNeeded: {rfp['allocation']} | BudgetPerHour: ${rfp['budget_per_hour']}

### PROJECT OVERVIEW
{rfp['desc']}

### REQUIREMENTS
- Team Size: {rfp['team']}
- Required Skills: {", ".join(rfp['skills'])}
- Location: {rfp['loc']} (Remote Not Allowed)
- Allocation Needed: {rfp['allocation']}
- Budget Per Hour (Team): ${rfp['budget_per_hour']}
- Duration: {rfp['duration_months']} months
"""
                self.create_professional_pdf(content, rfp["filename"], rfp_dir)
                print(f"  ✅ Saved RFP: {rfp['filename']}")
            except Exception as e:
                print(f"❌ Error RFP: {e}")

    # -------------------------
    # MAIN
    # -------------------------

    def generate_all_data(self):
        self.ensure_directories()

        output_dir = Path(self.config["generation"]["output_dir"])
        cv_dir = output_dir / "cvs"
        rfp_dir = output_dir / "rfps"

        total_target = int(self.config["generation"]["num_programmers"])

        # VIPs: stable for demo scenarios
        vips = [
            {
                "name": "Jacob Young",
                "role": "DevOps Engineer",
                "city": "London",
                "skills": ["Docker", "AWS", "Python", "Terraform", "Kubernetes"],
            },
            {
                "name": "Amanda Barker",
                "role": "DevOps Engineer",
                "city": "New York",
                "skills": ["Linux", "AWS", "CI/CD", "Terraform"],
            },
            {
                "name": "Michael Walker",
                "role": "Backend Developer",
                "city": "London",
                "skills": ["Python", "Django", "PostgreSQL", "FastAPI"],
            },
        ]

        print(f"🚀 Data Generation (Target: {total_target} CVs)...")

        # 1) Ensure VIPs exist
        print("\n👑 Ensuring Demo VIPs exist...")
        for vip in vips:
            safe = _safe_filename(vip["name"])
            filename = f"{safe}_CV.pdf"
            path = cv_dir / filename
            if path.exists():
                print(f"  ⏭️  VIP OK: {filename}")
                continue

            try:
                content = self.generate_cv_content(
                    vip["name"],
                    fixed_role=vip["role"],
                    fixed_city=vip["city"],
                    fixed_skills=vip["skills"],
                )
                self.create_professional_pdf(content, filename, cv_dir)
                print(f"  ✅ [VIP] Created: {filename}")
            except Exception as e:
                print(f"  ❌ Failed VIP: {vip['name']} - {e}")

        # 2) Fill up to target (include VIPs in count)
        existing = list(cv_dir.glob("*.pdf"))
        current_count = len(existing)
        needed = total_target - current_count

        if needed <= 0:
            print(f"\n✅ Total count reached ({current_count}/{total_target}). No randoms needed.")
        else:
            print(f"\n🎲 Need {needed} more CVs. Generating randoms...")

            vip_names = {v["name"] for v in vips}
            created = 0
            attempts_global = 0

            while created < needed and attempts_global < needed * 5:
                attempts_global += 1
                name = fake.name()

                # avoid VIP duplicates
                if name in vip_names:
                    continue

                safe = _safe_filename(name)
                filename = f"{safe}_CV.pdf"
                path = cv_dir / filename

                # avoid collision on filename
                if path.exists():
                    continue

                try:
                    content = self.generate_cv_content(name)
                    # very light sanity check
                    if not content or "NAME:" not in content or "ROLE:" not in content:
                        continue

                    self.create_professional_pdf(content, filename, cv_dir)
                    created += 1
                    print(f"  ✅ [{created}/{needed}] Saved Random CV: {filename}")
                    time.sleep(0.2)
                except Exception:
                    time.sleep(1)

            if created < needed:
                print(f"⚠️ Generated only {created}/{needed} random CVs (LLM/timeouts).")

        # 3) Generate RFPs
        self.generate_rfps(rfp_dir)


if __name__ == "__main__":
    try:
        generator = GraphRAGDataGenerator()
        generator.generate_all_data()
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
