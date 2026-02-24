import streamlit as st
import pandas as pd
from supabase import create_client
from fpdf import FPDF
import pdfplumber
import docx
import json
import io
import re

# --- 1. CORE CONFIG & STYLING ---
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
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
client = create_client(URL, KEY)

# --- 2. GLOBAL MAPPING DATA ---
EQUIVALENCY_MAP = {
    "Tier 1: Junior (Intern/FY1)": {
        "UK": "Foundation Year 1", "US": "PGY-1 (Intern)", "Australia": "Intern",
        "Ireland": "Intern", "Canada": "PGY-1", "Dubai/DHA": "Intern", "Poland": "Lekarz stażysta"
    },
    "Tier 2: Intermediate (SHO/Resident)": {
        "UK": "FY2 / Core Trainee", "US": "PGY-2/3 (Resident)", "Australia": "Resident / RMO",
        "Ireland": "SHO", "Canada": "Junior Resident", "Dubai/DHA": "GP / Resident", "Poland": "Lekarz rezydent (Junior)"
    },
    "Tier 3: Senior (Registrar/Fellow)": {
        "UK": "ST3+ / Registrar", "US": "Chief Resident / Fellow", "Australia": "Registrar",
        "Ireland": "Specialist Registrar (SpR)", "Canada": "Senior Resident / Fellow", "Dubai/DHA": "Specialist (P)", "Poland": "Lekarz rezydent (Senior)"
    },
    "Tier 4: Expert (Consultant/Attending)": {
        "UK": "Consultant / SAS", "US": "Attending Physician", "Australia": "Consultant / Specialist",
        "Ireland": "Consultant", "Canada": "Staff Specialist", "Dubai/DHA": "Consultant", "Poland": "Lekarz specjalista"
    }
}

COUNTRY_KEY_MAP = {
    "United Kingdom": "UK", "United States": "US", "Australia": "Australia",
    "Ireland": "Ireland", "Canada": "Canada", "Dubai (DHA)": "Dubai/DHA", "Poland": "Poland"
}

# --- 3. SESSION & AUTH ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'parsed_data' not in st.session_state:
    st.session_state.parsed_data = {
        "rotations": [], "procedures": [], "qips": [], "teaching": [], 
        "education": [], "registrations": [], "raw": ""
    }

def handle_login():
    try:
        res = client.auth.sign_in_with_password({"email": st.session_state.login_email, "password": st.session_state.login_password})
        if res.user:
            st.session_state.authenticated = True
            st.session_state.user_email = res.user.email
    except Exception as e:
        st.error(f"Login failed: {e}")

def fetch_user_data(table_name):
    if not st.session_state.user_email: return []
    try:
        res = client.table(table_name).select("*").eq("user_email", st.session_state.user_email).execute()
        return res.data if res.data else []
    except Exception: return []

# --- 4. GRANULAR CLINICAL PARSER ---
def get_raw_text(file):
    try:
        if file.name.endswith('.pdf'):
            with pdfplumber.open(file) as pdf:
                return "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        elif file.name.endswith('.docx'):
            doc = docx.Document(file)
            return "\n".join([p.text for p in doc.paragraphs])
    except: return ""

def granular_scan_parse(file):
    text = get_raw_text(file)
    st.session_state.parsed_data["raw"] = text
    blocks = text.split('\n\n') if '\n\n' in text else text.split('\n')
    
    triage = {
        "rotations": [], "procedures": [], "qips": [], 
        "teaching": [], "education": [], "registrations": [], "raw": text
    }
    
    # Keyword sets for specific medical domains
    kw = {
        "reg": ["gmc", "license", "registration", "mrcp", "mrcs", "board", "pwz"],
        "proc": ["intubation", "suturing", "cannulation", "procedure", "performed", "competenc", "drain"],
        "qip": ["audit", "qip", "quality improvement", "cycle", "re-audit", "closed loop"],
        "teach": ["teaching", "lectured", "tutoring", "mentoring", "bedside teaching"],
        "edu": ["seminar", "conference", "course", "als", "bls", "atls", "webinar", "cme", "cpd"],
        "rot": ["hospital", "trust", "ward", "department", "rotation", "resident", "intern"]
    }

    for block in blocks:
        clean = block.strip()
        if len(clean) < 5: continue
        low = clean.lower()
        
        if any(k in low for k in kw["reg"]): triage["registrations"].append(clean)
        elif any(k in low for k in kw["proc"]): triage["procedures"].append(clean)
        elif any(k in low for k in kw["qip"]): triage["qips"].append(clean)
        elif any(k in low for k in kw["teach"]): triage["teaching"].append(clean)
        elif any(k in low for k in kw["edu"]): triage["education"].append(clean)
        elif any(k in low for k in kw["rot"]) or re.search(r'\b(20\d{2})\b', low): triage["rotations"].append(clean)
            
    return triage

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Global Passport Sync")
        st.write(f"Logged in: **{st.session_state.user_email}**")
        up_file = st.file_uploader("Upload Medical CV", type=['pdf', 'docx'])
        if up_file and st.button("🚀 Deep Sync Portfolio"):
            st.session_state.parsed_data = granular_scan_parse(up_file)
            st.success("Portfolio Analyzed.")
        
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    
    tabs = st.tabs(["🌐 Equivalency", "🏥 Experience", "💉 Procedures", "🔬 QIP & Audit", "👨‍🏫 Teaching", "📚 Education", "📄 Export"])

    # 1. EQUIVALENCY
    with tabs[0]:
        st.subheader("International Seniority Mapping")
        profile_db = fetch_user_data("profiles")
        has_profile = len(profile_db) > 0
        curr_tier = profile_db[0].get('global_tier', "Tier 1: Junior (Intern/FY1)") if has_profile else "Tier 1: Junior (Intern/FY1)"
        selected_tier = st.selectbox("Seniority Level", list(EQUIVALENCY_MAP.keys()), index=list(EQUIVALENCY_MAP.keys()).index(curr_tier) if curr_tier in EQUIVALENCY_MAP else 0)
        
        saved_c = ["United Kingdom"]
        if has_profile:
            try: saved_c = json.loads(profile_db[0].get('selected_countries', "[]"))
            except: pass
        active_c = st.multiselect("Target Systems", options=list(COUNTRY_KEY_MAP.keys()), default=saved_c)
        
        map_data = [{"Country": c, "Title": EQUIVALENCY_MAP[selected_tier].get(COUNTRY_KEY_MAP[c], "N/A")} for c in active_c]
        st.table(pd.DataFrame(map_data))
        
        if st.button("💾 Save Profile"):
            client.table("profiles").upsert({"user_email": st.session_state.user_email, "global_tier": selected_tier, "selected_countries": json.dumps(active_c)}, on_conflict="user_email").execute()
            st.toast("Profile Synced.")

    # 2. EXPERIENCE
    with tabs[1]:
        st.subheader("Clinical Rotations")
        for i, block in enumerate(st.session_state.parsed_data.get("rotations", [])):
            with st.expander(f"Review Rotation {i+1}"):
                full = st.text_area("Details", block, key=f"rt_{i}")
                if st.button("Save Rotation", key=f"rb_{i}"):
                    client.table("rotations").insert({"user_email": st.session_state.user_email, "description": full}).execute()

    # 3. PROCEDURES
    with tabs[2]:
        st.subheader("Procedural Logbook")
        
        for i, block in enumerate(st.session_state.parsed_data.get("procedures", [])):
            with st.expander(f"Skill {i+1}"):
                p = st.text_input("Procedure", block[:100], key=f"pn_{i}")
                lvl = st.selectbox("Level", ["Observed", "Supervised", "Independent"], key=f"pl_{i}")
                if st.button("Log Procedure", key=f"pb_{i}"):
                    client.table("procedures").insert({"user_email": st.session_state.user_email, "procedure": p, "level": lvl}).execute()

    # 4. QIP & AUDIT (New Specific Logic)
    with tabs[3]:
        st.subheader("Quality Improvement & Clinical Audits")
        
        found_qips = st.session_state.parsed_data.get("qips", [])
        for i, block in enumerate(found_qips):
            with st.expander(f"Detected QIP/Audit {i+1}"):
                title = st.text_input("Project Title", block[:150], key=f"qn_{i}")
                cycle = st.selectbox("Cycle Status", ["Initial Audit", "Re-audit (Closed Loop)", "Sustained Improvement"], key=f"qc_{i}")
                if st.button("Save Project", key=f"qb_{i}"):
                    client.table("projects").insert({"user_email": st.session_state.user_email, "title": title, "type": "QIP", "notes": cycle}).execute()

    # 5. TEACHING
    with tabs[4]:
        st.subheader("Teaching & Leadership")
        for i, block in enumerate(st.session_state.parsed_data.get("teaching", [])):
            with st.expander(f"Teaching Entry {i+1}"):
                title = st.text_input("Session Title", block[:100], key=f"tn_{i}")
                audience = st.text_input("Target Audience (e.g., Medical Students)", key=f"ta_{i}")
                if st.button("Log Teaching", key=f"tb_{i}"):
                    client.table("teaching").insert({"user_email": st.session_state.user_email, "title": title, "audience": audience}).execute()

    # 6. EDUCATION & SEMINARS
    with tabs[5]:
        st.subheader("Education, Courses & CME")
        for i, block in enumerate(st.session_state.parsed_data.get("education", [])):
            with st.expander(f"Seminar/Course {i+1}"):
                title = st.text_input("Course Name", block[:100], key=f"en_{i}")
                hours = st.number_input("CPD/CME Hours", min_value=0.5, step=0.5, key=f"eh_{i}")
                if st.button("Log Education", key=f"eb_{i}"):
                    client.table("education").insert({"user_email": st.session_state.user_email, "course": title, "hours": hours}).execute()

    # 7. EXPORT
    with tabs[6]:
        st.subheader("Final Clinical Passport")
        st.write("Generate a standardized portfolio that translates your experience into international equivalents.")
        if st.button("🏗️ Build Full PDF Portfolio"):
            st.info("Compiling all rotations, procedures, QIPs, and teaching records...")

# --- AUTH GATE ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Passport Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
