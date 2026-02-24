import streamlit as st
import pandas as pd
from supabase import create_client
from google import genai
from google.genai import types
import json

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

# --- 2. DATA MAPPING ---
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
if 'temp_parsed' not in st.session_state:
    st.session_state.temp_parsed = None

def handle_login():
    try:
        res = supabase_client.auth.sign_in_with_password({"email": st.session_state.login_email, "password": st.session_state.login_password})
        if res.user:
            st.session_state.authenticated = True
            st.session_state.user_email = res.user.email
    except Exception as e:
        st.error(f"Login failed: {e}")

# --- 4. THE SECTIONAL PARSER ---
def parse_cv_snippet(snippet_text):
    prompt = f"Convert this medical CV snippet into a JSON list of objects. Use relevant keys like 'specialty', 'hospital', 'procedure', 'level', or 'title'. Data: {snippet_text}"
    try:
        response = ai_client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"AI Error: {e}")
        return None

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Clinical Portfolio")
        st.write(f"Logged in: **{st.session_state.user_email}**")
        
        st.divider()
        st.subheader("🤖 AI Section Assistant")
        st.caption("Paste a specific section from your CV below (e.g., just your rotations or just your publications) to avoid payload errors.")
        snippet = st.text_area("Paste CV Snippet here...")
        if st.button("✨ Parse Snippet"):
            with st.spinner("Analyzing..."):
                st.session_state.temp_parsed = parse_cv_snippet(snippet)
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    
    # Show AI Results if available
    if st.session_state.temp_parsed:
        with st.expander("📝 AI Extracted Data (Review & Copy)", expanded=True):
            st.json(st.session_state.temp_parsed)
            st.info("Copy the details above into the relevant tabs below to save them to your permanent record.")

    tabs = st.tabs(["🌐 Equivalency", "🏥 Experience", "💉 Procedures", "🔬 QIP & Audit", "👨‍🏫 Teaching", "📚 Education"])

    # 1. EQUIVALENCY
    with tabs[0]:
        st.subheader("International Seniority Mapping")
        
        profile_db = supabase_client.table("profiles").select("*").eq("user_email", st.session_state.user_email).execute().data
        curr_tier = profile_db[0].get('global_tier', "Tier 1: Junior (Intern/FY1)") if profile_db else "Tier 1: Junior (Intern/FY1)"
        selected_tier = st.selectbox("Current Seniority Tier", list(EQUIVALENCY_MAP.keys()), index=list(EQUIVALENCY_MAP.keys()).index(curr_tier) if curr_tier in EQUIVALENCY_MAP else 0)
        
        target = st.multiselect("Target Jurisdictions", options=["UK", "US", "Australia", "Poland"], default=["UK"])
        map_data = [{"Country": c, "Title": EQUIVALENCY_MAP[selected_tier].get(c, "N/A")} for c in target]
        st.table(pd.DataFrame(map_data))
        
        if st.button("💾 Save Grade"):
            supabase_client.table("profiles").upsert({"user_email": st.session_state.user_email, "global_tier": selected_tier}, on_conflict="user_email").execute()
            st.toast("Saved.")

    # 2. EXPERIENCE
    with tabs[1]:
        st.subheader("Add Clinical Rotation")
        with st.form("add_rotation"):
            col1, col2 = st.columns(2)
            spec = col1.text_input("Specialty (e.g. Cardiology)")
            hosp = col2.text_input("Hospital")
            dates = col1.text_input("Dates (e.g. Aug 2024 - Feb 2025)")
            desc = st.text_area("Key Responsibilities / Achievements")
            if st.form_submit_button("💾 Save Rotation"):
                supabase_client.table("rotations").insert({"user_email": st.session_state.user_email, "description": f"{spec} at {hosp} ({dates}): {desc}"}).execute()
                st.success("Rotation logged.")

    # 3. PROCEDURES
    with tabs[2]:
        st.subheader("Procedural Logbook")
        
        with st.form("add_proc"):
            proc_name = st.text_input("Procedure Name")
            proc_lvl = st.selectbox("Competency Level", ["Observed", "Supervised", "Independent"])
            if st.form_submit_button("💉 Log Procedure"):
                supabase_client.table("procedures").insert({"user_email": st.session_state.user_email, "procedure": proc_name, "level": proc_lvl}).execute()
                st.success("Procedure added.")

    # 4. QIP & AUDIT
    with tabs[3]:
        st.subheader("Quality Improvement Projects")
        
        with st.form("add_qip"):
            qip_title = st.text_input("Project Title")
            qip_cycle = st.selectbox("Cycle Status", ["Initial Audit", "Re-Audit (Closed Loop)", "QIP Phase 1"])
            if st.form_submit_button("🔬 Save QIP"):
                supabase_client.table("projects").insert({"user_email": st.session_state.user_email, "title": qip_title, "type": "QIP"}).execute()
                st.success("QIP logged.")

    # 5. TEACHING
    with tabs[4]:
        st.subheader("Teaching Portfolio")
        with st.form("add_teach"):
            t_topic = st.text_input("Topic")
            t_aud = st.text_input("Audience (e.g. Med Students, Nurses)")
            if st.form_submit_button("👨‍🏫 Save Teaching"):
                supabase_client.table("teaching").insert({"user_email": st.session_state.user_email, "title": t_topic}).execute()
                st.success("Teaching record saved.")

    # 6. EDUCATION
    with tabs[5]:
        st.subheader("Courses & Seminars")
        with st.form("add_edu"):
            e_name = st.text_input("Course/Seminar Name")
            e_year = st.text_input("Year")
            if st.form_submit_button("📚 Save Education"):
                supabase_client.table("education").insert({"user_email": st.session_state.user_email, "course": e_name}).execute()
                st.success("Education record saved.")

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
