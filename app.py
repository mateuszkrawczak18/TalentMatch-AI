import streamlit as st
import os
import time
import logging
import pandas as pd
import hashlib
from bi_engine import BusinessIntelligenceEngine

# --- IMPORT BIBLIOTEKI DO WIZUALIZACJI ---
try:
    from streamlit_agraph import agraph, Node, Edge, Config
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="TalentMatch AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- KONFIGURACJA LOGOWANIA ---
logging.basicConfig(
    filename='system_metrics.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- 2. STYLE CSS (TWOJE) ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    div[data-testid="metric-container"] {
        background-color: #262730;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #4F8BF9;
        text-align: center;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: auto;
        min-height: 2.5em;
        background-color: #262730;
        color: white;
        border: 1px solid #4F8BF9;
        margin-bottom: 5px;
    }
    .stButton>button:hover {
        background-color: #4F8BF9;
        color: white;
        border-color: #FFFFFF;
    }
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 3. FUNKCJE POMOCNICZE ---

def load_dashboard_metrics(engine):
    """Pobiera metryki biznesowe."""
    try:
        total_q = "MATCH (p:Person) RETURN count(p) as total"
        total = engine.graph.query(total_q)[0]['total']
        
        avail_q = """
        MATCH (p:Person)
        OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->()
        WITH p, sum(CASE WHEN r.allocation IS NOT NULL THEN r.allocation ELSE 0.0 END) as current_load
        WHERE current_load < 1.0
        RETURN count(p) as available
        """
        available = engine.graph.query(avail_q)[0]['available']
        
        rate_q = "MATCH (p:Person) WHERE p.rate IS NOT NULL RETURN avg(p.rate) as avg_rate"
        avg_rate_res = engine.graph.query(rate_q)
        avg_rate = avg_rate_res[0]['avg_rate'] if avg_rate_res and avg_rate_res[0]['avg_rate'] else 0
        
        return total, available, avg_rate
    except Exception:
        return 0, 0, 0

def get_db_stats_full(engine):
    """Pobiera listy wszystkich kategorii do filtrów zagnieżdżonych."""
    try:
        skills = [r['id'] for r in engine.graph.query("MATCH (s:Skill) RETURN s.id as id ORDER BY id")]
        companies = [r['name'] for r in engine.graph.query("MATCH (c:Company) RETURN c.name as name ORDER BY name")]
        people = [r['name'] for r in engine.graph.query("MATCH (p:Person) RETURN p.name as name ORDER BY name")]
        projects = [r['name'] for r in engine.graph.query("MATCH (p:Project) RETURN p.name as name ORDER BY name")]
        rels = [r['rel'] for r in engine.graph.query("CALL db.relationshipTypes() YIELD relationshipType as rel")]
        return skills, companies, people, projects, rels
    except:
        return [], [], [], [], ["HAS_SKILL", "WORKED_AT", "ASSIGNED_TO"]

def get_node_color(labels):
    """Kolory dla węzłów - Zaktualizowane na Czerwony i Niebieski dla kontrastu."""
    if "Person" in labels: return "#FF4B4B"   # Intensywny Czerwony
    if "Skill" in labels: return "#1C83E1"    # Jasny Niebieski
    if "Project" in labels: return "#00D4FF"  # Cyjan
    if "Company" in labels: return "#FF9000"  # Pomarańczowy (dla dopełnienia)
    return "#AAAAAA"

def get_graph_data(engine, filter_mode, selected_rels, specific_entity_name, privacy_active=True):
    """Pobiera dane grafu i przygotowuje węzły/krawędzie (BEZ RENDEROWANIA)."""
    if filter_mode == "Specific Entity Focus" and specific_entity_name:
        cypher = f"""
        MATCH (center)-[r]-(neighbor)
        WHERE (center.name = '{specific_entity_name}' OR center.id = '{specific_entity_name}')
        RETURN center as n, labels(center) as n_labels, type(r) as rel_type, neighbor as m, labels(neighbor) as m_labels
        LIMIT 300
        """
    else:
        if not selected_rels: return None, None
        rel_filter = " OR ".join([f"type(r) = '{rt}'" for rt in selected_rels])
        cypher = f"MATCH (n)-[r]->(m) WHERE ({rel_filter}) RETURN n, labels(n) as n_labels, type(r) as rel_type, m, labels(m) as m_labels LIMIT 150"

    results = engine.graph.query(cypher)
    nodes_dict, edges = {}, []
    for record in results:
        for key in ['n', 'm']:
            node, lbls = record[key], record[f'{key}_labels']
            nid = node.get('id', node.get('name', str(node)))
            n_show = node.get('name', nid)
            if privacy_active and "Person" in lbls:
                n_show = f"Candidate_{hashlib.md5(n_show.encode()).hexdigest()[:4]}"
            if nid not in nodes_dict:
                nodes_dict[nid] = Node(id=nid, label=n_show, size=25 if "Person" in lbls else 15, color=get_node_color(lbls), title=str(node))
        
        # Kolor linii ustawiony na lekki szary, aby żółty highlight był widoczny
        edges.append(Edge(source=record['n'].get('id', record['n'].get('name')), 
                          target=record['m'].get('id', record['m'].get('name')), 
                          color="#777777", label="")) 
    return list(nodes_dict.values()), edges



# --- 4. INICJALIZACJA STANU ---
if "engine" not in st.session_state:
    with st.spinner("🔌 Connecting to Knowledge Graph..."):
        try:
            st.session_state.engine = BusinessIntelligenceEngine()
        except Exception:
            st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "👋 Hi! I am connected to the secure Knowledge Graph. Ask me anything."}]

if "query_history" not in st.session_state:
    st.session_state.query_history = []

if "prompt_input" not in st.session_state:
    st.session_state.prompt_input = None

if "db_data" not in st.session_state:
    sk, co, pe, pr, rels = get_db_stats_full(st.session_state.engine)
    st.session_state.db_data = {"skills": sk, "companies": co, "people": pe, "projects": pr, "rels": rels}

if "current_nodes" not in st.session_state: st.session_state.current_nodes = None
if "current_edges" not in st.session_state: st.session_state.current_edges = None

# --- 5. PASEK BOCZNY (TWOJE LOGO I QUICK ACTIONS) ---
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png")
    else:
        st.header("🧠 TalentMatch AI")
    st.markdown("---")
    
    privacy_mode = st.sidebar.toggle("Compliance Mode (PII Anonymization)", value=True)
    
    st.subheader("📜 Search History")
    with st.expander("Show recent queries"):
        if not st.session_state.query_history:
            st.caption("No queries yet.")
        else:
            for q in reversed(st.session_state.query_history[-5:]):
                if st.button(f"{q[:25]}...", key=f"hist_{hash(q)}"):
                    st.session_state.prompt_input = q

    st.markdown("---")
    st.subheader("⚡ Quick Actions")
    def set_q(q): st.session_state.prompt_input = q

    with st.expander("📅 Availability", expanded=True):
        st.button("Who is free now?", on_click=set_q, args=("Who is currently available (has spare capacity)?",))
        st.button("Bench Report", on_click=set_q, args=("List developers currently on bench.",))
    with st.expander("🔍 Skills & Roles"):
        st.button("Python Seniors", on_click=set_q, args=("Find Senior Developers with Python skills.",))
        st.button("AWS DevOps", on_click=set_q, args=("Find Senior DevOps Engineers who know AWS.",))
    with st.expander("🚀 Scenarios"):
        st.button("Build Team (3x Python)", on_click=set_q, args=("Suggest an optimal team of 3 available Developers with Python skills.",))
    with st.expander("📊 Analytics"):
        st.button("Avg Rates", on_click=set_q, args=("What is the average hourly rate of Senior Python Developers?",))
    with st.expander("🔢 Statistics"):
        st.button("Total Projects", on_click=set_q, args=("How many active projects are there?",))
    with st.expander("🔗 Network"):
        st.button("Jacob's Network", on_click=set_q, args=("Who has worked with Jacob Young in the past?",))

# --- 6. MAIN UI ---
st.title("🚀 Intelligent Staffing Dashboard")
tab1, tab2 = st.tabs(["💬 AI Chat & Staffing", "🕸️ Network Explorer"])

# === TAB 1: CHAT ===
with tab1:
    # 1. METRYKI (Fajne liczby na środku)
    if "engine" in st.session_state:
        total, available, avg_rate = load_dashboard_metrics(st.session_state.engine)
        c1, c2, c3 = st.columns(3)
        c1.metric("👥 Total Talent", str(total))
        c2.metric("✅ Available Capacity", str(available))
        c3.metric("💰 Avg Rate", f"${avg_rate:.2f}/h")

    st.divider()

# 2. RENDEROWANIE HISTORII CZATU (DYNAMICZNE)
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🤖" if msg["role"]=="assistant" else "🧑‍💼"):
            
            display_text = msg["content"]
            
            # Jeśli to wiadomość od AI i posiada mapę dekodera
            if msg["role"] == "assistant" and msg.get("decoder_map"):
                if not privacy_mode:
                    # TRYB JAWNY: Podmieniamy hashe na nazwiska "w locie"
                    for fid, rname in msg["decoder_map"].items():
                        display_text = display_text.replace(fid, f"**{rname}**")
                else:
                    # TRYB ANONIMOWY: Dodajemy tylko ikonkę tarczy do surowego tekstu
                    # Sprawdzamy czy tarcza już tam jest, żeby nie dodawać jej wielokrotnie
                    if not display_text.startswith("🛡️"):
                        display_text = f"🛡️ **[Data Anonymized]**\n\n{display_text}"
            
            st.markdown(display_text)
            
            # Wyświetl tabelę identyfikacji tylko w trybie anonimowym
            if msg.get("decoder_map") and privacy_mode and len(msg["decoder_map"]) > 0:
                with st.expander("🔐 Reveal Real Identities"):
                    decoder_df = pd.DataFrame(list(msg["decoder_map"].items()), columns=["ID", "Real Name"])
                    st.dataframe(decoder_df, hide_index=True, use_container_width=True)

    # 3. OBSŁUGA WEJŚCIA (Input / Quick Actions)
    user_input = st.chat_input("Ask a question...")
    
    # Obsługa kliknięcia w Quick Action z Sidebaru
    if st.session_state.get("prompt_input"):
        user_input = st.session_state.prompt_input
        st.session_state.prompt_input = None # Czyścimy, żeby nie zapętlić

    if user_input:
        # Dodaj pytanie użytkownika do sesji
        st.session_state.messages.append({"role": "user", "content": user_input})
        if user_input not in st.session_state.query_history:
            st.session_state.query_history.append(user_input)
        
        # Wyświetlenie pytania i generowanie odpowiedzi
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analyzing Knowledge Graph..."):
                response = st.session_state.engine.answer_question(user_input)
                
                if response.get('success'):
                    # ZAPISUJEMY SUROWY TEKST (bez tarczy i bez podmian)
                    raw_text = response.get('natural_answer', "")
                    decoder_map = response.get('decoder_map', {})
                    
                    # Zapisujemy do historii "czyste" dane do późniejszego renderowania
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": raw_text, 
                        "decoder_map": decoder_map
                    })
                    
                    # Nie musimy tu robić st.markdown, bo st.rerun() 
                    # na końcu odświeży pętlę renderującą powyżej
        
        # Odśwież stronę, aby chat "skoczył" do góry i wyczyścił input
        st.rerun()

# === TAB 2: GRAF ===
with tab2:
    st.subheader("🌐 Network Explorer")
    db = st.session_state.db_data
    
    col_m, col_f = st.columns([2, 3])
    with col_m:
        mode = st.radio("Visualization Mode:", ["General Overview", "Specific Entity Focus"], horizontal=True)
    
    selected_rels, f_type, f_name = [], None, None
    with col_f:
        if mode == "General Overview":
            selected_rels = st.multiselect("Connection Types:", db["rels"], default=db["rels"][:2])
        else:
            c1, c2 = st.columns(2)
            f_type = c1.selectbox("Kategoria:", ["Skill", "Company", "Person", "Project"])
            options_map = {"Skill": db["skills"], "Company": db["companies"], "Person": db["people"], "Project": db["projects"]}
            f_name = c2.selectbox(f"Select {f_type}:", options_map[f_type])

    if st.button("🔄 Render Graph"):
        nodes, edges = get_graph_data(st.session_state.engine, mode, selected_rels, f_name, privacy_mode)
        st.session_state.current_nodes = nodes
        st.session_state.current_edges = edges

    if st.session_state.current_nodes:
        # highlightColor set to Yellow (#FFFF00) for edge visibility on click
        config = Config(
            width=None, height=700, directed=True, physics=True, 
            hierarchical=False, nodeHighlightBehavior=True, 
            highlightColor="#FFFF00", staticPlot=False
        )
        agraph(nodes=st.session_state.current_nodes, edges=st.session_state.current_edges, config=config)
    
    st.info("💡 Tip: You can drag nodes. Clicking a node highlights its direct connections.")
    st.markdown("**Legend:** 🔴 Person | 🔵 Skill | 🔵 Project | 🟠 Company")