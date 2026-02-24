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
        "Ireland": "Intern", "Canada": "PGY-1", "Dubai/DHA": "Intern",
        "India/Pakistan": "House Officer / Intern", "Nigeria": "House Officer",
        "China/S.Korea": "Junior Resident", "Europe": "Junior Doctor",
        "Poland": "Lekarz stażysta"
    },
    "Tier 2: Intermediate (SHO/Resident)": {
        "UK": "FY2 / Core Trainee", "US": "PGY-2/3 (Resident)", "Australia": "Resident / RMO",
        "Ireland": "SHO", "Canada": "Junior Resident", "Dubai/DHA": "GP / Resident",
        "India/Pakistan": "PG Resident / Medical Officer", "Nigeria": "Registrar",
        "China/S.Korea": "Resident", "Europe": "Resident Physician",
        "Poland": "Lekarz rezydent (Junior)"
    },
    "Tier 3: Senior (Registrar/Fellow)": {
        "UK": "ST3+ / Registrar", "US": "Chief Resident / Fellow", "Australia": "Registrar",
        "Ireland": "Specialist Registrar (SpR)", "Canada": "Senior Resident / Fellow", "Dubai/DHA": "Specialist (P)",
        "India/Pakistan": "Senior Resident / Registrar", "Nigeria": "Senior Registrar",
        "China/S.Korea": "Attending Physician / Fellow", "Europe": "Specialist Trainee / Senior Registrar",
        "Poland": "Lekarz rezydent (Senior)"
    },
    "Tier 4: Expert (Consultant/Attending)": {
        "UK": "Consultant / SAS", "US": "Attending Physician", "Australia": "Consultant / Specialist",
        "Ireland": "Consultant", "Canada": "Staff Specialist", "Dubai/DHA": "Consultant",
        "India/Pakistan": "Consultant / Asst. Professor", "Nigeria": "Consultant",
        "China/S.Korea": "Chief Physician", "Europe": "Specialist / Consultant",
        "Poland": "Lekarz specjalista"
    }
}

COUNTRY_KEY_MAP = {
    "United Kingdom": "UK", "United States": "US", "Australia": "Australia",
    "Ireland": "Ireland", "Canada": "Canada", "Dubai (DHA)": "Dubai/DHA",
    "India & Pakistan": "India/Pakistan", "Nigeria": "Nigeria",
    "China & S.Korea": "China/S.Korea", "Europe (General)": "Europe",
    "Poland": "Poland"
}

# --- 3. SESSION & AUTH ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'parsed_data' not in st.session_state:
    st.session_state.parsed_data = {"rotations": [], "procedures": [], "projects": [], "registrations": [], "fragments": []}

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
    except Exception:
        return []

# --- 4. IMPROVED "GLUE" PARSER ---
def get_clean_text(file):
    try:
        if file.name.endswith('.pdf'):
            with pdfplumber.open(file) as pdf:
                return "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        elif file.name.endswith('.docx'):
            doc = docx.Document(file)
            return "\n".join([p.text for p in doc.paragraphs])
    except: return ""
    return ""

def deep_clinical_parse(file):
    text = get_clean_text(file)
    if not text: return st.session_state.parsed_data
    
    lines = text.split('\n')
    triage = {"rotations": [], "procedures": [], "projects": [], "registrations": [], "fragments": []}
    current_block = []
    
    # Looking for a Date Range or a Year at the START of a line
    date_header_pattern = r'^(\d{4}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Present|Current)'

    for line in lines:
        clean_line = line.strip()
        if not clean_line: continue
        
        # If line starts with a date, it's a likely new experience
        if re.match(date_header_pattern, clean_line, re.IGNORECASE):
            if current_block:
                full_content = "\n".join(current_block)
                low = full_content.lower()
                # Sort by keyword
                if any(k in low for k in ["gmc", "license", "registration"]): triage["registrations"].append(full_content)
                elif any(k in low for k in ["audit", "qip", "research"]): triage["projects"].append(full_content)
                elif any(k in low for k in ["procedure", "intubation", "suturing"]): triage["procedures"].append(full_content)
                elif any(k in low for k in ["hospital", "trust", "ward", "szpital"]): triage["rotations"].append(full_content)
                else: triage["fragments"].append(full_content)
            current_block = [clean_line]
        else:
            current_block.append(clean_line)

    if current_block: triage["rotations"].append("\n".join(current_block))
    return triage

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Global Sync")
        st.write(f"Logged in: **{st.session_state.user_email}**")
        up_file = st.file_uploader("Upload CV", type=['pdf', 'docx'])
        if up_file and st.button("🚀 Process Passport"):
            st.session_state.parsed_data = deep_clinical_parse(up_file)
            st.success("Triage Complete.")
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    profile = fetch_user_data("profiles")
    rotations = fetch_user_data("rotations")
    procedures = fetch_user_data("procedures")
    projects = fetch_user_data("projects")

    tabs = st.tabs(["🌐 Equivalency", "🪪 Registration", "🏥 Experience", "💉 Procedures", "🔬 Academic", "🛡️ Vault"])

    # 🌐 EQUIVALENCY (Fixed Line 232 error)
    with tabs[0]:
        st.subheader("International Equivalency")
        # Defensive check for profile
        has_profile = len(profile) > 0
        curr_tier = profile[0].get('global_tier', "Tier 1: Junior (Intern/FY1)") if has_profile else "Tier 1: Junior (Intern/FY1)"
        
        selected_tier = st.selectbox("Current Seniority", list(EQUIVALENCY_MAP.keys()), index=list(EQUIVALENCY_MAP.keys()).index(curr_tier) if curr_tier in EQUIVALENCY_MAP else 0)
        
        default_countries = ["United Kingdom"]
        if has_profile:
            raw_c = profile[0].get('selected_countries', "[]")
            try:
                default_countries = json.loads(raw_c) if isinstance(raw_c, str) else raw_c
            except: pass

        active_c = st.multiselect("Active Systems", options=list(COUNTRY_KEY_MAP.keys()), default=default_countries)
        if st.button("💾 Save Profile"):
            client.table("profiles").upsert({"user_email": st.session_state.user_email, "global_tier": selected_tier, "selected_countries": json.dumps(active_c)}, on_conflict="user_email").execute()
            st.toast("Profile Synced.")

    # 🪪 REGISTRATION
    with tabs[1]:
        st.subheader("Medical Licensing")
        for reg in st.session_state.parsed_data.get("registrations", []):
            st.code(reg)
        with st.form("reg"):
            c1, c2 = st.columns(2)
            b, n = c1.text_input("Body"), c2.text_input("Number")
            if st.form_submit_button("Add"): st.success("Added.")

    # 🏥 EXPERIENCE (Fixed Line 281 error)
    with tabs[2]:
        st.subheader("Clinical Experience")
        
        if st.session_state.parsed_data.get("rotations"):
            for i, block in enumerate(st.session_state.parsed_data["rotations"]):
                with st.expander(f"Review Entry {i+1}", expanded=True):
                    # Defensive split
                    display_text = block if block else ""
                    header_guess = display_text.split('\n')[0] if '\n' in display_text else display_text
                    
                    full_text = st.text_area("Experience Details", display_text, height=180, key=f"rt_{i}")
                    c1, c2 = st.columns(2)
                    spec = c1.text_input("Specialty", key=f"rs_{i}")
                    grad = c2.text_input("Grade", key=f"rg_{i}")
                    
                    if st.button(f"Save Post {i+1}", key=f"rb_{i}"):
                        client.table("rotations").insert({
                            "user_email": st.session_state.user_email,
                            "hospital": header_guess[:100], "specialty": spec, "grade": grad, "description": full_text
                        }).execute()
                        st.toast("Saved!")

        if rotations: st.table(pd.DataFrame(rotations).drop(columns=['id', 'user_email'], errors='ignore'))

    # 💉 PROCEDURES
    with tabs[3]:
        st.subheader("Procedural Log")
        
        for i, block in enumerate(st.session_state.parsed_data.get("procedures", [])):
            with st.expander(f"Skill {i+1}"):
                p_name = st.text_input("Procedure", block[:100], key=f"pn_{i}")
                if st.button("Log", key=f"pb_{i}"):
                    client.table("procedures").insert({"user_email": st.session_state.user_email, "procedure": p_name, "level": "Independent"}).execute()
        if procedures: st.table(pd.DataFrame(procedures).drop(columns=['id', 'user_email'], errors='ignore'))

    # 🔬 ACADEMIC
    with tabs[4]:
        st.subheader("Academic Record")
        for i, block in enumerate(st.session_state.parsed_data.get("projects", [])):
            with st.expander(f"Project {i+1}"):
                t = st.text_input("Title", block[:100], key=f"an_{i}")
                if st.button("Log Project", key=f"ab_{i}"):
                    client.table("projects").insert({"user_email": st.session_state.user_email, "title": t}).execute()
        if projects: st.table(pd.DataFrame(projects).drop(columns=['id', 'user_email'], errors='ignore'))

    # 🛡️ VAULT
    with tabs[5]:
        st.subheader("Credential Vault")
        st.info("Upload scans of your certificates here.")

# --- LOGIN GATE ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Passport Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
