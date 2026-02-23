import streamlit as st
import time
import pandas as pd
from supabase import create_client, Client
from fpdf import FPDF
import io
import json

# --- 1. CORE CONFIGURATION ---
st.set_page_config(page_title="Global Medical Passport", page_icon="🏥", layout="wide")

# --- CUSTOM CSS TO HIDE STREAMLIT UI ELEMENTS ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stAppDeployButton {display:none;}
            [data-testid="stToolbar"] {visibility: hidden !important;}
            [data-testid="stDecoration"] {display:none;}
            .stButton>button {border-radius: 5px;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# Secure connection to Supabase
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
client = create_client(URL, KEY)

# GLOBAL MAPPING DATA (UK, US, Australia, Ireland, Canada, Dubai, India/Pakistan, Nigeria, China/S.Korea, Europe, Poland)
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

# --- 2. PROFESSIONAL PDF GENERATOR ---
class MedicalCV(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Professional Medical Portfolio', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 8, 'Verified Clinical Credential Document', 0, 1, 'C')
        self.ln(10)

    def section_header(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, f" {title}", 0, 1, 'L', fill=True)
        self.ln(3)

def generate_pdf(email, profile, rotations, procedures, projects, selected_countries):
    pdf = MedicalCV()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f"Physician: {email}", 0, 1)
    
    tier_key = profile[0]['global_tier'] if profile else None
    if tier_key in EQUIVALENCY_MAP:
        data = EQUIVALENCY_MAP[tier_key]
        pdf.section_header("Professional Standing & International Equivalency")
        pdf.set_font('Arial', 'B', 10)
        for country in selected_countries:
            key = COUNTRY_KEY_MAP.get(country)
            if key: pdf.cell(0, 7, f"{country} Equivalent: {data[key]}", 0, 1)
        pdf.ln(2)
        pdf.set_font('Arial', 'I', 10)
        pdf.multi_cell(0, 6, f"Scope of Practice: {data['Responsibilities']}")
    
    pdf.ln(5)
    pdf.section_header("Clinical Experience & Rotations")
    for r in rotations:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, f"{r['hospital']} - {r['specialty']}", 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f"Role: {r['grade']} | Dates: {r['dates']}", 0, 1)
        pdf.ln(2)

    pdf.ln(5)
    pdf.section_header("Procedural Logbook Summary")
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(80, 8, "Procedure", 1); pdf.cell(60, 8, "Level", 1); pdf.cell(30, 8, "Count", 1, 1)
    pdf.set_font('Arial', '', 9)
    for p in procedures:
        pdf.cell(80, 8, str(p['procedure']), 1); pdf.cell(60, 8, str(p['level']), 1); pdf.cell(30, 8, str(p['count']), 1, 1)

    pdf.ln(10)
    pdf.section_header("Academic Portfolio & QIP")
    for pr in projects:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, f"{pr['type']}: {pr['title']}", 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f"Role: {pr['role']} ({pr['year']})", 0, 1)
        pdf.ln(2)

    return pdf.output(dest='S').encode('latin-1')

# --- 3. DATABASE UTILITIES ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

def fetch_user_data(table_name):
    try:
        res = client.table(table_name).select("*").eq("user_email", st.session_state.user_email).execute()
        return res.data
    except: return []

# --- 4. THE PASSPORT DASHBOARD ---
def main_dashboard():
    head_col1, head_col2 = st.columns([0.80, 0.20])
    with head_col1:
        st.title("🩺 Global Medical Passport")
        st.caption(f"Physician Session: {st.session_state.user_email}")
    with head_col2:
        st.write("##")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user_email = ""
            st.rerun()

    profile = fetch_user_data("profiles")
    rotations = fetch_user_data("rotations")
    procedures = fetch_user_data("procedures")
    projects = fetch_user_data("projects")

    # Load preferences
    saved_countries = []
    if profile and profile[0].get('selected_countries'):
        saved_countries = profile[0]['selected_countries']
        if isinstance(saved_countries, str):
            saved_countries = json.loads(saved_countries)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🌐 Equivalency", "🏥 Rotations", "💉 Procedures", "🔬 Academic", "🛡️ Vault", "📄 Export CV"
    ])

    with tab1:
        st.subheader("Professional Seniority Mapping")
        current_tier = profile[0]['global_tier'] if profile else list(EQUIVALENCY_MAP.keys())[0]
        try:
            t_idx = list(EQUIVALENCY_MAP.keys()).index(current_tier)
        except: t_idx = 0
        
        selected_tier = st.selectbox("Define Your Clinical Standing", list(EQUIVALENCY_MAP.keys()), index=t_idx)
        active_countries = st.multiselect(
            "Target Healthcare Systems",
            options=list(COUNTRY_KEY_MAP.keys()),
            default=saved_countries if saved_countries else ["United Kingdom", "Poland"]
        )

        if active_countries:
            t_data = EQUIVALENCY_MAP[selected_tier]
            cols = st.columns(3)
            for i, country in enumerate(active_countries):
                key = COUNTRY_KEY_MAP[country]
                cols[i % 3].metric(country, t_data[key])
        
        if st.button("💾 Save Settings"):
            client.table("profiles").upsert({
                "user_email": st.session_state.user_email, 
                "global_tier": selected_tier,
                "selected_countries": active_countries
            }, on_conflict="user_email").execute()
            st.success("Global Standing Saved."); st.rerun()

    with tab2:
        st.subheader("Clinical Placements")
        if rotations: st.table(pd.DataFrame(rotations).drop(columns=['id', 'user_email'], errors='ignore'))
        with st.form("add_rot", clear_on_submit=True):
            h, s, d, g = st.text_input("Hospital"), st.text_input("Specialty"), st.text_input("Dates"), st.text_input("Grade")
            if st.form_submit_button("Add Placement"):
                client.table("rotations").insert({"user_email": st.session_state.user_email, "hospital": h, "specialty": s, "dates": d, "grade": g}).execute()
                st.rerun()

    with tab3:
        st.subheader("Procedural Log")
        if procedures: st.table(pd.DataFrame(procedures).drop(columns=['id', 'user_email'], errors='ignore'))
        with st.form("add_proc", clear_on_submit=True):
            n, l, c = st.text_input("Procedure"), st.selectbox("Level", ["Observed", "Supervised", "Independent", "Assessor"]), st.number_input("Count", 1)
            if st.form_submit_button("Log Procedure"):
                client.table("procedures").insert({"user_email": st.session_state.user_email, "procedure": n, "level": l, "count": c}).execute()
                st.rerun()

    with tab4:
        st.subheader("Academic Portfolio")
        if projects: st.table(pd.DataFrame(projects).drop(columns=['id', 'user_email'], errors='ignore'))
        with st.form("add_proj", clear_on_submit=True):
            t = st.selectbox("Type", ["Audit", "Research", "QIP", "Teaching"])
            title, r, y = st.text_input("Title"), st.text_input("Role"), st.text_input("Year")
            if st.form_submit_button("Log Project"):
                client.table("projects").insert({"user_email": st.session_state.user_email, "type": t, "title": title, "role": r, "year": y}).execute()
                st.rerun()

    with tab5:
        st.subheader("🛡️ Credential Vault")
        st.info("Document upload is currently in development.")

    with tab6:
        st.subheader("Compile Portfolio")
        export_countries = st.multiselect("Include in PDF Header", options=list(COUNTRY_KEY_MAP.keys()), default=active_countries)
        if st.button("🏗️ Generate Professional PDF"):
            try:
                pdf_bytes = generate_pdf(st.session_state.user_email, profile, rotations, procedures, projects, export_countries)
                st.download_button(label="⬇️ Download CV", data=pdf_bytes, file_name="Clinical_Passport.pdf", mime="application/pdf")
            except Exception as e: st.error(f"Error: {e}")

# --- 5. AUTHENTICATION (NO-RACE CONDITION VERSION) ---
def login_screen():
    st.title("🏥 Medical Passport Gateway")
    # Using container for better visual grouping
    with st.container():
        e = st.text_input("Email", key="auth_email")
        p = st.text_input("Password", type="password", key="auth_pass")
        
        col1, col2 = st.columns(2)
        
        if col1.button("Login", use_container_width=True):
            if not e or not p:
                st.warning("Please enter both email and password.")
                return

            try:
                # 1. Attempt the handshake
                res = client.auth.sign_in_with_password({"email": e, "password": p})
                
                # 2. Check for user existence in response
                if res.user:
                    # 3. SET STATE BEFORE ANYTHING ELSE
                    st.session_state.authenticated = True
                    st.session_state.user_email = e
                    # 4. Show success and force a hard refresh
                    st.success("Authentication Successful! Syncing profile...")
                    time.sleep(0.4)
                    st.rerun()
                else:
                    st.error("Credential verification failed.")
            except Exception as ex:
                # Specifically catch the error so it doesn't stay on screen on next click
                st.error(f"Login attempt failed. Please try again.")

        if col2.button("Register", use_container_width=True):
            try:
                client.auth.sign_up({"email": e, "password": p})
                st.info("Verification email sent! Check your inbox.")
            except:
                st.error("Registration failed. Email might already be in use.")

# --- 6. EXECUTION FLOW ---
if st.session_state.authenticated:
    main_dashboard()
else:
    login_screen()
