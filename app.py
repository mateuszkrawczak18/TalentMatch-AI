import streamlit as st
import os
from src.graph_agent import TalentAgent

# --- 1. Konfiguracja Strony ---
st.set_page_config(
    page_title="TalentMatch AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. Style CSS ---
st.markdown("""
<style>
    /* Stylizacja metryk - tło i ramki */
    div[data-testid="metric-container"] {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 15px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    /* Stylizacja przycisków wewnątrz expanderów */
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        border: 1px solid #4b4b4b;
        text-align: left;
        background-color: #262730;
        color: white;
    }
    .stButton>button:hover {
        border-color: #ff4b4b;
        background-color: #363740;
    }
    /* Ukrycie domyślnego menu hamburgera */
    #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 3. Funkcje Pomocnicze ---
def load_dashboard_metrics(agent):
    """Pobiera metryki z Neo4j do dashboardu."""
    try:
        # Całkowita liczba pracowników
        total_q = "MATCH (p:Person) RETURN count(p) as total"
        total = agent.graph.query(total_q)[0]['total']
        
        # Dostępni (nieprzypisani do żadnego projektu)
        avail_q = "MATCH (p:Person) WHERE NOT (p)-[:ASSIGNED_TO]->(:Project) RETURN count(p) as available"
        available = agent.graph.query(avail_q)[0]['available']
        
        # Średnia stawka
        rate_q = "MATCH (p:Person) RETURN avg(p.rate) as avg_rate"
        avg_rate_res = agent.graph.query(rate_q)
        avg_rate = avg_rate_res[0]['avg_rate'] if avg_rate_res and avg_rate_res[0]['avg_rate'] else 0
        
        return total, available, avg_rate
    except Exception:
        return 0, 0, 0

def handle_query(query_text):
    """Wysyła zapytanie do czatu i obsługuje odpowiedź."""
    # Dodaj pytanie użytkownika
    st.session_state.messages.append({"role": "user", "content": query_text})
    
    # Wygeneruj odpowiedź
    with st.chat_message("assistant", avatar="🤖"):
        placeholder = st.empty()
        with st.spinner("🧠 Analyzing Knowledge Graph..."):
            try:
                response = st.session_state.agent.ask(query_text)
                placeholder.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                placeholder.error(f"Error: {e}")

# --- 4. Inicjalizacja Agenta ---
if "agent" not in st.session_state:
    with st.spinner("🔌 Connecting to Knowledge Graph..."):
        try:
            st.session_state.agent = TalentAgent()
        except Exception as e:
            st.error(f"❌ Connection failed: {e}")
            st.stop()

# --- 5. Pasek Boczny (Sidebar) ---
with st.sidebar:
    # Logo i Nagłówek
    if os.path.exists("logo.png"):
        st.image("logo.png", width=220)
    else:
        st.header("🧠 TalentMatch AI")
    
    st.markdown("---")
    st.subheader("⚡ Quick Actions")
    st.write("Select a category to see query templates:")
    
    # --- KATEGORIA 1: DOSTĘPNOŚĆ ---
    with st.expander("👥 Availability & Staffing", expanded=True):
        st.caption("Check who is free or busy")
        
        if st.button("Who is available?"):
            handle_query("Who is currently available (not assigned to any project)?")
            
        if st.button("Capacity for 3 Seniors?"):
            handle_query("Do we have enough capacity for a new project requiring 3 Senior Developers? Check if they are available.")

    # --- KATEGORIA 2: UMIEJĘTNOŚCI ---
    with st.expander("🐍 Skills & Roles", expanded=False):
        st.caption("Search by tech stack")
        
        if st.button("Find Senior Python Devs"):
            handle_query("Find all Senior Python Developers. List their names, seniority, and rates.")
            
        if st.button("Find DevOps with AWS"):
            handle_query("Find DevOps Engineers who have 'AWS' skill and are located in London.")

    # --- KATEGORIA 3: ANALITYKA ---
    with st.expander("📊 Market Analytics", expanded=False):
        st.caption("Rates and stats")
        
        if st.button("Avg Rate for Seniors"):
            handle_query("What is the average hourly rate of Senior level employees?")
            
        if st.button("Avg Rate for DevOps"):
            handle_query("What is the average hourly rate of DevOps Engineers?")

    # --- KATEGORIA 4: RELACJE ---
    with st.expander("🔗 Network Analysis", expanded=False):
        st.caption("Who worked with whom?")
        
        if st.button("Worked with Jacob Young?"):
            handle_query("Who has worked with Jacob Young in the past (same company or project)?")

    st.markdown("---")
    st.info("Powered by **Neo4j GraphRAG** & **Azure OpenAI**")

# --- 6. Dashboard (Góra strony) ---
st.title("🚀 Intelligent Staffing Dashboard")
st.markdown("Real-time insights based on your **Graph Database**.")

if "agent" in st.session_state:
    total, available, avg_rate = load_dashboard_metrics(st.session_state.agent)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="👥 Total Talent Pool", value=str(total))
    
    with col2:
        # Obliczanie procentowego wykorzystania
        utilization = ((total - available) / total) * 100 if total > 0 else 0
        
        # Kolor delty: zielony jeśli są dostępni, czerwony (inverse) jeśli 0 dostępnych
        delta_val = f"{utilization:.0f}% Busy"
        delta_col = "inverse" if available == 0 else "normal"
        
        st.metric(
            label="✅ Available Bench", 
            value=str(available), 
            delta=delta_val, 
            delta_color=delta_col
        )
    
    with col3:
        st.metric(label="💰 Avg Hourly Rate", value=f"${avg_rate:.2f}")

st.divider()

# --- 7. Czat ---
st.subheader("💬 AI Analyst Chat")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "👋 Hi! Select a Quick Action from the sidebar or type your own question below."}]

for msg in st.session_state.messages:
    avatar = "🤖" if msg["role"] == "assistant" else "🧑‍💼"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask a custom question... (e.g. 'Find Java devs in Berlin')"):
    handle_query(prompt)