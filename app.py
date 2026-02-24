import streamlit as st
import pandas as pd
from supabase import create_client
from google import genai
from google.genai import types
import pdfplumber
import docx
import json
import re
import time

# --- 1. CORE CONFIG ---
st.set_page_config(page_title="Global Medical Passport", page_icon="🏥", layout="wide")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stAppDeployButton {display:none;}
            [data-testid="stToolbar"] {visibility: hidden !important;}
            [data-testid="stDecoration"] {display:none;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# Connection Setup
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase_client = create_client(URL, KEY)
    
    if "GEMINI_API_KEY" in st.secrets:
        ai_client = genai.Client(
            api_key=st.secrets["GEMINI_API_KEY"],
            http_options={'api_version': 'v1'}
        )
        MODEL_ID = "gemini-1.5-flash" 
    else:
        st.error("⚠️ GEMINI_API_KEY missing.")
except Exception as e:
    st.error(f"Config Error: {e}")

# --- 2. GLOBAL MAPPING DATA ---
EQUIVALENCY_MAP = {
    "Tier 1: Junior (Intern/FY1)": {"UK": "Foundation Year 1", "US": "PGY-1 (Intern)", "Australia": "Intern", "Poland": "Lekarz stażysta"},
    "Tier 2: Intermediate (SHO/Resident)": {"UK": "FY2 / Core Trainee", "US": "PGY-2/3 (Resident)", "Australia": "Resident / RMO", "Poland": "Lekarz rezydent (Junior)"},
    "Tier 3: Senior (Registrar/Fellow)": {"UK": "ST3+ / Registrar", "US": "Chief Resident / Fellow", "Australia": "Registrar", "Poland": "Lekarz rezydent (Senior)"},
    "Tier 4: Expert (Consultant/Attending)": {"UK": "Consultant / SAS", "US": "Attending Physician", "Australia": "Consultant / Specialist", "Poland": "Lekarz specjalista"}
}

# --- 3. SESSION STATE ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'scraped_lines' not in st.session_state:
    st.session_state.scraped_lines = []

def handle_login():
    try:
        res = supabase_client.auth.sign_in_with_password({"email": st.session_state.login_email, "password": st.session_state.login_password})
        if res.user:
            st.session_state.authenticated = True
            st.session_state.user_email = res.user.email
    except Exception as e:
        st.error(f"Login failed: {e}")

# --- 4. THE FAIL-SAFE ENGINE ---
def get_raw_text(file):
    text = ""
    try:
        if file.name.endswith('.pdf'):
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + "\n"
        elif file.name.endswith('.docx'):
            doc = docx.Document(file)
            text = "\n".join([p.text for p in doc.paragraphs])
        return text.strip()
    except: return ""

def extract_medical_lines(chunk_text):
    """Asks for plain text lines instead of complex JSON to avoid crashes."""
    prompt = (
        "Identify every clinical rotation, medical job, hospital, procedure, and audit in this text. "
        "List them as plain text lines. Format each line exactly like this: "
        "CATEGORY | TITLE | DATE "
        "Use categories: EXPERIENCE, PROCEDURE, QIP, EDUCATION. "
        f"\n\nCV Text: {chunk_text}"
    )
    try:
        response = ai_client.models.generate_content(
            model=MODEL_ID,
            contents=prompt
        )
        return response.text.split('\n')
    except:
        return []

def run_failsafe_scan(full_text):
    all_lines = []
    # 2000 character chunks for stability
    chunks = [full_text[i:i+2000] for i in range(0, len(full_text), 2000)]
    prog = st.progress(0)
    status = st.empty()
    
    for idx, chunk in enumerate(chunks):
        status.text(f"Scribing CV Section {idx+1} of {len(chunks)}...")
        lines = extract_medical_lines(chunk)
        if lines:
            for line in lines:
                if "|" in line: # Only keep lines that follow our pattern
                    all_lines.append(line)
        prog.progress((idx + 1) / len(chunks))
        time.sleep(1)
    
    status.text("Scribing Complete.")
    return all_lines

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Clinical Portfolio")
        up_file = st.file_uploader("Upload CV", type=['pdf', 'docx'])
        
        if up_file:
            raw_txt = get_raw_text(up_file)
            if raw_txt:
                st.info(f"CV Loaded ({len(raw_txt)} characters)")
                if st.button("🚀 Force Portfolio Sync"):
                    st.session_state.scraped_lines = run_failsafe_scan(raw_txt)
            else:
                st.error("No text detected.")

        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")

    # Helper to parse the "|" lines
    def get_data_by_cat(cat_name):
        results = []
        for line in st.session_state.scraped_lines:
            parts = line.split("|")
            if len(parts) >= 2 and cat_name.upper() in parts[0].upper():
                results.append({
                    "title": parts[1].strip(),
                    "date": parts[2].strip() if len(parts) > 2 else "N/A"
                })
        return results

    tabs = st.tabs(["🌐 Equivalency", "🏥 Experience", "💉 Procedures", "🔬 QIP & Audit", "📄 Raw Scribe"])

    # 1. EQUIVALENCY
    with tabs[0]:
        st.subheader("International Seniority Mapping")
        
        profile_db = supabase_client.table("profiles").select("*").eq("user_email", st.session_state.user_email).execute().data
        curr_tier = profile_db[0].get('global_tier', "Tier 1: Junior (Intern/FY1)") if profile_db else "Tier 1: Junior (Intern/FY1)"
        selected_tier = st.selectbox("Current Grade", list(EQUIVALENCY_MAP.keys()), index=list(EQUIVALENCY_MAP.keys()).index(curr_tier) if curr_tier in EQUIVALENCY_MAP else 0)
        
        map_data = [{"Region": r, "Equivalent Title": EQUIVALENCY_MAP[selected_tier].get(r, "N/A")} for r in ["UK", "US", "Australia", "Poland"]]
        st.table(pd.DataFrame(map_data))

    # 2. EXPERIENCE
    with tabs[1]:
        st.subheader("Clinical Rotations")
        exp = get_data_by_cat("EXPERIENCE")
        if exp:
            for e in exp:
                with st.expander(f"🏥 {e['title']}"):
                    st.write(f"**Dates:** {e['date']}")
        else:
            st.info("No rotations identified.")

    # 3. PROCEDURES
    with tabs[2]:
        st.subheader("Procedural Logbook")
        
        procs = get_data_by_cat("PROCEDURE")
        for p in procs:
            st.write(f"💉 **{p['title']}** — {p['date']}")

    # 4. QIP & AUDIT
    with tabs[3]:
        st.subheader("Quality Improvement")
        
        qips = get_data_by_cat("QIP")
        for q in qips:
            st.write(f"🔬 **{q['title']}** ({q['date']})")

    # 5. RAW SCRIBE
    with tabs[4]:
        st.subheader("Direct AI Output")
        if st.session_state.scraped_lines:
            for line in st.session_state.scraped_lines:
                st.text(line)
        else:
            st.warning("No clinical lines were captured by the AI.")

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
