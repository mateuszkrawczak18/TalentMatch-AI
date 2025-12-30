import os
import sys
from dotenv import load_dotenv

# Próba importu kluczowych bibliotek
try:
    import neo4j
    from langchain_openai import AzureChatOpenAI, ChatOpenAI
    print("✅ Libraries: Imports successful.")
except ImportError as e:
    print(f"❌ Libraries: Import failed. Did you run 'pip install -r requirements.txt'? Error: {e}")
    sys.exit(1)

# Ładowanie zmiennych środowiskowych
load_dotenv()

def check_env_vars():
    required_vars = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"]
    # Sprawdzamy czy mamy klucz OpenAI (zwykły lub Azure)
    has_openai = os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
    
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print(f"❌ Environment: Missing variables in .env: {', '.join(missing)}")
    elif not has_openai:
        print("❌ Environment: Missing OPENAI_API_KEY or AZURE_OPENAI_API_KEY")
    else:
        print("✅ Environment: Variables loaded.")

def check_neo4j_connection():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password123")
    
    try:
        driver = neo4j.GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        print(f"✅ Neo4j: Connected successfully to {uri}")
        driver.close()
    except Exception as e:
        print(f"❌ Neo4j: Connection failed. Is Docker running? Error: {e}")

if __name__ == "__main__":
    print("--- 🛠️  TalentMatch AI Setup Check 🛠️  ---\n")
    check_env_vars()
    check_neo4j_connection()
    print("\n----------------------------------------")