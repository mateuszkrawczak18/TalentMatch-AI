import os
import glob
import time
from dotenv import load_dotenv

# Używamy sprawdzonych modułów (Core + Community)
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()

class NaiveRAGSystem:
    def __init__(self):
        # Wyciszamy logi konfiguracji, żeby nie śmiecić w benchmarku
        # 1. Konfiguracja Embeddingów
        self.embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
            openai_api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        )
        
        # 2. Konfiguracja Modelu Chat
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0
        )
        
        self.vectorstore = None

    def ingest_data(self):
        print("   📥 [Naive RAG] Loading PDFs...")
        files = glob.glob("data/cvs/*.pdf")
        
        if not files:
            print("❌ No PDFs found in data/cvs/")
            return False

        documents = []
        for f in files:
            try:
                loader = PyPDFLoader(f)
                documents.extend(loader.load())
            except Exception:
                pass 

        if not documents:
            print("❌ No valid documents loaded.")
            return False
            
        # Cięcie tekstu
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        splits = text_splitter.split_documents(documents)
        
        # Baza wektorowa (Chroma) z mechanizmem RETRY
        print(f"   Creating Embeddings for {len(splits)} chunks...")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.vectorstore = Chroma.from_documents(
                    documents=splits, 
                    embedding=self.embeddings,
                    collection_name="cv_collection"
                )
                print("   ✅ Vector Store ready.")
                return True
            except Exception as e:
                print(f"   ⚠️ Connection Error (Attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print("   ⏳ Waiting 5s before retrying...")
                    time.sleep(5)
                else:
                    print(f"❌ Failed to create Vector Store after {max_retries} attempts.")
                    return False

    def query(self, question):
        if not self.vectorstore:
            print("⚠️ System not initialized.")
            return

        # print(f"\n❓ NAIVE QUERY: {question}") # Wyłączone, bo skrypt 5 sam drukuje pytania
        
        try:
            # KROK 1: Retrieval
            docs = self.vectorstore.similarity_search(question, k=5)
            context_text = "\n\n".join([d.page_content for d in docs])
            
            # KROK 2: Generation
            prompt = f"""
            You are a helpful HR Assistant. Answer the question based ONLY on the context provided below.
            If the answer is not in the context, say "I don't know".
            
            CONTEXT:
            {context_text}
            
            QUESTION:
            {question}
            """
            
            response = self.llm.invoke(prompt)
            answer = response.content
            
            # Printujemy tylko odpowiedź, bo skrypt 5 drukuje resztę
            print(f"Result: {answer}")
            return answer
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return "Error"

if __name__ == "__main__":
    rag = NaiveRAGSystem()
    if rag.ingest_data():
        rag.query("Who is experienced in Python?")
        rag.query("How many developers are located in London?") 
        rag.query("Who is currently available (not busy)?")