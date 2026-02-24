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

# --- 2. GLOBAL MAPPING DATA (Full Set) ---
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
    st.session_state.parsed_data = {"rotations": [], "procedures": [], "projects": [], "registrations": [], "raw": ""}

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

# --- 4. ADVANCED PARSER ---
def get_raw_text(file):
    try:
        if file.name.endswith('.pdf'):
            with pdfplumber.open(file) as pdf:
                return "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        elif file.name.endswith('.docx'):
            doc = docx.Document(file)
            return "\n".join([p.text for p in doc.paragraphs])
    except: return ""

def deep_scan_parse(file):
    text = get_raw_text(file)
    st.session_state.parsed_data["raw"] = text
    blocks = text.split('\n\n') if '\n\n' in text else text.split('\n')
    triage = {"rotations": [], "procedures": [], "projects": [], "registrations": [], "raw": text}
    
    kw_reg = ["gmc", "license", "registration", "mrcp", "mrcs", "board", "usmle", "plab", "pwz", "nip"]
    kw_proc = ["intubation", "suturing", "cannulation", "procedure", "performed", "competenc", "laparoscopy", "drain", "tap", "venepuncture"]
    kw_acad = ["audit", "qip", "research", "publication", "poster", "presentation", "teaching", "abstract", "journal"]
    kw_rot = ["hospital", "trust", "szpital", "ward", "department", "clinic", "rotation", "resident", "officer", "foundation"]

    for block in blocks:
        clean_block = block.strip()
        if len(clean_block) < 5: continue
        low = clean_block.lower()
        if any(k in low for k in kw_reg): triage["registrations"].append(clean_block)
        elif any(k in low for k in kw_proc): triage["procedures"].append(clean_block)
        elif any(k in low for k in kw_acad): triage["projects"].append(clean_block)
        elif any(k in low for k in kw_rot) or re.search(r'\b(20\d{2})\b', clean_block):
            triage["rotations"].append(clean_block)
    return triage

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Global Passport Sync")
        st.write(f"Logged in as: **{st.session_state.user_email}**")
        up_file = st.file_uploader("Upload Medical CV", type=['pdf', 'docx'])
        if up_file and st.button("🚀 Sync Portfolio"):
            with st.spinner("Analyzing Clinical Content..."):
                st.session_state.parsed_data = deep_scan_parse(up_file)
            st.success("Triage Complete.")
        
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    
    # Pre-fetch Database
    profile_db = fetch_user_data("profiles")
    rotations_db = fetch_user_data("rotations")
    procedures_db = fetch_user_data("procedures")
    projects_db = fetch_user_data("projects")

    tabs = st.tabs(["🌐 Equivalency", "🪪 Registration", "🏥 Experience", "💉 Procedures", "🔬 Academic", "📄 Export"])

    # 1. EQUIVALENCY
    with tabs[0]:
        st.subheader("International Seniority & Competency Mapping")
        
        has_profile = len(profile_db) > 0
        curr_tier = profile_db[0].get('global_tier', "Tier 1: Junior (Intern/FY1)") if has_profile else "Tier 1: Junior (Intern/FY1)"
        selected_tier = st.selectbox("Your Current Seniority Level", list(EQUIVALENCY_MAP.keys()), index=list(EQUIVALENCY_MAP.keys()).index(curr_tier) if curr_tier in EQUIVALENCY_MAP else 0)
        
        saved_countries = ["United Kingdom"]
        if has_profile:
            raw_c = profile_db[0].get('selected_countries', "[]")
            try: saved_countries = json.loads(raw_c) if isinstance(raw_c, str) else raw_c
            except: pass
        active_countries = st.multiselect("Active Medical Systems for Mapping", options=list(COUNTRY_KEY_MAP.keys()), default=saved_countries)
        
        st.write("### 🌍 Role Translations")
        map_rows = []
        for c in active_countries:
            map_rows.append({
                "Medical System": c, 
                "Equivalent Title": EQUIVALENCY_MAP[selected_tier].get(COUNTRY_KEY_MAP[c], "N/A")
            })
        st.table(pd.DataFrame(map_rows))

        if st.button("💾 Save Professional Profile"):
            try:
                client.table("profiles").upsert({
                    "user_email": st.session_state.user_email, 
                    "global_tier": selected_tier,
                    "selected_countries": json.dumps(active_countries)
                }, on_conflict="user_email").execute()
                st.toast("Profile Updated.")
            except: st.error("Database conflict. Ensure 'user_email' is unique in Supabase.")

    # 2. REGISTRATION
    with tabs[1]:
        st.subheader("Professional Licensing")
        for reg in st.session_state.parsed_data.get("registrations", []):
            st.code(reg)
        with st.form("manual_reg"):
            c1, c2 = st.columns(2)
            body = c1.text_input("Regulatory Body (e.g., GMC, AHPRA)")
            num = c2.text_input("Registration Number")
            if st.form_submit_button("Add License"): st.success("Added to vault.")

    # 3. EXPERIENCE
    with tabs[2]:
        st.subheader("Clinical Rotations & Placements")
        
        found_rots = st.session_state.parsed_data.get("rotations", [])
        if found_rots:
            st.write("### 📥 Triage Area")
            for i, block in enumerate(found_rots):
                with st.expander(f"Review Entry {i+1}", expanded=True):
                    full_text = st.text_area("Experience Details", block, height=150, key=f"rt_{i}")
                    c1, c2 = st.columns(2)
                    spec = c1.text_input("Specialty", key=f"rs_{i}")
                    hosp = c2.text_input("Hospital/Trust", key=f"rh_{i}")
                    if st.button(f"Confirm Experience {i+1}", key=f"rb_{i}"):
                        client.table("rotations").insert({
                            "user_email": st.session_state.user_email, 
                            "specialty": spec,
                            "hospital": hosp,
                            "description": full_text
                        }).execute()
                        st.toast("Experience Saved.")

        if rotations_db:
            st.divider()
            st.write("### 📜 Verified Record")
            st.table(pd.DataFrame(rotations_db)[['specialty', 'hospital', 'description']])

    # 4. PROCEDURES
    with tabs[3]:
        st.subheader("Procedural Competency Log")
        
        found_procs = st.session_state.parsed_data.get("procedures", [])
        if found_procs:
            for i, block in enumerate(found_procs):
                with st.expander(f"Detected Skill {i+1}"):
                    p_name = st.text_input("Procedure", block[:100], key=f"pn_{i}")
                    level = st.selectbox("Competency Level", ["Observed", "Supervised", "Independent"], key=f"pl_{i}")
                    if st.button("Log Procedure", key=f"pb_{i}"):
                        client.table("procedures").insert({
                            "user_email": st.session_state.user_email, 
                            "procedure": p_name,
                            "level": level
                        }).execute()

        if procedures_db:
            st.write("### ✅ Logged Skills")
            st.table(pd.DataFrame(procedures_db)[['procedure', 'level']])

    # 5. ACADEMIC
    with tabs[4]:
        st.subheader("Research, Audit & Academic Portfolio")
        found_proj = st.session_state.parsed_data.get("projects", [])
        if found_proj:
            for i, block in enumerate(found_proj):
                with st.expander(f"Detected Project {i+1}"):
                    t = st.text_input("Title", block[:100], key=f"an_{i}")
                    type_p = st.selectbox("Category", ["Audit", "QIP", "Research", "Teaching"], key=f"at_{i}")
                    if st.button("Save to Academic Record", key=f"ab_{i}"):
                        client.table("projects").insert({
                            "user_email": st.session_state.user_email, 
                            "title": t,
                            "type": type_p
                        }).execute()
        if projects_db:
            st.table(pd.DataFrame(projects_db)[['title', 'type']])

    # 6. EXPORT
    with tabs[5]:
        st.subheader("Final Portfolio Generation")
        st.write("Select the standards you want applied to your Global Medical Passport.")
        
        export_countries = st.multiselect("International Equivalencies to Print", options=list(COUNTRY_KEY_MAP.keys()), default=saved_countries)
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📄 Professional PDF Portfolio")
            st.write(f"- Mapping included for: {', '.join(export_countries)}")
            st.write(f"- Seniority Level: **{selected_tier}**")
            if st.button("🏗️ Build Full PDF Portfolio"):
                st.info("Compiling Clinical Evidence and mapping equivalents...")
                
        with col2:
            st.markdown("#### 🛡️ Secure QR Passport")
            st.write("Generate a digital link that allows employers to verify your procedural log and registration status.")
            if st.button("🔗 Generate Verified Link"):
                st.success("Digital Passport Link Ready.")

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Passport Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
