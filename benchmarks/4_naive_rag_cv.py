import sys
import os
import glob
import time
from dotenv import load_dotenv

# --- MAGICZNY NAGŁÓWEK: Naprawa ścieżek ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

load_dotenv(os.path.join(parent_dir, ".env"))

DATA_DIR = os.path.join(parent_dir, "data")
CHROMA_DB_DIR = os.path.join(parent_dir, "chroma_db")

# --- BEZPIECZNE IMPORTY (LCEL) ---
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

class NaiveRAGSystem:
    def __init__(self):
        # 1. Embeddingi
        self.embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_EMBEDDING_NAME", "text-embedding-3-small"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        )
        
        # 2. Model Chat
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=1
        )
        
        self.vectorstore = None
        self.persist_directory = CHROMA_DB_DIR

    def ingest_data(self):
        """Wczytuje PDFy i buduje bazę."""
        print("   📥 [Naive RAG] Loading PDFs...")
        pdf_path = os.path.join(DATA_DIR, "cvs", "*.pdf")
        files = glob.glob(pdf_path)
        
        if not files:
            print(f"❌ No PDFs found in {pdf_path}")
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
            
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        splits = text_splitter.split_documents(documents)
        
        print(f"   Creating Embeddings for {len(splits)} chunks...")
        
        try:
            self.vectorstore = Chroma.from_documents(
                documents=splits, 
                embedding=self.embeddings,
                collection_name="cv_collection",
                persist_directory=self.persist_directory
            )
            print("   ✅ Vector Store ready.")
            return True
        except Exception as e:
            print(f"❌ Failed to create Vector Store: {e}")
            return False

    def query(self, question):
        """Zadaje pytanie używając LCEL (Modern LangChain)."""
        # Inicjalizacja bazy
        if not self.vectorstore:
            try:
                self.vectorstore = Chroma(
                    persist_directory=self.persist_directory,
                    embedding_function=self.embeddings,
                    collection_name="cv_collection"
                )
            except Exception:
                return "Error: Vector Store not initialized."

        try:
            # Tworzymy retriever
            retriever = self.vectorstore.as_retriever(search_kwargs={"k": 4})
            
            # Definiujemy Prompt
            template = """Answer the question based only on the following context:
            {context}

            Question: {question}
            """
            prompt = ChatPromptTemplate.from_template(template)
            
            # --- TWORZYMY ŁAŃCUCH (LCEL) ---
            # To zastępuje stare RetrievalQA i omija błędy importu
            def format_docs(docs):
                return "\n\n".join([d.page_content for d in docs])

            chain = (
                {"context": retriever | format_docs, "question": RunnablePassthrough()}
                | prompt
                | self.llm
                | StrOutputParser()
            )
            
            # Uruchamiamy łańcuch
            response = chain.invoke(question)
            return response.strip()
            
        except Exception as e:
            return f"Error: {e}"

if __name__ == "__main__":
    rag = NaiveRAGSystem()
    
    # Próbujemy załadować lub zbudować bazę
    if not os.path.exists(CHROMA_DB_DIR) or not os.listdir(CHROMA_DB_DIR):
        rag.ingest_data()
    
    # SMOKE TESTS
    test_questions = [
        "Find a candidate with Java skills.",
        "How many candidates are located in London?",
        "What is the average hourly rate of Senior Developers?"
    ]
    
    print("\n🔎 Smoke Tests (Verification):")
    for q in test_questions:
        print("-" * 60)
        print(f"❓ Question: {q}")
        answer = rag.query(q)
        print(f"💡 Answer:   {answer}")
    print("-" * 60)