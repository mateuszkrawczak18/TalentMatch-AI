import os
import glob
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

class NaiveRAGSystem:
    def __init__(self):
        # 1. Konfiguracja Azure - WAŻNE: Musisz mieć model Embeddings w Azure
        # Upewnij się, że masz AZURE_EMBEDDING_DEPLOYMENT w .env (np. text-embedding-3-small)
        embedding_deployment = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
        
        self.embeddings = AzureOpenAIEmbeddings(
            azure_deployment=embedding_deployment,
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        )
        
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=1.0
        )
        
        self.vectorstore = None

    def ingest_data(self):
        """Wczytuje PDFy i buduje indeks wektorowy (czyta całość RAZ)"""
        print("📥 [Naive RAG] Loading PDFs...")
        files = glob.glob("data/cvs/*.pdf")
        
        if not files:
            print("❌ No PDFs found in data/cvs/")
            return False

        documents = []
        for f in files:
            loader = PyPDFLoader(f)
            documents.extend(loader.load())
            
        print(f"   Loaded {len(documents)} pages from {len(files)} files.")
        
        # Cięcie tekstu na kawałki (Chunks)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        splits = text_splitter.split_documents(documents)
        print(f"   Split into {len(splits)} text chunks.")
        
        # Tworzenie bazy wektorowej
        print("   Creating Embeddings (this may take a moment)...")
        try:
            self.vectorstore = Chroma.from_documents(
                documents=splits, 
                embedding=self.embeddings,
                collection_name="cv_collection" # Baza w pamięci RAM dla szybkości testu
            )
            print("✅ Vector Store ready.")
            return True
        except Exception as e:
            print(f"❌ Error creating embeddings: {e}")
            print("💡 TIP: Check if AZURE_EMBEDDING_DEPLOYMENT is correct in .env")
            return False

    def query(self, question):
        if not self.vectorstore:
            print("⚠️ Index not ready.")
            return

        print(f"\n❓ NAIVE QUERY: {question}")
        
        # Retrieve: Pobierz TYLKO 5 najbardziej pasujących fragmentów
        # To jest cecha Naive RAG - ograniczone okno kontekstowe
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        
        template = """Answer the question based ONLY on the following context context.
        If you don't know the answer or the context is insufficient, say "I don't know".
        
        Context:
        {context}
        
        Question: {question}
        """
        prompt = ChatPromptTemplate.from_template(template)
        
        chain = (
            {"context": retriever | self.format_docs, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )
        
        try:
            response = chain.invoke(question)
            print(f"🤖 NAIVE ANSWER: {response}")
            return response
        except Exception as e:
            print(f"❌ Error: {e}")
            return "Error"

    def format_docs(self, docs):
        return "\n\n".join([d.page_content for d in docs])

if __name__ == "__main__":
    rag = NaiveRAGSystem()
    if rag.ingest_data():
        # Testy porównawcze
        rag.query("Who is experienced in Python?")
        rag.query("How many developers are located in London?") # Tu powinien polec (zwróci np. 2-3 zamiast wszystkich)
        rag.query("Who is currently available (not busy)?")     # Tu musi polec (nie ma danych o availability w PDF)