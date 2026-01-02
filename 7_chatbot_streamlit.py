"""
TalentMatch AI - Chatbot UI (Streamlit)

This is the user-facing interface for the Business Intelligence Engine.
Users can ask natural language questions and get instant answers powered
by the GraphRAG system.

Run with: streamlit run 7_chatbot_streamlit.py
"""

import streamlit as st
import os
from dotenv import load_dotenv
import json
from datetime import datetime
import importlib.util

# Import BusinessIntelligenceEngine from 6_business_intelligence.py
spec = importlib.util.spec_from_file_location(
    "business_intelligence",
    os.path.join(os.path.dirname(__file__), "6_business_intelligence.py")
)
bi_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bi_module)
BusinessIntelligenceEngine = bi_module.BusinessIntelligenceEngine

# Load environment variables
load_dotenv()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_explanation(query_type: str, answer: any, original_question: str) -> str:
    """
    Generate contextual explanation based on query type and results.
    """
    
    if query_type == 'counting':
        return f"This is a counting query. We found {answer} items matching your criteria in our developer pool."
    
    elif query_type == 'filtering':
        if isinstance(answer, list):
            count = len(answer)
            # Check if result is a skills list (single result with 'skills' key)
            if count == 1 and 'skills' in answer[0]:
                skills = answer[0]['skills']
                skill_list = ', '.join(skills) if isinstance(skills, list) else skills
                return f"This person has {len(skills) if isinstance(skills, list) else 'several'} skills: {skill_list}"
            # Check if result is a list of developers
            elif count > 0 and 'name' in answer[0]:
                return f"Found {count} developer(s) matching your filters. These are the most suitable candidates from our pool based on skills, location, and availability."
            else:
                return f"Found {count} result(s) matching your criteria."
        else:
            return "Filtering query executed successfully."
    
    elif query_type == 'aggregation':
        if isinstance(answer, dict):
            # Generate smart explanation based on the data
            if 'avg_skills_per_developer' in answer:
                avg = answer.get('avg_skills_per_developer', 0)
                total = answer.get('total_developers', 0)
                max_skills = answer.get('max_skills', 0)
                min_skills = answer.get('min_skills', 0)
                return f"Our pool of {total} developers has diverse skill levels. On average, each developer has {avg} skills. The most skilled developer has {max_skills} skills, while the least experienced has {min_skills}. This indicates a good mix of experienced and entry-level developers."
            elif 'available_developers' in answer:
                available = answer.get('available_developers', 0)
                assigned = answer.get('assigned_developers', 0)
                total = answer.get('total_developers', 0)
                return f"Capacity analysis: Out of {total} developers, {available} are currently available and {assigned} are assigned to projects. This gives us {available} FTE of available capacity for new projects."
            else:
                return f"Aggregation results: {', '.join([f'{k.replace(chr(95), ' ')}: {v}' for k, v in answer.items()])}"
        else:
            return f"Aggregation result: {answer}"
    
    elif query_type == 'reasoning':
        if isinstance(answer, list):
            count = len(answer)
            return f"Found {count} connection(s) between developers. These relationships show developers who have worked together or share common backgrounds, which can be valuable for team building."
        else:
            return "Reasoning query executed successfully."
    
    elif query_type == 'temporal':
        if isinstance(answer, list):
            count = len(answer)
            return f"Found {count} temporal event(s). These are developers whose availability status will change based on their current project timelines. This is useful for capacity planning."
        else:
            return "Temporal query executed successfully."
    
    elif query_type == 'scenario':
        if isinstance(answer, list):
            return f"Scenario analysis complete. We evaluated {len(answer) if isinstance(answer, list) else 'multiple'} possible team compositions based on your constraints. The results show the optimal assignments considering skills, availability, and other factors."
        else:
            return "Scenario analysis completed. The results show the recommended team composition for your project requirements."
    
    else:
        return f"Query executed successfully. Result: {answer}"

# Load environment variables
load_dotenv()

# Configure Streamlit page
st.set_page_config(
    page_title="TalentMatch AI - Staffing Intelligence",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    /* Main container */
    .main {
        padding: 0rem 1rem;
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] button {
        font-size: 16px;
        padding: 10px 20px;
    }
    
    /* Query type badges */
    .query-type-badge {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 5px;
        font-size: 12px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .counting { background-color: #FFE082; color: #333; }
    .filtering { background-color: #81C784; color: white; }
    .aggregation { background-color: #64B5F6; color: white; }
    .reasoning { background-color: #BA68C8; color: white; }
    .temporal { background-color: #FF8A65; color: white; }
    .scenario { background-color: #4DB6AC; color: white; }
    
    /* Chat message bubbles */
    [data-testid="stChatMessage"] {
        border-radius: 15px;
        padding: 10px 15px;
        margin-bottom: 10px;
    }
    
    /* Text input styling */
    .stTextInput input {
        border-radius: 25px;
        border: 1px solid #E0E0E0;
        padding: 12px 20px;
        font-size: 15px;
        background-color: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    .stTextInput input:focus {
        border-color: #1976D2;
        box-shadow: 0 2px 8px rgba(25, 118, 210, 0.15);
        outline: none;
    }
    
    /* Send button styling */
    .stButton button {
        background-color: #1976D2;
        color: white;
        border-radius: 25px;
        padding: 12px 35px;
        font-weight: 600;
        border: none;
        transition: all 0.2s ease;
        height: 48px;
        margin-top: 25px;
    }
    
    .stButton button:hover {
        background-color: #1565C0;
        box-shadow: 0 4px 12px rgba(25, 118, 210, 0.3);
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #F8F9FA;
    }
    
    [data-testid="stSidebar"] h2 {
        color: #1976D2;
        font-weight: 600;
    }
    
    [data-testid="stSidebar"] .stButton button {
        width: 100%;
        background-color: #DC3545;
        border-radius: 10px;
    }
    
    [data-testid="stSidebar"] .stButton button:hover {
        background-color: #C82333;
    }
    
    /* Code blocks styling */
    code {
        background-color: #2D2D2D;
        color: #F8F8F2;
        border-radius: 5px;
        padding: 2px 6px;
        font-family: 'Monaco', 'Menlo', monospace;
    }
    
    pre {
        background-color: #2D2D2D;
        border-radius: 8px;
        padding: 15px;
        border-left: 4px solid #1976D2;
    }
    
    /* Metric styling */
    [data-testid="stMetricValue"] {
        font-size: 24px;
        font-weight: bold;
        color: #1976D2;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: #F5F5F5;
        border-radius: 8px;
        font-weight: 600;
    }
    
    /* Chat input container */
    .stChatFloatingInputContainer {
        background-color: white;
        border-top: 1px solid #E0E0E0;
        padding: 15px 0;
    }
    
    /* Success/Error messages */
    .stSuccess {
        background-color: #D4EDDA;
        border-left: 4px solid #28A745;
        border-radius: 5px;
    }
    
    .stError {
        background-color: #F8D7DA;
        border-left: 4px solid #DC3545;
        border-radius: 5px;
    }
    
    /* Info messages */
    .stInfo {
        background-color: #D1ECF1;
        border-left: 4px solid #17A2B8;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "bi_engine" not in st.session_state:
    with st.spinner("🚀 Initializing Business Intelligence Engine..."):
        try:
            st.session_state.bi_engine = BusinessIntelligenceEngine()
            st.session_state.engine_ready = True
        except Exception as e:
            st.session_state.engine_ready = False
            st.session_state.engine_error = str(e)

# ============================================================================
# HEADER
# ============================================================================

st.title("🎯 TalentMatch AI - Staffing Intelligence")
st.markdown("""
Ask natural language questions about your developer pool, projects, and team assignments.
The system uses GraphRAG to provide precise, structured answers.
""")

# # ============================================================================
# # SIDEBAR
# # ============================================================================

# with st.sidebar:
#     st.header("📚 About This System")
    
#     st.markdown("""
#     **TalentMatch AI** uses GraphRAG to answer complex business questions about:
    
#     - **👥 Developers** - Skills, locations, experience, availability
#     - **🏢 Companies** - Where developers have worked
#     - **🎓 Education** - Universities and degrees
#     - **💼 Projects** - Assigned teams, requirements, timelines
    
#     ### Query Types Supported:
    
#     🔢 **Counting** - "How many?" questions
#     - *"How many Python developers are available?"*
    
#     🔍 **Filtering** - "Find" with specific criteria
#     - *"Find senior devs with React AND Node.js"*
    
#     📊 **Aggregation** - "Average", "sum", statistics
#     - *"Average years of experience?"*
    
#     🔗 **Reasoning** - Relationships and connections
#     - *"Who worked together?"*
    
#     ⏰ **Temporal** - Time-based queries
#     - *"Who becomes available next month?"*
    
#     🎯 **Scenario** - Complex what-if analysis
#     - *"Best team for FinTech project under budget?"*
#     """)
    
#     st.divider()
    
#     st.header("💡 Example Questions")
    
#     example_questions = {
#         "Counting": [
#             "How many Python developers are available?",
#             "Count developers with machine learning experience",
#             "How many projects are currently active?"
#         ],
#         "Filtering": [
#             "Find senior developers with React skills",
#             "List developers from NYC with AWS experience",
#             "Show all developers with both Python and SQL"
#         ],
#         "Aggregation": [
#             "What is the average years of experience?",
#             "How many total skills do we have in the pool?",
#             "Average team size for completed projects?"
#         ],
#         "Reasoning": [
#             "Who worked together before?",
#             "Find developers from the same company",
#             "Which developers studied at the same university?"
#         ]
#     }
    
#     selected_category = st.selectbox(
#         "📌 Example queries:",
#         ["Counting", "Filtering", "Aggregation", "Reasoning"]
#     )
    
#     if st.button("Copy example to input"):
#         example = example_questions[selected_category][0]
#         st.session_state.user_input = example
    
#     st.divider()
    
#     st.header("⚙️ System Status")
    
#     if st.session_state.engine_ready:
#         st.success("✅ Business Intelligence Engine: Ready")
        
#         # Try to show graph statistics
#         try:
#             nodes_result = st.session_state.bi_engine.graph.query(
#                 "MATCH (n) RETURN count(n) as count"
#             )
#             relationships_result = st.session_state.bi_engine.graph.query(
#                 "MATCH ()-[r]->() RETURN count(r) as count"
#             )
            
#             if nodes_result and relationships_result:
#                 nodes = nodes_result[0]["count"]
#                 rels = relationships_result[0]["count"]
                
#                 col1, col2 = st.columns(2)
#                 with col1:
#                     st.metric("📊 Graph Nodes", nodes)
#                 with col2:
#                     st.metric("🔗 Relationships", rels)
#         except:
#             st.warning("⚠️ Could not fetch graph statistics")
#     else:
#         st.error(f"❌ Engine Error: {st.session_state.get('engine_error', 'Unknown error')}")
#         st.info("Please check your .env file and Neo4j connection.")
    
#     st.divider()
    
#     if st.button("🗑️ Clear Chat History", use_container_width=True):
#         st.session_state.messages = []
#         st.success("Chat history cleared!")
#         st.rerun()

# ============================================================================
# MAIN CHAT INTERFACE
# ============================================================================

if not st.session_state.engine_ready:
    st.error("🔴 Cannot start chatbot - Business Intelligence Engine is not ready")
    st.info("Please verify:")
    st.markdown("""
    1. Neo4j is running (`docker-compose up -d`)
    2. `.env` file has correct credentials
    3. Knowledge graph is populated (`python 2_data_to_knowledge_graph.py`)
    """)
else:
    # Display chat history
    chat_container = st.container()
    
    with chat_container:
        for i, message in enumerate(st.session_state.messages):
            if message["role"] == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(message["content"])
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(message["content"])
                    
                    # Show metadata if available
                    if "metadata" in message:
                        with st.expander("📊 Query Details"):
                            metadata = message["metadata"]
                            
                            # Query type badge
                            query_type = metadata.get("query_type", "unknown").lower()
                            st.markdown(
                                f'<span class="query-type-badge {query_type}">'
                                f'{metadata.get("query_type", "UNKNOWN")}</span>',
                                unsafe_allow_html=True
                            )
                            
                            # Cypher query
                            if metadata.get("cypher_query"):
                                st.code(
                                    metadata["cypher_query"],
                                    language="cypher",
                                    line_numbers=True
                                )
                            
                            # Raw result - convert to string for display
                            if metadata.get("raw_result") is not None:
                                raw = metadata["raw_result"]
                                # Only try st.json() if it's a dict or list
                                if isinstance(raw, (dict, list)):
                                    try:
                                        st.json(raw)
                                    except:
                                        st.text(str(raw))
                                else:
                                    # For primitives (int, str, etc), just display
                                    st.metric("Result", raw)
    
    st.divider()
    
    # Input section
    st.subheader("🎤 Ask a Question")
    
    col1, col2 = st.columns([5, 1])
    
    with col1:
        user_input = st.text_input(
            "What would you like to know?",
            placeholder="e.g., How many Python developers are available?",
            key="user_input_field"
        )
    
    with col2:
        send_button = st.button("Send ✈️", use_container_width=True)
    
        # Process user input
        if send_button and user_input:
            # Add user message to chat
            st.session_state.messages.append({
                "role": "user",
                "content": user_input
            })
            
            # Process with BI Engine
            with st.spinner("🔍 Analyzing query..."):
                try:
                    # Get answer from BI engine
                    result = st.session_state.bi_engine.answer_question(user_input)
                    
                    # Format response based on result structure
                    if result.get('success', False):
                        answer = result.get('result', 'No answer generated')
                        answer_text = str(answer) if answer else 'No answer'
                        query_type = result.get('type', 'unknown').lower()
                        
                        # Generate contextual explanation based on query type
                        explanation = generate_explanation(query_type, answer, user_input)
                    else:
                        answer_text = f"⚠️ {result.get('error', 'No answer generated')}"
                        explanation = "Please rephrase your question or check the system status"
                        query_type = result.get('type', 'unknown')
                    
                    response_text = f"""
**Answer:**
{answer_text}

**Explanation:**
{explanation}
"""
                    
                    # Add assistant response to chat
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "metadata": {
                            "query_type": result.get("type", "UNKNOWN"),
                            "cypher_query": result.get("cypher_query", ""),
                            "raw_result": result.get("result", [])
                        }
                    })
                    
                    st.rerun()
                    
                except Exception as e:
                    error_msg = f"""
❌ **Error Processing Query**

{str(e)}

**Troubleshooting:**
1. Is Neo4j running? Check: `docker-compose ps`
2. Is the knowledge graph populated? Run: `python 2_data_to_knowledge_graph.py`
3. Check `.env` file for correct credentials
"""
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })
                    st.rerun()

# # ============================================================================
# # FOOTER
# # ============================================================================

# st.divider()

# footer_cols = st.columns(4)

# with footer_cols[0]:
#     st.caption("🛠️ Built with LangChain + Neo4j")

# with footer_cols[1]:
#     st.caption("📊 GraphRAG powered")

# with footer_cols[2]:
#     st.caption(f"⏰ {datetime.now().strftime('%H:%M:%S')}")

# with footer_cols[3]:
#     st.caption("[Docs](https://example.com) | [GitHub](https://example.com)")
