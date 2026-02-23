import streamlit as st
import pandas as pd
from supabase import create_client
from fpdf import FPDF
import pdfplumber
import json
import io

# --- 1. CORE CONFIG & STYLING ---
st.set_page_config(page_title="Global Medical Passport", page_icon="🏥", layout="wide")

# This hides the Streamlit "Developer" UI for a professional clinical look
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

# Secure connection to Supabase
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
client = create_client(URL, KEY)

# --- 2. GLOBAL MAPPING DATA (UK, Poland, etc.) ---
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

# --- 3. SESSION & AUTHENTICATION ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def handle_login():
    email = st.session_state.login_email
    password = st.session_state.login_password
    try:
        res = client.auth.sign_in_with_password({"email": email, "password": password})
        if res.user:
            st.session_state.authenticated = True
            st.session_state.user_email = email
    except:
        st.error("Authentication failed. Please check your credentials.")

def login_screen():
    st.title("🏥 Medical Passport Gateway")
    with st.form("login_form"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login, use_container_width=True)

# --- 4. DATA UTILITIES ---
def fetch_user_data(table_name):
    try:
        res = client.table(table_name).select("*").eq("user_email", st.session_state.user_email).execute()
        return res.data
    except: return []

class MedicalCV(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Professional Medical Portfolio', 0, 1, 'C')
        self.ln(5)
    def section_header(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, f" {title}", 0, 1, 'L', fill=True)
        self.ln(3)

def generate_pdf(email, profile, rotations, procedures, projects, countries):
    pdf = MedicalCV()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f"Physician: {email}", 0, 1)
    
    tier_key = profile[0]['global_tier'] if profile else None
    if tier_key in EQUIVALENCY_MAP:
        data = EQUIVALENCY_MAP[tier_key]
        pdf.section_header("International Standing Equivalency")
        pdf.set_font('Arial', 'B', 10)
        for c in countries:
            key = COUNTRY_KEY_MAP.get(c)
            if key: pdf.cell(0, 7, f"{c}: {data[key]}", 0, 1)
        pdf.ln(5)

    pdf.section_header("Clinical Experience")
    for r in rotations:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, f"{r['hospital']} - {r['specialty']}", 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f"{r['grade']} | {r['dates']}", 0, 1)
        pdf.ln(2)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
    # Header with Logout functionality
    col1, col2 = st.columns([0.8, 0.2])
    col1.title("🩺 Global Medical Passport")
    if col2.button("Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

    profile = fetch_user_data("profiles")
    rotations = fetch_user_data("rotations")
    procedures = fetch_user_data("procedures")
    projects = fetch_user_data("projects")

    tabs = st.tabs(["🌐 Equivalency", "🏥 Rotations", "💉 Procedures", "🔬 Academic", "🛡️ Vault", "📄 Export"])

    with tabs[0]:
        st.subheader("Global Standing Mapping")
        current_tier = profile[0]['global_tier'] if profile else list(EQUIVALENCY_MAP.keys())[0]
        try: t_idx = list(EQUIVALENCY_MAP.keys()).index(current_tier)
        except: t_idx = 0
        
        tier = st.selectbox("Define Your Global Seniority", list(EQUIVALENCY_MAP.keys()), index=t_idx)
        
        # --- FIXED DATA HANDLING FOR API ERROR ---
        raw_saved = profile[0].get('selected_countries') if profile else ["United Kingdom", "Poland"]
        if isinstance(raw_saved, str):
            try: saved_c = json.loads(raw_saved)
            except: saved_c = ["United Kingdom", "Poland"]
        else:
            saved_c = raw_saved if raw_saved else ["United Kingdom", "Poland"]
            
        active_c = st.multiselect("Relevant Healthcare Systems", options=list(COUNTRY_KEY_MAP.keys()), default=saved_c)

        if st.button("💾 Save Preferences"):
            # Upserting directly as a list/array to match Supabase requirements
            client.table("profiles").upsert({
                "user_email": st.session_state.user_email, 
                "global_tier": tier, 
                "selected_countries": active_c 
            }, on_conflict="user_email").execute()
            st.success("Preferences Saved!")
            st.rerun()

    with tabs[1]:
        st.subheader("Clinical Experience")
        # --- HANDS-FREE PARSER ---
        with st.expander("🪄 Quick-Start: Auto-Fill from Legacy CV", expanded=False):
            st.info("Upload your PDF. I will scan for hospitals and departments to save you typing.")
            legacy_file = st.file_uploader("Upload PDF CV", type=['pdf'], key="auto_cv_upload")
            
            if legacy_file:
                with pdfplumber.open(legacy_file) as pdf:
                    full_text = "".join([p.extract_text() for p in pdf.pages])
                
                hospital_keywords = ["hospital", "szpital", "clinic", "klinika", "medical centre", "ward", "oddział", "instytut"]
                lines = full_text.split('\n')
                found_placements = [line.strip() for line in lines if any(k in line.lower() for k in hospital_keywords)]

                if found_placements:
                    st.write("### 🤖 Potential Rotations Identified:")
                    for i, place in enumerate(found_placements[:10]): 
                        c1, c2, c3 = st.columns([2, 1, 1])
                        h_name = c1.text_input("Hospital", value=place, key=f"auto_h_{i}")
                        h_spec = c2.text_input("Specialty", value="Verify...", key=f"auto_s_{i}")
                        if c3.button("✅ Add", key=f"btn_add_{i}"):
                            client.table("rotations").insert({"user_email": st.session_state.user_email, "hospital": h_name, "specialty": h_spec, "dates": "Imported", "grade": "Imported"}).execute()
                            st.toast(f"Added {h_name}")
                else:
                    st.warning("No hospital entries detected. Please use the manual form below.")

        st.divider()
        if rotations: 
            st.write("### Your Career History")
            st.table(pd.DataFrame(rotations).drop(columns=['id', 'user_email'], errors='ignore'))
        
        with st.form("add_rot", clear_on_submit=True):
            st.write("Add New Rotation Manually")
            h, s, d, g = st.text_input("Hospital"), st.text_input("Specialty"), st.text_input("Dates"), st.text_input("Grade")
            if st.form_submit_button("Add Rotation"):
                client.table("rotations").insert({"user_email": st.session_state.user_email, "hospital": h, "specialty": s, "dates": d, "grade": g}).execute()
                st.rerun()

    with tabs[2]:
        st.subheader("Procedural Log")
        if procedures: st.table(pd.DataFrame(procedures).drop(columns=['id', 'user_email'], errors='ignore'))
        with st.form("add_proc", clear_on_submit=True):
            n, l, c = st.text_input("Procedure"), st.selectbox("Level", ["Observed", "Supervised", "Independent", "Assessor"]), st.number_input("Count", 1)
            if st.form_submit_button("Log Skill"):
                client.table("procedures").insert({"user_email": st.session_state.user_email, "procedure": n, "level": l, "count": c}).execute()
                st.rerun()

    with tabs[3]:
        st.subheader("Academic, Research & QIP")
        if projects: st.table(pd.DataFrame(projects).drop(columns=['id', 'user_email'], errors='ignore'))
        with st.form("add_proj", clear_on_submit=True):
            t = st.selectbox("Type", ["Audit", "Research", "QIP", "Teaching"])
            title, r, y = st.text_input("Title"), st.text_input("Role"), st.text_input("Year")
            if st.form_submit_button("Add Project"):
                client.table("projects").insert({"user_email": st.session_state.user_email, "type": t, "title": title, "role": r, "year": y}).execute()
                st.rerun()

    with tabs[4]:
        st.subheader("🛡️ Verified Credential Vault")
        up = st.file_uploader("Upload Degree, License or GMC/Izba Letter", type=['pdf', 'jpg', 'png'])
        if up and st.button("📤 Vault File"):
            path = f"{st.session_state.user_email}/{up.name}"
            client.storage.from_('medical-vault').upload(path, up.getvalue())
            st.success("File securely vaulted.")
        
        files = client.storage.from_('medical-vault').list(st.session_state.user_email)
        if files:
            for f in files:
                c1, c2 = st.columns([0.8, 0.2])
                c1.write(f"📄 {f['name']}")
                res = client.storage.from_('medical-vault').create_signed_url(f"{st.session_state.user_email}/{f['name']}", 60)
                c2.link_button("View", res['signedURL'])

    with tabs[5]:
        st.subheader("Generate Global Clinical CV")
        exp_c = st.multiselect("Choose countries for equivalency header:", options=list(COUNTRY_KEY_MAP.keys()), default=active_c)
        if st.button("🏗️ Compile Professional PDF"):
            pdf_bytes = generate_pdf(st.session_state.user_email, profile, rotations, procedures, projects, exp_c)
            st.download_button("⬇️ Download CV", pdf_bytes, "Clinical_Passport.pdf", "application/pdf")

# --- EXECUTION ---
if st.session_state.authenticated:
    main_dashboard()
else:
    login_screen()
