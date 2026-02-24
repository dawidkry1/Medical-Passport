import streamlit as st
import pandas as pd
from supabase import create_client
from fpdf import FPDF
import pdfplumber
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

def handle_login():
    try:
        res = client.auth.sign_in_with_password({"email": st.session_state.login_email, "password": st.session_state.login_password})
        if res.user:
            st.session_state.authenticated = True
            st.session_state.user_email = res.user.email
            client.auth.set_session(res.session.access_token, res.session.refresh_token)
    except Exception as e:
        st.error(f"Login failed: {e}")

def login_screen():
    st.title("🏥 Medical Passport Gateway")
    with st.form("login_form"):
        st.text_input("Institutional/Personal Email", key="login_email")
        st.text_input("Security Password", type="password", key="login_password")
        st.form_submit_button("Sign In to Secured Vault", on_click=handle_login, use_container_width=True)

def fetch_user_data(table_name):
    if not st.session_state.user_email: return []
    try:
        res = client.table(table_name).select("*").eq("user_email", st.session_state.user_email).execute()
        return res.data
    except Exception:
        return []

# --- 4. SMART PARSER ENGINE ---
def smart_parse_cv(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = "".join([p.extract_text() for p in pdf.pages])
    
    lines = text.split('\n')
    extracted = {"rotations": [], "procedures": [], "projects": []}
    
    # Keywords for categorization
    rotation_keys = ["hospital", "szpital", "clinic", "trust", "foundation year", "resident", "intern"]
    procedure_keys = ["intubation", "cannulation", "suturing", "centesis", "tap", "biopsy", "scopy"]
    academic_keys = ["audit", "qip", "research", "publication", "poster", "presentation"]
    ignore_keys = ["gmc", "registration", "license", "licence", "address", "phone", "email"]

    for line in lines:
        clean_line = line.strip()
        if len(clean_line) < 5 or any(k in clean_line.lower() for k in ignore_keys):
            continue
        
        # Categorize based on keywords
        if any(k in clean_line.lower() for k in rotation_keys):
            extracted["rotations"].append(clean_line)
        elif any(k in clean_line.lower() for k in procedure_keys):
            extracted["procedures"].append(clean_line)
        elif any(k in clean_line.lower() for k in academic_keys):
            extracted["projects"].append(clean_line)
            
    return extracted

# --- 5. PDF EXPORT ENGINE ---
class MedicalCV(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Global Professional Medical Portfolio', 0, 1, 'C')
        self.ln(5)

def generate_pdf(email, profile, rotations, procedures, projects, countries):
    pdf = MedicalCV()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"Clinician: {email}", 0, 1)
    
    tier = profile[0]['global_tier'] if profile else None
    if tier in EQUIVALENCY_MAP:
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(0, 10, " International Standing Equivalency", 0, 1, 'L', fill=True)
        pdf.set_font('Arial', 'B', 9)
        for c in countries:
            key = COUNTRY_KEY_MAP.get(c)
            if key: pdf.cell(0, 6, f"{c}: {EQUIVALENCY_MAP[tier][key]}", 0, 1)
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, " Clinical Experience", 0, 1, fill=True)
    pdf.set_font('Arial', '', 10)
    for r in rotations:
        pdf.cell(0, 6, f"{r['hospital']} ({r['specialty']}) - {r['grade']}", 0, 1)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 6. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.success(f"Verified Session: {st.session_state.user_email}")
        if st.button("🚪 Logout", use_container_width=True):
            client.auth.sign_out()
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")

    profile = fetch_user_data("profiles")
    rotations = fetch_user_data("rotations")
    procedures = fetch_user_data("procedures")
    projects = fetch_user_data("projects")

    tabs = st.tabs(["🌐 Equivalency", "🏥 Rotations", "💉 Procedures", "🔬 Academic", "🛡️ Vault", "📄 Export"])

    with tabs[0]:
        st.subheader("Global Standing Mapping")
        curr_tier = profile[0]['global_tier'] if profile else "Tier 1: Junior (Intern/FY1)"
        try: t_idx = list(EQUIVALENCY_MAP.keys()).index(curr_tier)
        except: t_idx = 0
        
        selected_tier = st.selectbox("Define Your Global Seniority", list(EQUIVALENCY_MAP.keys()), index=t_idx)
        
        raw_c = profile[0].get('selected_countries', []) if profile else ["United Kingdom", "Poland"]
        if isinstance(raw_c, str):
            try: saved_c = json.loads(raw_c)
            except: saved_c = ["United Kingdom", "Poland"]
        else: saved_c = raw_c if raw_c else ["United Kingdom", "Poland"]
            
        active_countries = st.multiselect("Relevant Healthcare Systems", options=list(COUNTRY_KEY_MAP.keys()), default=saved_c)

        if st.button("💾 Save Preferences"):
            save_payload = {"user_email": st.session_state.user_email, "global_tier": selected_tier, "selected_countries": json.dumps(active_countries)}
            try:
                client.table("profiles").upsert(save_payload, on_conflict="user_email").execute()
                st.success("Preferences Secured.")
            except:
                client.table("profiles").upsert({"user_email": st.session_state.user_email, "global_tier": selected_tier}, on_conflict="user_email").execute()
                st.success("Seniority Saved.")

    with tabs[1]:
        st.subheader("Clinical Experience")
        
        with st.expander("🪄 Smart-Scan: Sort Entire CV"):
            cv_file = st.file_uploader("Upload Medical CV (PDF)", type=['pdf'], key="smart_cv")
            if cv_file:
                data = smart_parse_cv(cv_file)
                
                # Show detected rotations
                if data["rotations"]:
                    st.write("**Detected Rotations:**")
                    for i, item in enumerate(data["rotations"]):
                        c1, c2, c3 = st.columns([2, 1, 1])
                        h = c1.text_input("Hospital", item, key=f"rot_h_{i}")
                        s = c2.text_input("Spec", "Select...", key=f"rot_s_{i}")
                        if c3.button("Confirm", key=f"rot_b_{i}"):
                            client.table("rotations").insert({"user_email": st.session_state.user_email, "hospital": h, "specialty": s, "grade": "Imported"}).execute()
                            st.toast("Saved to Rotations")

        if rotations: st.table(pd.DataFrame(rotations).drop(columns=['id', 'user_email'], errors='ignore'))

    with tabs[2]:
        st.subheader("Procedural Log")
        
        if 'data' in locals() and data["procedures"]:
            st.write("**Detected Procedures:**")
            for i, item in enumerate(data["procedures"]):
                c1, c2, c3 = st.columns([2, 1, 1])
                p_name = c1.text_input("Procedure", item, key=f"proc_n_{i}")
                p_lvl = c2.selectbox("Level", ["Observed", "Supervised", "Independent"], key=f"proc_l_{i}")
                if c3.button("Log", key=f"proc_b_{i}"):
                    client.table("procedures").insert({"user_email": st.session_state.user_email, "procedure": p_name, "level": p_lvl, "count": 1}).execute()
                    st.toast("Logged Procedure")
        
        if procedures: st.table(pd.DataFrame(procedures).drop(columns=['id', 'user_email'], errors='ignore'))

    with tabs[3]:
        st.subheader("Academic & QIP")
        if 'data' in locals() and data["projects"]:
            st.write("**Detected Academic Projects:**")
            for i, item in enumerate(data["projects"]):
                c1, c2, c3 = st.columns([2, 1, 1])
                pr_title = c1.text_input("Project", item, key=f"proj_t_{i}")
                pr_type = c2.selectbox("Type", ["Audit", "QIP", "Research"], key=f"proj_y_{i}")
                if c3.button("Add", key=f"proj_b_{i}"):
                    client.table("projects").insert({"user_email": st.session_state.user_email, "type": pr_type, "title": pr_title}).execute()
                    st.toast("Added Project")
                    
        if projects: st.table(pd.DataFrame(projects).drop(columns=['id', 'user_email'], errors='ignore'))

    with tabs[4]:
        st.subheader("🛡️ Verified Vault")
        up = st.file_uploader("Secure Upload", type=['pdf', 'jpg', 'png'])
        if up and st.button("Upload to Secure Cloud"):
            client.storage.from_('medical-vault').upload(f"{st.session_state.user_email}/{up.name}", up.getvalue())
            st.success("Document Verified.")
        
        try:
            files = client.storage.from_('medical-vault').list(st.session_state.user_email)
            for f in files:
                c1, c2 = st.columns([0.8, 0.2])
                c1.write(f"📄 {f['name']}")
                res = client.storage.from_('medical-vault').create_signed_url(f"{st.session_state.user_email}/{f['name']}", 60)
                c2.link_button("View", res['signedURL'])
        except: st.info("Vault empty.")

    with tabs[5]:
        st.subheader("Export Portfolio")
        if st.button("🏗️ Compile Secured PDF"):
            pdf_bytes = generate_pdf(st.session_state.user_email, profile, rotations, procedures, projects, active_countries)
            st.download_button("⬇️ Download PDF", pdf_bytes, "Medical_Portfolio.pdf", "application/pdf")

if st.session_state.authenticated: main_dashboard()
else: login_screen()
