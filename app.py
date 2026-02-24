import streamlit as st
import pandas as pd
from supabase import create_client
from google import genai
from google.genai import types
import pdfplumber
import docx
import json
import io
import time

# --- 1. CORE CONFIG ---
st.set_page_config(page_title="Global Medical Passport", page_icon="🏥", layout="wide")

# Connection Setup
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase_client = create_client(URL, KEY)
    
    if "GEMINI_API_KEY" in st.secrets:
        ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        # Using 1.5 Flash as it typically has more generous free-tier limits than 2.0
        MODEL_ID = "gemini-1.5-flash" 
    else:
        st.error("⚠️ GEMINI_API_KEY missing in Secrets.")
except Exception as e:
    st.error(f"Config Error: {e}")

# --- 2. MAPPING DATA ---
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

# --- 4. PARSER WITH QUOTA RETRY ---
def get_raw_text(file):
    try:
        if file.name.endswith('.pdf'):
            with pdfplumber.open(file) as pdf:
                return "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        elif file.name.endswith('.docx'):
            doc = docx.Document(file)
            return "\n".join([p.text for p in doc.paragraphs])
    except: return ""

def gemini_ai_parse(text):
    prompt = f"""
    Extract the following Doctor's CV into a JSON object. 
    Separate content strictly into: rotations, procedures, qips, teaching, education (seminars), and publications.
    Return ONLY JSON.
    CV Text: {text}
    """
    # Simple retry logic for "Resource Exhausted"
    for attempt in range(3):
        try:
            response = ai_client.models.generate_content(
                model=MODEL_ID,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return json.loads(response.text)
        except Exception as e:
            if "429" in str(e) or "exhausted" in str(e).lower():
                st.warning(f"Quota reached. Retrying in {5 * (attempt + 1)}s...")
                time.sleep(5 * (attempt + 1))
            else:
                st.error(f"AI Error: {e}")
                break
    return None

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Doctor AI Sync")
        up_file = st.file_uploader("Upload CV", type=['pdf', 'docx'])
        if up_file and st.button("🚀 Run Gemini Scan"):
            with st.spinner("AI is analyzing clinical history..."):
                raw_text = get_raw_text(up_file)
                parsed = gemini_ai_parse(raw_text)
                if parsed:
                    st.session_state.parsed_data = parsed
                    st.success("Analysis Complete.")
        
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    
    tabs = st.tabs(["🌐 Equivalency", "🏥 Experience", "💉 Procedures", "🔬 QIP & Audit", "👨‍🏫 Teaching", "📚 Education/Seminars", "📄 Export"])

    # 1. EQUIVALENCY
    with tabs[0]:
        st.subheader("International Seniority Mapping")
        
        profile_db = supabase_client.table("profiles").select("*").eq("user_email", st.session_state.user_email).execute().data
        curr_tier = profile_db[0].get('global_tier', "Tier 1: Junior (Intern/FY1)") if profile_db else "Tier 1: Junior (Intern/FY1)"
        selected_tier = st.selectbox("Current Tier", list(EQUIVALENCY_MAP.keys()), index=list(EQUIVALENCY_MAP.keys()).index(curr_tier) if curr_tier in EQUIVALENCY_MAP else 0)
        
        active_c = st.multiselect("Target Systems", options=list(COUNTRY_KEY_MAP.keys()), default=["United Kingdom"])
        map_data = [{"Country": c, "Equivalent Title": EQUIVALENCY_MAP[selected_tier].get(COUNTRY_KEY_MAP[c], "N/A")} for c in active_c]
        st.table(pd.DataFrame(map_data))
        
        if st.button("💾 Save Profile"):
            supabase_client.table("profiles").upsert({"user_email": st.session_state.user_email, "global_tier": selected_tier}, on_conflict="user_email").execute()
            st.toast("Profile Synced.")

    # 2. EXPERIENCE
    with tabs[1]:
        st.subheader("Clinical Rotations")
        for i, item in enumerate(st.session_state.parsed_data.get("rotations", [])):
            with st.expander(f"{item.get('specialty', 'Rotation')} at {item.get('hospital', 'Hospital')}"):
                st.write(f"**Dates:** {item.get('dates')}")
                st.info(item.get('description'))

    # 3. PROCEDURES
    with tabs[2]:
        st.subheader("Procedural Logbook")
        
        for i, item in enumerate(st.session_state.parsed_data.get("procedures", [])):
            st.write(f"💉 {item.get('name')} — **Level: {item.get('level')}**")

    # 4. QIP & AUDIT
    with tabs[3]:
        st.subheader("Quality Improvement & Audits")
        
        for i, item in enumerate(st.session_state.parsed_data.get("qips", [])):
            st.write(f"🔬 **{item.get('title')}** | Cycle: {item.get('cycle')}")
            st.caption(f"Outcome: {item.get('outcome', 'N/A')}")

    # 5. TEACHING
    with tabs[4]:
        st.subheader("Teaching Portfolio")
        for i, item in enumerate(st.session_state.parsed_data.get("teaching", [])):
            st.write(f"👨‍🏫 **{item.get('topic')}**")
            st.write(f"Audience: {item.get('audience')} | Details: {item.get('details')}")

    # 6. EDUCATION & SEMINARS
    with tabs[5]:
        st.subheader("Seminars, Courses & CME")
        for i, item in enumerate(st.session_state.parsed_data.get("education", [])):
            st.write(f"📚 **{item.get('course')}** ({item.get('year', 'N/A')})")
            st.write(f"Hours Logged: {item.get('hours', 'N/A')}")

    # 7. EXPORT
    with tabs[6]:
        st.subheader("Passport Generation")
        st.button("🏗️ Build Verified PDF Portfolio")

# --- LOGIN GATE ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
