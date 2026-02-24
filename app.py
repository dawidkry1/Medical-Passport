import streamlit as st
import pandas as pd
from supabase import create_client
from google import genai
from google.genai import types
import pdfplumber
import docx
import json
import io
import re

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
        # Explicit stable v1 API
        ai_client = genai.Client(
            api_key=st.secrets["GEMINI_API_KEY"],
            http_options={'api_version': 'v1'}
        )
        MODEL_ID = "gemini-1.5-flash" 
    else:
        st.error("⚠️ GEMINI_API_KEY missing in Secrets.")
except Exception as e:
    st.error(f"Config Error: {e}")

# --- 2. GLOBAL MAPPING DATA ---
EQUIVALENCY_MAP = {
    "Tier 1: Junior (Intern/FY1)": {"UK": "Foundation Year 1", "US": "PGY-1 (Intern)", "Australia": "Intern", "Poland": "Lekarz stażysta"},
    "Tier 2: Intermediate (SHO/Resident)": {"UK": "FY2 / Core Trainee", "US": "PGY-2/3 (Resident)", "Australia": "Resident / RMO", "Poland": "Lekarz rezydent (Junior)"},
    "Tier 3: Senior (Registrar/Fellow)": {"UK": "ST3+ / Registrar", "US": "Chief Resident / Fellow", "Australia": "Registrar", "Poland": "Lekarz rezydent (Senior)"},
    "Tier 4: Expert (Consultant/Attending)": {"UK": "Consultant / SAS", "US": "Attending Physician", "Australia": "Consultant / Specialist", "Poland": "Lekarz specjalista"}
}

COUNTRY_KEY_MAP = {"United Kingdom": "UK", "United States": "US", "Australia": "Australia", "Poland": "Poland"}

# --- 3. SESSION STATE ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'parsed_data' not in st.session_state:
    st.session_state.parsed_data = {"rotations": [], "procedures": [], "qips": [], "teaching": [], "education": [], "publications": []}

def handle_login():
    try:
        res = supabase_client.auth.sign_in_with_password({"email": st.session_state.login_email, "password": st.session_state.login_password})
        if res.user:
            st.session_state.authenticated = True
            st.session_state.user_email = res.user.email
    except Exception as e:
        st.error(f"Login failed: {e}")

# --- 4. THE ROBUST CHUNKING PARSER ---
def get_clean_clinical_text(file):
    try:
        raw_text = ""
        if file.name.endswith('.pdf'):
            with pdfplumber.open(file) as pdf:
                raw_text = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        elif file.name.endswith('.docx'):
            doc = docx.Document(file)
            raw_text = "\n".join([p.text for p in doc.paragraphs])
        
        # Aggressive cleaning: Keep only letters, numbers, and basic punctuation
        clean = re.sub(r'[^a-zA-Z0-9\s\.,\-\(\):/]', '', raw_text)
        # Collapse whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        # Return only the first 6000 characters to ensure the payload is lean
        return clean[:6000]
    except Exception as e:
        st.error(f"Extraction error: {e}")
        return ""

def gemini_ai_parse(text):
    # Minimalist prompt to avoid payload bloat
    prompt_text = (
        "Convert this doctor's CV text into a JSON object with these exact keys: "
        "rotations, procedures, qips, teaching, education, publications. "
        f"Text: {text}"
    )
    
    try:
        response = ai_client.models.generate_content(
            model=MODEL_ID,
            contents=prompt_text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0 # Strict accuracy
            )
        )
        return json.loads(response.text)
    except Exception as e:
        if "400" in str(e):
            st.error("🚨 Payload Error: Even with cleaning, the CV formatting is too complex for the AI. Please try a simplified 'plain text' version of your CV.")
        elif "exhausted" in str(e).lower():
            st.error("⏳ Quota Full: Wait 60s and try again.")
        else:
            st.error(f"AI API Error: {e}")
        return None

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Doctor AI Sync")
        st.write(f"Logged in: **{st.session_state.user_email}**")
        up_file = st.file_uploader("Upload CV (Best results with single column)", type=['pdf', 'docx'])
        if up_file and st.button("🚀 Run Clinical Scan"):
            with st.spinner("Executing chunked clinical analysis..."):
                clean_text = get_clean_clinical_text(up_file)
                if clean_text:
                    parsed = gemini_ai_parse(clean_text)
                    if parsed:
                        st.session_state.parsed_data = parsed
                        st.success("Analysis Complete.")
                else:
                    st.error("No extractable text found.")
        
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    
    tabs = st.tabs([
        "🌐 Equivalency", "🏥 Experience", "💉 Procedures", 
        "🔬 QIP & Audit", "👨‍🏫 Teaching", "📚 Seminars & CME", "📄 Export"
    ])

    # 1. EQUIVALENCY
    with tabs[0]:
        st.subheader("International Seniority Mapping")
        
        profile_db = supabase_client.table("profiles").select("*").eq("user_email", st.session_state.user_email).execute().data
        curr_tier = profile_db[0].get('global_tier', "Tier 1: Junior (Intern/FY1)") if profile_db else "Tier 1: Junior (Intern/FY1)"
        selected_tier = st.selectbox("Current Seniority Tier", list(EQUIVALENCY_MAP.keys()), index=list(EQUIVALENCY_MAP.keys()).index(curr_tier) if curr_tier in EQUIVALENCY_MAP else 0)
        
        active_c = st.multiselect("Target Jurisdictions", options=list(COUNTRY_KEY_MAP.keys()), default=["United Kingdom"])
        map_data = [{"Country": c, "Equivalent Title": EQUIVALENCY_MAP[selected_tier].get(COUNTRY_KEY_MAP[c], "N/A")} for c in active_c]
        st.table(pd.DataFrame(map_data))
        
        if st.button("💾 Update Global Profile"):
            supabase_client.table("profiles").upsert({"user_email": st.session_state.user_email, "global_tier": selected_tier}, on_conflict="user_email").execute()
            st.toast("Profile Synced.")

    # 2. EXPERIENCE
    with tabs[1]:
        st.subheader("Clinical Rotations")
        for i, item in enumerate(st.session_state.parsed_data.get("rotations", [])):
            with st.expander(f"{item.get('specialty', 'Unknown')} - {item.get('hospital', 'Unknown')}"):
                st.write(f"**Dates:** {item.get('dates')}")
                st.info(item.get('description', 'No details.'))

    # 3. PROCEDURES
    with tabs[2]:
        st.subheader("Procedural Logbook")
        
        for item in st.session_state.parsed_data.get("procedures", []):
            st.write(f"💉 {item.get('name')} — **{item.get('level')}**")

    # 4. QIP & AUDIT
    with tabs[3]:
        st.subheader("Quality Improvement & Clinical Audit")
        
        for item in st.session_state.parsed_data.get("qips", []):
            st.write(f"🔬 **{item.get('title', 'Audit')}** ({item.get('cycle', 'Cycle')})")

    # 5. TEACHING
    with tabs[4]:
        st.subheader("Teaching Portfolio")
        for item in st.session_state.parsed_data.get("teaching", []):
            st.write(f"👨‍🏫 **{item.get('topic')}** for {item.get('audience')}")

    # 6. SEMINARS & CME
    with tabs[5]:
        st.subheader("Educational Courses")
        for item in st.session_state.parsed_data.get("education", []):
            st.write(f"📚 {item.get('course', 'Course')} ({item.get('year', 'N/A')}) — {item.get('hours', 'N/A')} hours")

    # 7. EXPORT
    with tabs[6]:
        st.subheader("Portfolio Generation")
        st.info("Ready to build your verified international clinical passport.")
        st.button("🏗️ Build Professional Passport PDF")

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Passport Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
