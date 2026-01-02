import os
import toml
import random
import time
from dotenv import load_dotenv
from faker import Faker
from langchain_openai import AzureChatOpenAI
from pathlib import Path

# --- REPORTLAB PLATYPUS (Silnik PDF) ---
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY

load_dotenv()
fake = Faker('en_US')

class GraphRAGDataGenerator:
    def __init__(self, config_path: str = "utils/config.toml"):
        if not os.path.exists(config_path):
             os.makedirs("utils", exist_ok=True)
             with open("utils/config.toml", "w") as f:
                 f.write('[generation]\nnum_programmers = 30\nnum_projects = 5\nnum_rfps = 3\noutput_dir = "data"')
             self.config = toml.load(config_path)
        else:
            self.config = toml.load(config_path)
        
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.8,
            max_retries=5,
            request_timeout=60
        )

    def ensure_directories(self):
        """Tworzy foldery, jeśli nie istnieją."""
        dirs = ["data/cvs", "data/rfps"]
        print("\n📁 Checking data directories...")
        for d in dirs:
            path = Path(d)
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
        print("✅ Directories ready.")

    def generate_cv_content(self, name, fixed_role=None, fixed_city=None, fixed_skills=None):
        roles = {
            "Frontend Developer": ["React", "TypeScript", "JavaScript", "Tailwind", "Redux", "Next.js"],
            "Backend Developer": ["Python", "Django", "FastAPI", "PostgreSQL", "Docker", "Java", "Spring Boot"],
            "DevOps Engineer": ["AWS", "Kubernetes", "Terraform", "CI/CD", "Linux", "Azure"],
            "Data Scientist": ["Python", "PyTorch", "Pandas", "NLP", "Machine Learning", "RAG", "LLM"],
            "Security Engineer": ["Penetration Testing", "Network Security", "Python", "OWASP", "Cryptography"]
        }
        
        selected_role = fixed_role if fixed_role else random.choice(list(roles.keys()))
        core_skills = roles[selected_role]
        
        if fixed_skills:
            # Gwarantujemy kluczowe skille dla VIP-ów
            skills_to_use = fixed_skills
            remaining = [s for s in core_skills if s not in fixed_skills]
            if remaining:
                skills_to_use += random.sample(remaining, k=min(len(remaining), 2))
        else:
            skills_to_use = random.sample(core_skills, k=min(len(core_skills), 5))
        
        cities = ["New York", "London", "Berlin", "Remote", "New York", "London"] 
        city = fixed_city if fixed_city else random.choice(cities)
        rate = random.randint(50, 200)

        print(f"   🤖 Generating Content for: {name} ({selected_role})...")

        prompt = f"""
        You are a professional Resume Writer. Create a CV for: {name}.
        Role: {selected_role}.
        
        CRITICAL INSTRUCTIONS:
        1. WRITE IN ENGLISH ONLY.
        2. DO NOT use special characters.
        
        DATA:
        Name: {name}
        Location: {city}
        Rate: ${rate}/h
        
        STRUCTURE:
        NAME: {name}
        ROLE: {selected_role}
        META: Location: {city} | Rate: ${rate}/h
        
        ### SUMMARY
        (2 professional sentences in English.)
        
        ### TECHNICAL SKILLS
        (List exactly: {', '.join(skills_to_use)}, plus 2 others.)
        
        ### PROFESSIONAL EXPERIENCE
        (Company A) | (Dates)
        - (Task description in English)
        
        (Company B) | (Dates)
        - (Task description in English)
        
        ### EDUCATION
        (University), (Degree), (Year)
        """
        response = self.llm.invoke(prompt)
        return response.content

    def create_professional_pdf(self, content, filename, folder):
        output_path = Path(folder) / filename
        doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()
        
        style_name = ParagraphStyle('CV_Name', parent=styles['Heading1'], fontSize=22, textColor=colors.darkblue, spaceAfter=5, alignment=TA_LEFT)
        style_role = ParagraphStyle('CV_Role', parent=styles['Heading2'], fontSize=14, textColor=colors.gray, spaceAfter=2, alignment=TA_LEFT)
        style_meta = ParagraphStyle('CV_Meta', parent=styles['Normal'], fontSize=10, textColor=colors.black, spaceAfter=20, alignment=TA_LEFT)
        style_section = ParagraphStyle('CV_Section', parent=styles['Heading3'], fontSize=12, textColor=colors.darkblue, spaceBefore=15, spaceAfter=5, borderPadding=5, borderWidth=0, borderBottomWidth=1, borderColor=colors.lightgrey)
        style_body = ParagraphStyle('CV_Body', parent=styles['Normal'], fontSize=10, leading=14, alignment=TA_JUSTIFY)
        style_bullet = ParagraphStyle('CV_Bullet', parent=styles['Normal'], fontSize=10, leading=14, leftIndent=20, firstLineIndent=0, spaceAfter=2)

        story = []
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line: continue
            if line.startswith("NAME:"): story.append(Paragraph(line.replace("NAME:", "").strip(), style_name))
            elif line.startswith("ROLE:"): story.append(Paragraph(line.replace("ROLE:", "").strip(), style_role))
            elif line.startswith("META:"): story.append(Paragraph(line.replace("META:", "").strip(), style_meta))
            elif line.startswith("###"): story.append(Paragraph(line.replace("###", "").strip(), style_section))
            elif line.startswith("-") or line.startswith("•"): story.append(Paragraph(f"• {line[1:].strip()}", style_bullet))
            else: story.append(Paragraph(line, style_body))

        doc.build(story)

    def generate_rfps(self, rfp_dir):
        rfps_data = [
            {"filename": "RFP_001_FinTech.pdf", "title": "FinTech AI Platform", "desc": "Secure banking API.", "skills": "Python, Machine Learning, AWS", "team": 5, "loc": "New York"},
            {"filename": "RFP_002_ECom.pdf", "title": "E-Commerce Migration", "desc": "Microservices migration.", "skills": "Java, Spring Boot, Kubernetes", "team": 4, "loc": "London"},
            {"filename": "RFP_003_Health.pdf", "title": "Healthcare Portal", "desc": "Patient portal frontend.", "skills": "React, TypeScript, UX/UI", "team": 4, "loc": "Berlin"}
        ]

        print("\n📄 Checking RFPs...")
        for rfp in rfps_data:
            path = Path(rfp_dir) / rfp['filename']
            if path.exists():
                print(f"  ⏭️  Skipping existing RFP: {rfp['filename']}")
                continue
            try:
                print(f"  🆕 Generating RFP: {rfp['filename']}...")
                content = f"""
                NAME: REQUEST FOR PROPOSAL
                ROLE: {rfp['title']}
                META: Location: {rfp['loc']} | Team Size: {rfp['team']}
                ### PROJECT OVERVIEW
                {rfp['desc']}
                ### REQUIREMENTS
                - Team Size: {rfp['team']} developers
                - Required Skills: {rfp['skills']}
                - Location: {rfp['loc']} (Remote Not Allowed)
                - Budget: Competitive
                """
                self.create_professional_pdf(content, rfp['filename'], rfp_dir)
                print(f"  ✅ Saved RFP: {rfp['filename']}")
            except Exception as e: print(f"❌ Error RFP: {e}")

    def generate_all_data(self):
        self.ensure_directories()
        cv_dir = Path("data/cvs")
        rfp_dir = Path("data/rfps")
        total_target = self.config['generation']['num_programmers']
        
        # --- VIP LIST (Kluczowe dla Demo - muszą być stworzone jeśli ich brak) ---
        vips = [
            {"name": "Jacob Young", "role": "DevOps Engineer", "city": "London", "skills": ["Docker", "AWS", "Python", "Terraform"]},
            {"name": "Amanda Barker", "role": "DevOps Engineer", "city": "New York", "skills": ["Linux", "AWS", "CI/CD"]},
            {"name": "Michael Walker", "role": "Backend Developer", "city": "London", "skills": ["Python", "Django", "PostgreSQL"]}
        ]
        
        print(f"🚀 Data Generation (Target: {total_target} CVs)...")

        # 1. Sprawdzamy VIP-ów (Zawsze muszą istnieć)
        print("\n👑 Ensuring Demo VIPs exist...")
        for vip in vips:
            safe_name = vip["name"].replace(" ", "_")
            filename = f"{safe_name}_CV.pdf"
            path = cv_dir / filename
            
            if path.exists():
                print(f"  ⏭️  VIP OK: {filename}")
            else:
                try:
                    content = self.generate_cv_content(vip["name"], fixed_role=vip["role"], fixed_city=vip["city"], fixed_skills=vip["skills"])
                    self.create_professional_pdf(content, filename, cv_dir)
                    print(f"  ✅ [VIP] Created missing VIP: {filename}")
                except Exception as e:
                    print(f"  ❌ Failed to generate VIP: {vip['name']} - {e}")

        # 2. Dopełniamy resztę do limitu (np. 30)
        current_cvs = list(cv_dir.glob("*.pdf"))
        current_count = len(current_cvs)
        needed = total_target - current_count
        
        if needed <= 0:
            print(f"\n✅ Total count reached ({current_count}/{total_target}). No randoms needed.")
        else:
            print(f"\n🎲 Need {needed} more CVs. Generating randoms...")
            for i in range(needed):
                name = fake.name()
                # Unikaj duplikatów VIP-ów w losowych
                while any(vip['name'] == name for vip in vips):
                    name = fake.name()
                    
                attempts = 0
                success = False
                while attempts < 3 and not success:
                    try:
                        content = self.generate_cv_content(name)
                        safe_name = name.replace(" ", "_")
                        filename = f"{safe_name}_CV.pdf"
                        self.create_professional_pdf(content, filename, cv_dir)
                        print(f"  ✅ [{i+1}/{needed}] Saved Random CV: {filename}")
                        success = True
                        time.sleep(0.5)
                    except Exception as e:
                        attempts += 1
                        time.sleep(2)
                if not success: print(f"  ❌ Failed: {name}")

        # 3. RFPs
        self.generate_rfps(rfp_dir)

if __name__ == "__main__":
    try:
        generator = GraphRAGDataGenerator()
        generator.generate_all_data()
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")