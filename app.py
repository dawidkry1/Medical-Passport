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
if 'all_entries' not in st.session_state:
    st.session_state.all_entries = []

def handle_login():
    try:
        res = supabase_client.auth.sign_in_with_password({"email": st.session_state.login_email, "password": st.session_state.login_password})
        if res.user:
            st.session_state.authenticated = True
            st.session_state.user_email = res.user.email
    except Exception as e:
        st.error(f"Login failed: {e}")

# --- 4. THE AGGRESSIVE EXTRACTOR ---
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

def ai_extract_clinical_events(chunk_text):
    # We ask for a simple list of events. This is much easier for the AI to fulfill.
    prompt = (
        "You are a medical scribe. Look at this CV text and list every clinical activity, "
        "job, procedure, audit, or course you find. "
        "Return a JSON list of objects called 'events'. "
        "Each object must have: 'category' (rotation, procedure, qip, teaching, or education), "
        "'title', 'details', and 'date'. "
        f"\n\nText: {chunk_text}"
    )
    try:
        response = ai_client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = json.loads(response.text)
        return data.get("events", [])
    except:
        return []

def run_deep_scan(full_text):
    all_found = []
    # 2500 character chunks
    segments = [full_text[i:i+2500] for i in range(0, len(full_text), 2500)]
    prog = st.progress(0)
    
    for idx, seg in enumerate(segments):
        events = ai_extract_clinical_events(seg)
        if events:
            all_found.extend(events)
        prog.progress((idx + 1) / len(segments))
        time.sleep(1)
        
    return all_found

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Doctor-to-Doctor Sync")
        up_file = st.file_uploader("Upload CV (PDF/DOCX)", type=['pdf', 'docx'])
        if up_file:
            raw = get_raw_text(up_file)
            if raw and st.button("🚀 Re-Scan Clinical History"):
                st.session_state.all_entries = run_deep_scan(raw)
                if st.session_state.all_entries:
                    st.success(f"Found {len(st.session_state.all_entries)} clinical records.")
                else:
                    st.error("AI scanned the text but couldn't identify specific medical activities. Is the file protected?")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")

    # Filter data for tabs
    def get_by_cat(cat_list):
        return [e for e in st.session_state.all_entries if str(e.get('category')).lower() in cat_list]

    tabs = st.tabs(["🌐 Equivalency", "🏥 Experience", "💉 Procedures", "🔬 QIP & Audit", "👨‍🏫 Teaching", "📚 Education"])

    # 1. EQUIVALENCY
    with tabs[0]:
        st.subheader("International Seniority Mapping")
        
        profile_db = supabase_client.table("profiles").select("*").eq("user_email", st.session_state.user_email).execute().data
        curr_tier = profile_db[0].get('global_tier', "Tier 1: Junior (Intern/FY1)") if profile_db else "Tier 1: Junior (Intern/FY1)"
        selected_tier = st.selectbox("Current Seniority", list(EQUIVALENCY_MAP.keys()), index=list(EQUIVALENCY_MAP.keys()).index(curr_tier) if curr_tier in EQUIVALENCY_MAP else 0)
        
        map_data = []
        for c in ["UK", "US", "Australia", "Poland"]:
            map_data.append({"Country": c, "Equivalent Title": EQUIVALENCY_MAP[selected_tier].get(c, "N/A")})
        st.table(pd.DataFrame(map_data))

    # 2. EXPERIENCE
    with tabs[1]:
        st.subheader("Clinical Rotations")
        rotations = get_by_cat(["rotation", "experience", "job", "work"])
        if not rotations: st.info("No rotations identified yet.")
        for r in rotations:
            with st.expander(f"🏥 {r.get('title', 'Medical Placement')}"):
                st.write(f"**Date:** {r.get('date', 'N/A')}")
                st.write(r.get('details', ''))

    # 3. PROCEDURES
    with tabs[2]:
        st.subheader("Procedural Logbook")
        
        procs = get_by_cat(["procedure", "skill", "clinical skill"])
        for p in procs:
            st.write(f"💉 {p.get('title')} — *{p.get('details', 'Logged')}*")

    # 4. QIP & AUDIT
    with tabs[3]:
        st.subheader("Quality Improvement")
        
        qips = get_by_cat(["qip", "audit", "project"])
        for q in qips:
            st.write(f"🔬 **{q.get('title')}** ({q.get('date')})")

    # 5. TEACHING
    with tabs[4]:
        st.subheader("Teaching Portfolio")
        teaching = get_by_cat(["teaching", "presentation", "lecture"])
        for t in teaching:
            st.write(f"👨‍🏫 **{t.get('title')}** — {t.get('details')}")
    
    # 6. EDUCATION
    with tabs[5]:
        st.subheader("Education & CME")
        edu = get_by_cat(["education", "course", "seminar", "degree"])
        for e in edu:
            st.write(f"📚 {e.get('title')} ({e.get('date')})")

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
