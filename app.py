# app.py

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

# --- 2. STYLE CSS ---
st.markdown("""
<style>
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

# -----------------------------
# HELPERS
# -----------------------------

def is_deanon_allowed() -> bool:
    """De-anonymization allowed only if env flag is enabled."""
    return os.getenv("ALLOW_DEANONYMIZATION", "false").lower() == "true"

def stable_person_mask(name: str) -> str:
    """Stable short mask for UI graph labels (visual only)."""
    if not name:
        return "Candidate_????"
    return f"Candidate_{hashlib.md5(name.encode()).hexdigest()[:8].upper()}"

def load_dashboard_metrics(engine: BusinessIntelligenceEngine):
    """Pobiera metryki biznesowe."""
    try:
        total_q = "MATCH (p:Person) RETURN count(p) as total"
        total = engine.graph.query(total_q)[0]['total']

        avail_q = """
        MATCH (p:Person)
        OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->()
        WITH p, sum(CASE WHEN r.allocation_percentage IS NOT NULL THEN r.allocation_percentage WHEN r.allocation IS NOT NULL THEN r.allocation ELSE 0.0 END) as current_load
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

def get_db_stats_full(engine: BusinessIntelligenceEngine):
    """Pobiera listy wszystkich kategorii do filtrów zagnieżdżonych."""
    try:
        skills = [r['id'] for r in engine.graph.query("MATCH (s:Skill) RETURN s.id as id ORDER BY id")]
        companies = [r['name'] for r in engine.graph.query("MATCH (c:Company) RETURN c.name as name ORDER BY name")]
        people = [r['name'] for r in engine.graph.query("MATCH (p:Person) RETURN p.name as name ORDER BY name")]
        projects = [r['name'] for r in engine.graph.query("MATCH (p:Project) RETURN coalesce(p.title, p.name) as name ORDER BY name")]
        rels = [r['rel'] for r in engine.graph.query("CALL db.relationshipTypes() YIELD relationshipType as rel")]
        return skills, companies, people, projects, rels
    except Exception:
        # fallback safe defaults
        return [], [], [], [], ["HAS_SKILL", "WORKED_AT", "ASSIGNED_TO"]

def get_node_color(labels):
    """Kolory dla węzłów - kontrast."""
    if "Person" in labels: return "#FF4B4B"   # czerwony
    if "Skill" in labels: return "#1C83E1"    # niebieski
    if "Project" in labels: return "#00D4FF"  # cyjan
    if "Company" in labels: return "#FF9000"  # pomarańcz
    if "Location" in labels: return "#A855F7" # fiolet
    if "University" in labels: return "#22C55E" # zielony
    return "#AAAAAA"

def get_graph_data(engine: BusinessIntelligenceEngine,
                   filter_mode: str,
                   selected_rels,
                   specific_entity_name: str,
                   privacy_active: bool = False):
    """Pobiera dane grafu i przygotowuje węzły/krawędzie (BEZ RENDEROWANIA)."""

    # SECURITY: avoid Cypher injection by parameterizing when possible
    if filter_mode == "Specific Entity Focus" and specific_entity_name:
        cypher = """
        MATCH (center)-[r]-(neighbor)
        WHERE (center.name = $val OR center.id = $val)
        RETURN center as n, labels(center) as n_labels, type(r) as rel_type,
               neighbor as m, labels(neighbor) as m_labels
        LIMIT 300
        """
        params = {"val": specific_entity_name}
    else:
        if not selected_rels:
            return None, None
        # relationship filter is constrained to known types from DB, but still build carefully
        rel_filter = " OR ".join([f"type(r) = '{rt}'" for rt in selected_rels])
        cypher = f"""
        MATCH (n)-[r]->(m)
        WHERE ({rel_filter})
        RETURN n, labels(n) as n_labels, type(r) as rel_type, m, labels(m) as m_labels
        LIMIT 150
        """
        params = {}

    results = engine.graph.query(cypher, params)

    nodes_dict, edges = {}, []
    for record in results:
        for key in ["n", "m"]:
            node = record[key]
            lbls = record[f"{key}_labels"]

            nid = node.get("id", node.get("name", str(node)))
            display = node.get("name", nid)

            if privacy_active and "Person" in lbls:
                display = stable_person_mask(display)

            if nid not in nodes_dict:
                nodes_dict[nid] = Node(
                    id=nid,
                    label=display,
                    size=25 if "Person" in lbls else 15,
                    color=get_node_color(lbls),
                    title=str(node)
                )

        edges.append(
            Edge(
                source=record["n"].get("id", record["n"].get("name")),
                target=record["m"].get("id", record["m"].get("name")),
                color="#777777",
                label=""  # keep UI clean
            )
        )

    return list(nodes_dict.values()), edges

# -----------------------------
# STATE INIT
# -----------------------------

if "engine" not in st.session_state:
    with st.spinner("🔌 Connecting to Knowledge Graph..."):
        try:
            st.session_state.engine = BusinessIntelligenceEngine()
        except Exception:
            st.error("Failed to initialize Business Intelligence Engine.")
            st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": "👋 Hi! I am connected to the secure Knowledge Graph. Ask me anything."
    }]

if "query_history" not in st.session_state:
    st.session_state.query_history = []

if "prompt_input" not in st.session_state:
    st.session_state.prompt_input = None

if "db_data" not in st.session_state:
    sk, co, pe, pr, rels = get_db_stats_full(st.session_state.engine)
    st.session_state.db_data = {"skills": sk, "companies": co, "people": pe, "projects": pr, "rels": rels}

if "current_nodes" not in st.session_state:
    st.session_state.current_nodes = None
if "current_edges" not in st.session_state:
    st.session_state.current_edges = None

# -----------------------------
# SIDEBAR
# -----------------------------
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png")
    else:
        st.header("🧠 TalentMatch AI")

    st.markdown("---")

    # Privacy toggle (UI-only). Deanon only if env allows.
    privacy_mode = st.toggle("Compliance Mode (PII Anonymization)", value=False)

    # Deanon capability indicator + control
    deanon_allowed = is_deanon_allowed()
    if deanon_allowed:
        st.caption("🔓 Admin mode: de-anonymization is ENABLED (ALLOW_DEANONYMIZATION=true).")
    else:
        st.caption("🔒 De-anonymization is DISABLED (set ALLOW_DEANONYMIZATION=true to enable).")

    st.markdown("---")
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

    def set_q(q):
        st.session_state.prompt_input = q

    with st.expander("📅 Availability", expanded=True):
        st.button("Who is free now?", on_click=set_q, args=("Who is currently available (has spare capacity)?",))
        st.button("Bench Report", on_click=set_q, args=("List developers currently on bench.",))

    with st.expander("🔍 Skills & Roles"):
        st.button("Python Seniors", on_click=set_q, args=("Find Senior Developers with Python skills.",))
        st.button("AWS DevOps", on_click=set_q, args=("Find Senior DevOps Engineers who know AWS.",))

    with st.expander("🚀 Scenarios"):
        st.button("Build Team (Python)", on_click=set_q, args=("Suggest an optimal team with Python under budget constraints.",))
        st.button("Skills Gap (RFP Pipeline)", on_click=set_q, args=("Gap analysis: skills gaps for upcoming RFP pipeline.",))
        st.button("Risk (SPOF)", on_click=set_q, args=("Risk assessment: single points of failure (SPOF) in current assignments.",))

    with st.expander("📊 Analytics"):
        st.button("Avg Rates", on_click=set_q, args=("What is the average hourly rate of Senior Python Developers?",))

    with st.expander("🔢 Statistics"):
        st.button("Total Projects", on_click=set_q, args=("How many active projects are there? (count)",))

    with st.expander("🔗 Network"):
        st.button("Jacob's Network", on_click=set_q, args=("Who has worked with Jacob Young in the past?",))
    
    with st.expander("⚡ Cypher Console (Read-Only)"):
        st.markdown("**Execute custom Cypher queries directly** (read-only for safety)")
        
        cypher_example = """MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
WHERE s.name = 'Python'
RETURN p.name, p.role, p.rate
LIMIT 10"""
        
        cypher_query = st.text_area(
            "Enter Cypher query:",
            value=cypher_example,
            height=150,
            key="cypher_input"
        )
        
        if st.button("🚀 Execute Query", key="execute_cypher"):
            # Validate read-only
            query_lower = cypher_query.lower().strip()
            forbidden = ["create", "merge", "delete", "detach", "set", "drop", "remove", 
                        "call", "load csv", "apoc", "gds", "dbms", "admin", "schema"]
            
            if any(kw in query_lower for kw in forbidden):
                st.error("❌ Write operations are not allowed. Only read queries (MATCH, RETURN, etc.)")
            elif not query_lower.startswith(("match", "with", "return")):
                st.error("❌ Query must start with MATCH, WITH, or RETURN")
            else:
                try:
                    with st.spinner("Executing query..."):
                        start = time.time()
                        result = st.session_state.engine.graph.query(cypher_query)
                        duration = time.time() - start
                    
                    st.success(f"✅ Query executed in {duration:.3f}s")
                    st.metric("Rows returned", len(result))
                    
                    if result:
                        df = pd.DataFrame(result)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No results returned")
                        
                except Exception as e:
                    st.error(f"❌ Query error: {str(e)}")

# -----------------------------
# MAIN UI
# -----------------------------
st.title("🚀 Intelligent Staffing Dashboard")
tab1, tab2 = st.tabs(["💬 AI Chat & Staffing", "🕸️ Network Explorer"])

# === TAB 1: CHAT ===
with tab1:
    # Metrics
    total, available, avg_rate = load_dashboard_metrics(st.session_state.engine)
    c1, c2, c3 = st.columns(3)
    c1.metric("👥 Total Talent", str(total))
    c2.metric("✅ Available Capacity", str(available))
    c3.metric("💰 Avg Rate", f"${avg_rate:.2f}/h")

    st.divider()

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "🧑‍💼"):
            display_text = msg["content"]

            # If assistant has decoder_map AND privacy_mode is OFF, we can reveal ONLY when env allows.
            decoder_map = msg.get("decoder_map") or {}
            if msg["role"] == "assistant" and decoder_map:
                if not privacy_mode:
                    if deanon_allowed:
                        for fid, real_name in decoder_map.items():
                            display_text = display_text.replace(fid, f"**{real_name}**")
                    else:
                        # user asked to unmask, but system doesn't allow it
                        st.warning("De-anonymization is disabled by configuration (ALLOW_DEANONYMIZATION=false).")
                else:
                    if not display_text.startswith("🛡️"):
                        display_text = f"🛡️ **[Data Anonymized]**\n\n{display_text}"

            st.markdown(display_text)

            # Reveal table only when:
            # - privacy_mode ON (so user sees mapping deliberately)
            # - AND env allows
            # - AND decoder_map exists
            if decoder_map and privacy_mode and deanon_allowed:
                with st.expander("🔐 Reveal Real Identities (Admin Only)"):
                    decoder_df = pd.DataFrame(list(decoder_map.items()), columns=["Masked ID", "Real Name"])
                    st.dataframe(decoder_df, hide_index=True, use_container_width=True)

    # Input
    user_input = st.chat_input("Ask a question...")

    # Quick action click handling
    if st.session_state.get("prompt_input"):
        user_input = st.session_state.prompt_input
        st.session_state.prompt_input = None

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        if user_input not in st.session_state.query_history:
            st.session_state.query_history.append(user_input)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analyzing Knowledge Graph..."):
                response = st.session_state.engine.answer_question(user_input, privacy_mode=privacy_mode)

                if response.get("success"):
                    raw_text = response.get("natural_answer", "")
                    decoder_map = response.get("decoder_map", {})  # already empty unless env allows

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": raw_text,
                        "decoder_map": decoder_map
                    })
                else:
                    err = response.get("error", "Unknown error")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"❌ Error: {err}",
                        "decoder_map": {}
                    })

        st.rerun()

# === TAB 2: GRAPH ===
with tab2:
    st.subheader("🌐 Network Explorer")

    if not VISUALIZATION_AVAILABLE:
        st.warning("streamlit-agraph is not installed or failed to import.")
    else:
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
                f_type = c1.selectbox("Kategoria:", ["Skill", "Company", "Person", "Project", "Location", "University"])
                options_map = {
                    "Skill": db["skills"],
                    "Company": db["companies"],
                    "Person": db["people"],
                    "Project": db["projects"],
                    "Location": [r["name"] for r in st.session_state.engine.graph.query("MATCH (l:Location) RETURN l.name as name ORDER BY name")],
                    "University": [r["name"] for r in st.session_state.engine.graph.query("MATCH (u:University) RETURN u.name as name ORDER BY name")]
                }
                opts = options_map.get(f_type, [])
                if not opts:
                    st.info("No items found for this category.")
                    f_name = None
                else:
                    f_name = c2.selectbox(f"Select {f_type}:", opts)

        if st.button("🔄 Render Graph"):
            nodes, edges = get_graph_data(st.session_state.engine, mode, selected_rels, f_name, privacy_mode)
            st.session_state.current_nodes = nodes
            st.session_state.current_edges = edges

        if st.session_state.current_nodes:
            config = Config(
                width=None,
                height=700,
                directed=True,
                physics=True,
                hierarchical=False,
                nodeHighlightBehavior=True,
                highlightColor="#FFFF00",
                staticPlot=False
            )
            agraph(nodes=st.session_state.current_nodes, edges=st.session_state.current_edges, config=config)

        st.info("💡 Tip: You can drag nodes. Clicking a node highlights its direct connections.")
        st.markdown("**Legend:** 🔴 Person | 🔵 Skill | 🟦 Project | 🟠 Company | 🟣 Location | 🟢 University")
