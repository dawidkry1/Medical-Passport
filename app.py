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
if 'parsed_data' not in st.session_state:
    st.session_state.parsed_data = {"rotations": [], "procedures": [], "qips": [], "teaching": [], "education": []}

def handle_login():
    try:
        res = supabase_client.auth.sign_in_with_password({"email": st.session_state.login_email, "password": st.session_state.login_password})
        if res.user:
            st.session_state.authenticated = True
            st.session_state.user_email = res.user.email
    except Exception as e:
        st.error(f"Login failed: {e}")

# --- 4. ROBUST EXTRACTION & SMART CHUNKING ---
def get_raw_text(file):
    text = ""
    try:
        if file.name.endswith('.pdf'):
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
        elif file.name.endswith('.docx'):
            doc = docx.Document(file)
            text = "\n".join([p.text for p in doc.paragraphs])
        return text.strip()
    except: return ""

def ai_process_chunk(chunk_text):
    # A more "desperate" prompt that tells the AI to find ANYTHING medical.
    prompt = (
        "Identify every medical detail in this text. "
        "Sort them into these categories: rotations, procedures, qips, teaching, education. "
        "Even if a detail is vague, include it. Use generic field names. "
        "Return ONLY valid JSON."
        f"\n\nText: {chunk_text}"
    )
    try:
        response = ai_client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except:
        return None

def run_deep_scan(full_text):
    combined = {"rotations": [], "procedures": [], "qips": [], "teaching": [], "education": []}
    # Break into 3000-character segments
    segments = [full_text[i:i+3000] for i in range(0, len(full_text), 3000)]
    
    prog = st.progress(0)
    status = st.empty()
    
    for idx, seg in enumerate(segments):
        status.text(f"Scanning Section {idx+1} of {len(segments)}...")
        res = ai_process_chunk(seg)
        if res:
            for key in combined:
                if key in res and isinstance(res[key], list):
                    combined[key].extend(res[key])
        prog.progress((idx + 1) / len(segments))
        time.sleep(1)
        
    status.text("Scan Complete.")
    return combined

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Clinical Portfolio")
        up_file = st.file_uploader("Upload Medical CV", type=['pdf', 'docx'])
        
        if up_file:
            raw_text = get_raw_text(up_file)
            if raw_text:
                st.success("File Content Extracted.")
                if st.button("🚀 Run Deep Clinical Scan"):
                    st.session_state.parsed_data = run_deep_scan(raw_text)
            else:
                st.error("No text found in file.")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    
    tabs = st.tabs(["🌐 Equivalency", "🏥 Experience", "💉 Procedures", "🔬 QIP & Audit", "👨‍🏫 Teaching", "📚 Education"])

    # 1. EQUIVALENCY
    with tabs[0]:
        st.subheader("International Seniority Mapping")
        
        profile_db = supabase_client.table("profiles").select("*").eq("user_email", st.session_state.user_email).execute().data
        curr_tier = profile_db[0].get('global_tier', "Tier 1: Junior (Intern/FY1)") if profile_db else "Tier 1: Junior (Intern/FY1)"
        selected_tier = st.selectbox("Current Level", list(EQUIVALENCY_MAP.keys()), index=list(EQUIVALENCY_MAP.keys()).index(curr_tier) if curr_tier in EQUIVALENCY_MAP else 0)
        
        targets = ["UK", "US", "Australia", "Poland"]
        map_data = [{"Country": c, "Title": EQUIVALENCY_MAP[selected_tier].get(c, "N/A")} for c in targets]
        st.table(pd.DataFrame(map_data))

    # 2. EXPERIENCE
    with tabs[1]:
        st.subheader("Clinical Rotations")
        items = st.session_state.parsed_data.get("rotations", [])
        if not items: st.warning("AI did not label any 'rotations'. Check your file for keywords like 'Resident', 'Intern', or 'Department'.")
        for i, item in enumerate(items):
            # Dynamic Labeling: Show whatever data is available
            label = next((item[k] for k in ['specialty', 'title', 'role', 'department'] if k in item), f"Experience {i+1}")
            with st.expander(f"📍 {label}"):
                st.write(item)

    # 3. PROCEDURES
    with tabs[2]:
        st.subheader("Procedural Logbook")
        
        items = st.session_state.parsed_data.get("procedures", [])
        if not items: st.info("No procedures identified.")
        for item in items:
            name = next((item[k] for k in ['name', 'procedure', 'skill'] if k in item), "Medical Procedure")
            lvl = next((item[k] for k in ['level', 'competency', 'status'] if k in item), "N/A")
            st.write(f"💉 {name} — **{lvl}**")

    # 4. QIP & AUDIT
    with tabs[3]:
        st.subheader("Quality Improvement")
        
        items = st.session_state.parsed_data.get("qips", [])
        for item in items:
            st.write(f"🔬 {item}")

    # 5. TEACHING & EDUCATION
    with tabs[4]:
        for item in st.session_state.parsed_data.get("teaching", []):
            st.write(f"👨‍🏫 {item}")
    
    with tabs[5]:
        for item in st.session_state.parsed_data.get("education", []):
            st.write(f"📚 {item}")

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
    main_dashboard()
