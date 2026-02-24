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
if 'raw_records' not in st.session_state:
    st.session_state.raw_records = []

def handle_login():
    try:
        res = supabase_client.auth.sign_in_with_password({"email": st.session_state.login_email, "password": st.session_state.login_password})
        if res.user:
            st.session_state.authenticated = True
            st.session_state.user_email = res.user.email
    except Exception as e:
        st.error(f"Login failed: {e}")

# --- 4. THE ULTIMATE SCRAPER ---
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

def ai_unstructured_extract(chunk_text):
    """Tell the AI to be less picky and just grab everything."""
    prompt = (
        "As a medical recruitment assistant, extract EVERY clinical activity from this text. "
        "Include jobs, rotations, procedures, audits, teaching, and education. "
        "Format as a JSON list of objects under the key 'data'. "
        "Each object must have: 'category', 'title', 'organization', and 'date'. "
        "Categories must be: 'Rotation', 'Procedure', 'Audit', 'Teaching', or 'Education'. "
        f"\n\nCV Text: {chunk_text}"
    )
    try:
        response = ai_client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
        )
        return json.loads(response.text).get("data", [])
    except:
        return []

def run_deep_scan(full_text):
    found_data = []
    # Smaller chunks for high precision
    segments = [full_text[i:i+2000] for i in range(0, len(full_text), 2000)]
    prog = st.progress(0)
    
    for idx, seg in enumerate(segments):
        res = ai_unstructured_extract(seg)
        if res:
            found_data.extend(res)
        prog.progress((idx + 1) / len(segments))
        time.sleep(1)
        
    return found_data

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🏥 Doctor Portfolio Sync")
        up_file = st.file_uploader("Upload CV", type=['pdf', 'docx'])
        if up_file:
            txt = get_raw_text(up_file)
            if txt and st.button("🚀 Force Clinical Extraction"):
                with st.spinner("AI is scraping clinical data..."):
                    st.session_state.raw_records = run_deep_scan(txt)
                    if st.session_state.raw_records:
                        st.success(f"Successfully scraped {len(st.session_state.raw_records)} clinical items.")
                    else:
                        st.warning("AI found text but no items. Try a version of your CV with less formatting.")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")

    # Layout for Clinical Data
    tabs = st.tabs(["🌐 Equivalency", "🏥 Clinical Records", "🔬 QIP/Audits", "👨‍🏫 Portfolio Review"])

    # 1. EQUIVALENCY
    with tabs[0]:
        st.subheader("International Seniority Mapping")
        
        profile_db = supabase_client.table("profiles").select("*").eq("user_email", st.session_state.user_email).execute().data
        curr_tier = profile_db[0].get('global_tier', "Tier 1: Junior (Intern/FY1)") if profile_db else "Tier 1: Junior (Intern/FY1)"
        selected_tier = st.selectbox("Current Seniority", list(EQUIVALENCY_MAP.keys()), index=list(EQUIVALENCY_MAP.keys()).index(curr_tier) if curr_tier in EQUIVALENCY_MAP else 0)
        
        map_data = []
        for c in ["UK", "US", "Australia", "Poland"]:
            map_data.append({"Country": c, "Title": EQUIVALENCY_MAP[selected_tier].get(c, "N/A")})
        st.table(pd.DataFrame(map_data))

    # 2. CLINICAL RECORDS (Rotation + Procedures combined for visibility)
    with tabs[1]:
        st.subheader("Extracted Clinical Experience")
        records = [r for r in st.session_state.raw_records if r.get('category') in ['Rotation', 'Procedure']]
        if not records: st.info("No rotations or procedures identified yet.")
        for r in records:
            icon = "🏥" if r.get('category') == 'Rotation' else "💉"
            with st.expander(f"{icon} {r.get('title')} - {r.get('organization')}"):
                st.write(f"**Date:** {r.get('date', 'N/A')}")
                st.write(f"**Category:** {r.get('category')}")

    # 3. QIP & AUDITS
    with tabs[2]:
        st.subheader("Quality Improvement & Research")
        
        qips = [r for r in st.session_state.raw_records if r.get('category') == 'Audit']
        for q in qips:
            st.write(f"🔬 **{q.get('title')}** ({q.get('date')})")

    # 4. PORTFOLIO REVIEW (The "Safety" view)
    with tabs[3]:
        st.subheader("Raw AI Findings")
        st.write("This tab shows everything the AI found, regardless of how it was categorized.")
        if st.session_state.raw_records:
            df = pd.DataFrame(st.session_state.raw_records)
            st.dataframe(df, use_container_width=True)
            if st.button("💾 Push All to Database"):
                # Logic to push to Supabase
                st.toast("Syncing with Cloud Database...")
        else:
            st.warning("No raw data to display.")

# --- LOGIN GATE ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Passport Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
