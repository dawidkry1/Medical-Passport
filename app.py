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
        "Poland": "Lekarz stażysta",
        "Responsibilities": "Ward based, supervised prescribing, basic clinical procedures."
    },
    "Tier 2: Intermediate (SHO/Resident)": {
        "UK": "FY2 / Core Trainee", "US": "PGY-2/3 (Resident)", "Australia": "Resident / RMO",
        "Ireland": "SHO", "Canada": "Junior Resident", "Dubai/DHA": "GP / Resident",
        "India/Pakistan": "PG Resident / Medical Officer", "Nigeria": "Registrar",
        "China/S.Korea": "Resident", "Europe": "Resident Physician",
        "Poland": "Lekarz rezydent (Junior)",
        "Responsibilities": "Acute assessments, procedural proficiency, core specialty rotations."
    },
    "Tier 3: Senior (Registrar/Fellow)": {
        "UK": "ST3+ / Registrar", "US": "Chief Resident / Fellow", "Australia": "Registrar",
        "Ireland": "Specialist Registrar (SpR)", "Canada": "Senior Resident / Fellow", "Dubai/DHA": "Specialist (P)",
        "India/Pakistan": "Senior Resident / Registrar", "Nigeria": "Senior Registrar",
        "China/S.Korea": "Attending Physician / Fellow", "Europe": "Specialist Trainee / Senior Registrar",
        "Poland": "Lekarz rezydent (Senior)",
        "Responsibilities": "Team leadership, specialty decision making, independent in core procedures."
    },
    "Tier 4: Expert (Consultant/Attending)": {
        "UK": "Consultant / SAS", "US": "Attending Physician", "Australia": "Consultant / Specialist",
        "Ireland": "Consultant", "Canada": "Staff Specialist", "Dubai/DHA": "Consultant",
        "India/Pakistan": "Consultant / Asst. Professor", "Nigeria": "Consultant",
        "China/S.Korea": "Chief Physician", "Europe": "Specialist / Consultant",
        "Poland": "Lekarz specjalista",
        "Responsibilities": "Final clinical accountability, service leadership, senior training."
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
            client.auth.set_session(res.session.access_token, res.session.refresh_token)
    except Exception as e:
        st.error(f"Login failed: {e}")

def fetch_user_data(table_name):
    if not st.session_state.user_email: return []
    try:
        res = client.table(table_name).select("*").eq("user_email", st.session_state.user_email).execute()
        return res.data
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
    except Exception as e:
        st.error(f"File reading error: {e}")
    return ""

def deep_clinical_parse(file):
    text = get_clean_text(file)
    lines = text.split('\n')
    
    triage = {"rotations": [], "procedures": [], "projects": [], "registrations": [], "fragments": []}
    current_block = []
    
    # Improved Date Header logic: Look for dates at the START of the line
    date_header_pattern = r'^(\d{4}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Present|Current)'

    for line in lines:
        clean_line = line.strip()
        if not clean_line: continue
        
        # Determine if this line is a structural "break" (a new job or section)
        is_new_header = re.match(date_header_pattern, clean_line, re.IGNORECASE) or \
                        any(k in clean_line.upper() for k in ["EXPERIENCE", "EMPLOYMENT", "EDUCATION", "QUALIFICATIONS"])
        
        if is_new_header and current_block:
            # Process finished block
            full_content = "\n".join(current_block)
            low = full_content.lower()
            
            if any(k in low for k in ["gmc", "license", "registration"]):
                triage["registrations"].append(full_content)
            elif any(k in low for k in ["audit", "qip", "research", "publication"]):
                triage["projects"].append(full_content)
            elif any(k in low for k in ["procedure", "intubation", "suturing", "cannulation"]):
                triage["procedures"].append(full_content)
            elif any(k in low for k in ["hospital", "trust", "szpital", "ward", "clinic"]):
                triage["rotations"].append(full_content)
            else:
                triage["fragments"].append(full_content)
            
            current_block = [clean_line]
        else:
            current_block.append(clean_line)

    if current_block:
        triage["rotations"].append("\n".join(current_block))
        
    return triage

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Global Sync")
        st.success(f"Verified: {st.session_state.user_email}")
        
        st.divider()
        st.write("### 📂 Portfolio Importer")
        up_file = st.file_uploader("Upload Medical CV", type=['pdf', 'docx'])
        
        if up_file and st.button("🚀 Analyze & Triage"):
            with st.spinner("Intelligently Grouping Experiences..."):
                st.session_state.parsed_data = deep_clinical_parse(up_file)
                st.success("Triage Complete.")

        if st.button("🚪 Logout", use_container_width=True):
            client.auth.sign_out()
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    profile = fetch_user_data("profiles")
    rotations = fetch_user_data("rotations")
    procedures = fetch_user_data("procedures")
    projects = fetch_user_data("projects")

    tabs = st.tabs(["🌐 Equivalency", "🪪 Registration", "🏥 Experience", "💉 Procedures", "🔬 Academic", "🛡️ Vault", "📄 Export"])

    # 🌐 EQUIVALENCY
    with tabs[0]:
        st.subheader("International Equivalency")
        curr_tier = profile[0]['global_tier'] if profile else "Tier 1: Junior (Intern/FY1)"
        selected_tier = st.selectbox("Current Seniority", list(EQUIVALENCY_MAP.keys()), index=list(EQUIVALENCY_MAP.keys()).index(curr_tier) if curr_tier in EQUIVALENCY_MAP else 0)
        raw_c = profile[0].get('selected_countries', []) if profile else ["United Kingdom"]
        active_c = st.multiselect("Active Systems", options=list(COUNTRY_KEY_MAP.keys()), default=raw_c if isinstance(raw_c, list) else json.loads(raw_c))
        if st.button("💾 Save Preferences"):
            client.table("profiles").upsert({"user_email": st.session_state.user_email, "global_tier": selected_tier, "selected_countries": json.dumps(active_c)}, on_conflict="user_email").execute()
            st.toast("Profile Synced.")

    # 🪪 REGISTRATION
    with tabs[1]:
        st.subheader("Medical Licensing")
        if st.session_state.parsed_data["registrations"]:
            for reg in st.session_state.parsed_data["registrations"]:
                st.code(reg)
        with st.form("reg_form"):
            b, n = st.text_input("Regulatory Body"), st.text_input("Number")
            if st.form_submit_button("Confirm Registration"): 
                st.success("Added.")

    # 🏥 EXPERIENCE
    with tabs[2]:
        st.subheader("Clinical Experience Record")
        if st.session_state.parsed_data["rotations"]:
            st.markdown("### 📥 Triage Area")
            for i, block in enumerate(st.session_state.parsed_data["rotations"]):
                with st.expander(f"Review Entry {i+1}", expanded=True):
                    full_text = st.text_area("Experience Block", block, height=200, key=f"rot_tx_{i}")
                    c1, c2 = st.columns(2)
                    spec = c1.text_input("Specialty", key=f"rot_s_{i}")
                    grad = c2.text_input("Grade", key=f"rot_g_{i}")
                    
                    if st.button(f"Save Post {i+1}", key=f"rot_btn_{i}"):
                        try:
                            client.table("rotations").insert({
                                "user_email": st.session_state.user_email,
                                "hospital": full_text.split('\n')[0][:100], 
                                "specialty": spec, 
                                "grade": grad, 
                                "description": full_text
                            }).execute()
                            st.toast("Saved!")
                        except Exception as e:
                            st.error(f"Error saving: {e}. Check if 'description' column exists in Supabase.")

        if st.session_state.parsed_data["fragments"]:
            with st.expander("🧩 Uncategorized Fragments"):
                for frag in st.session_state.parsed_data["fragments"]:
                    st.code(frag)

        if rotations:
            df = pd.DataFrame(rotations).drop(columns=['id', 'user_email'], errors='ignore')
            st.table(df)

    # 💉 PROCEDURES
    with tabs[3]:
        st.subheader("Procedural Log")
        
        if st.session_state.parsed_data["procedures"]:
            for i, block in enumerate(st.session_state.parsed_data["procedures"]):
                with st.expander(f"Skill {i+1}"):
                    p_name = st.text_input("Procedure", block[:100], key=f"pr_n_{i}")
                    if st.button("Log Skill", key=f"pr_btn_{i}"):
                        client.table("procedures").insert({"user_email": st.session_state.user_email, "procedure": p_name, "level": "Independent"}).execute()
        
        with st.form("man_pr"):
            pn, pl = st.text_input("Procedure"), st.selectbox("Level", ["Observed", "Supervised", "Independent"])
            if st.form_submit_button("Add Manual Skill"): 
                client.table("procedures").insert({"user_email": st.session_state.user_email, "procedure": pn, "level": pl}).execute()
                st.rerun()

    # 🔬 ACADEMIC
    with tabs[4]:
        st.subheader("Academic Record")
        if st.session_state.parsed_data["projects"]:
            for i, block in enumerate(st.session_state.parsed_data["projects"]):
                with st.expander(f"Project {i+1}"):
                    title = st.text_input("Title", block[:100], key=f"ac_n_{i}")
                    if st.button("Add Project", key=f"ac_btn_{i}"):
                        client.table("projects").insert({"user_email": st.session_state.user_email, "title": title}).execute()
        if projects: st.table(pd.DataFrame(projects).drop(columns=['id', 'user_email'], errors='ignore'))

    # 🛡️ VAULT & EXPORT
    with tabs[5]: st.info("Vault ready for document uploads.")
    with tabs[6]: st.button("🏗️ Build Portfolio PDF")

# --- AUTH ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Passport Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
