import os
import glob
import time
from typing import List
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import AzureChatOpenAI
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_neo4j import Neo4jGraph
from langchain_core.documents import Document

# Ładowanie zmiennych środowiskowych
load_dotenv()

def process_cvs_to_graph():
    print("🚀 STARTING: Knowledge Graph Construction Pipeline")
    print("="*60)

    # 1. Połączenie z Neo4j
    try:
        graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD")
        )
        print("✅ Connected to Neo4j Database.")
    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
        return

    # 2. Czyszczenie starej bazy (Reset)
    print("🧹 Cleaning old graph data (Full Reset)...")
    try:
        graph.query("MATCH (n) DETACH DELETE n")
        # Usuwamy indeksy (opcjonalnie, dla pewności)
        try:
            graph.query("CALL apoc.schema.assert({}, {})")
        except:
            pass # Ignorujemy błąd jeśli nie ma APOC
        print("✅ Database is clean.")
    except Exception as e:
        print(f"⚠️ Warning during cleaning: {e}")

    # 3. Konfiguracja LLM (Azure OpenAI)
    llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
        api_version=os.getenv("OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        temperature=0 
    )

    # 4. Konfiguracja Transformera (POPRAWKA TUTAJ)
    # Usunęliśmy "id" z node_properties, bo jest zarezerwowane przez bibliotekę.
    print("⚙️  Configuring LLM Graph Transformer...")
    llm_transformer = LLMGraphTransformer(
        llm=llm,
        allowed_nodes=[
            "Person", 
            "Skill", 
            "Location", 
            "University", 
            "Role", 
            "Company"
        ],
        allowed_relationships=[
            "HAS_SKILL", 
            "LOCATED_IN", 
            "EDUCATED_AT", 
            "WORKED_AT", 
            "HAS_ROLE",
            "AVAILABLE_IN",
            "REQUIRED_SKILL"
        ],
        # Zostawiamy tylko "name" - biblioteka sama ogarnie ID wewnętrznie
        node_properties=["name"]
    )

    # 5. Wczytywanie plików PDF
    pdf_files = glob.glob("data/cvs/*.pdf")
    if not pdf_files:
        print("❌ No PDF files found in data/cvs/")
        return

    print(f"📂 Found {len(pdf_files)} CVs. Loading content...")
    
    all_documents = []
    for pdf_file in pdf_files:
        try:
            loader = PyPDFLoader(pdf_file)
            docs = loader.load()
            for d in docs:
                d.metadata["source"] = os.path.basename(pdf_file)
            all_documents.extend(docs)
        except Exception as e:
            print(f"⚠️ Error loading {pdf_file}: {e}")

    print(f"   Loaded {len(all_documents)} pages total.")

    # 6. Przetwarzanie wsadowe (Batch Processing)
    batch_size = 5
    total_docs = len(all_documents)
    
    print("\n🧠 Extracting Entities & Relationships (This may take time)...")
    
    for i in range(0, total_docs, batch_size):
        batch = all_documents[i:i+batch_size]
        current_batch_num = (i // batch_size) + 1
        total_batches = (total_docs + batch_size - 1) // batch_size
        
        print(f"   Processing Batch {current_batch_num}/{total_batches} ({len(batch)} pages)...")
        
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                graph_documents = llm_transformer.convert_to_graph_documents(batch)
                
                if graph_documents:
                    graph.add_graph_documents(graph_documents)
                    print(f"      ✅ Batch {current_batch_num} saved to Neo4j.")
                else:
                    print(f"      ⚠️ Batch {current_batch_num} resulted in empty graph data.")
                
                break 
                
            except Exception as e:
                retry_count += 1
                print(f"      ❌ Error in Batch {current_batch_num} (Attempt {retry_count}/{max_retries}): {e}")
                time.sleep(5)
        
        if retry_count == max_retries:
            print(f"      ⛔ Skipping Batch {current_batch_num} after multiple failures.")

    # 7. Finalizacja
    print("\n" + "="*60)
    print("🎉 KNOWLEDGE GRAPH BUILT SUCCESSFULLY!")
    print("="*60)
    
    try:
        node_count = graph.query("MATCH (n) RETURN count(n) as c")[0]['c']
        rel_count = graph.query("MATCH ()-[r]->() RETURN count(r) as c")[0]['c']
        print(f"📊 Stats: {node_count} Nodes | {rel_count} Relationships created.")
    except:
        pass

if __name__ == "__main__":
    process_cvs_to_graph()