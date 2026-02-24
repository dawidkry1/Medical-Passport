import streamlit as st
import pandas as pd
from supabase import create_client
from fpdf import FPDF
import pdfplumber
import json
import io

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

def handle_login():
    try:
        res = client.auth.sign_in_with_password({"email": st.session_state.login_email, "password": st.session_state.login_password})
        if res.user:
            st.session_state.authenticated = True
            st.session_state.user_email = st.session_state.login_email
    except: st.error("Login failed. Check your Supabase credentials.")

def login_screen():
    st.title("🏥 Medical Passport Gateway")
    with st.form("login_form"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login, use_container_width=True)

def fetch_user_data(table_name):
    try:
        res = client.table(table_name).select("*").eq("user_email", st.session_state.user_email).execute()
        return res.data
    except: return []

# --- 4. PDF ENGINE ---
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

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
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
        
        curr_tier = profile[0]['global_tier'] if profile else list(EQUIVALENCY_MAP.keys())[0]
        try: t_idx = list(EQUIVALENCY_MAP.keys()).index(curr_tier)
        except: t_idx = 0
        
        selected_tier = st.selectbox("Define Your Global Seniority", list(EQUIVALENCY_MAP.keys()), index=t_idx)
        
        # Load saved countries safely
        raw_c = profile[0].get('selected_countries', []) if profile else ["United Kingdom", "Poland"]
        if isinstance(raw_c, str):
            try: saved_c = json.loads(raw_c)
            except: saved_c = ["United Kingdom", "Poland"]
        else: saved_c = raw_c
            
        active_countries = st.multiselect("Relevant Healthcare Systems", options=list(COUNTRY_KEY_MAP.keys()), default=saved_c)

        if active_countries:
            st.write("### 🌍 Comparison of Your Role")
            t_data = EQUIVALENCY_MAP[selected_tier]
            m_cols = st.columns(len(active_countries) if len(active_countries) < 5 else 4)
            for i, country in enumerate(active_countries):
                key = COUNTRY_KEY_MAP[country]
                m_cols[i % 4].metric(country, t_data[key])
            st.info(f"**Responsibilities:** {t_data['Responsibilities']}")

        if st.button("💾 Save Preferences"):
            # CRITICAL FIX: Convert list to string to avoid Supabase Type Errors
            save_data = {
                "user_email": st.session_state.user_email, 
                "global_tier": selected_tier, 
                "selected_countries": json.dumps(active_countries) # Force JSON String
            }
            try:
                client.table("profiles").upsert(save_data, on_conflict="user_email").execute()
                st.success("Preferences Saved!")
                st.rerun()
            except Exception as e:
                st.error(f"Save failed. Error details: {e}")

    with tabs[1]:
        st.subheader("Clinical Experience")
        with st.expander("🪄 Hands-Free: Auto-Fill from Legacy CV"):
            legacy = st.file_uploader("Upload PDF CV", type=['pdf'], key="cv_auto")
            if legacy:
                with pdfplumber.open(legacy) as pdf:
                    txt = "".join([p.extract_text() for p in pdf.pages])
                keys = ["hospital", "szpital", "clinic", "klinika", "medical", "ward", "oddział"]
                found = [line.strip() for line in txt.split('\n') if any(k in line.lower() for k in keys)]
                for i, place in enumerate(found[:6]):
                    c1, c2, c3 = st.columns([2,1,1])
                    h = c1.text_input("Hospital", place, key=f"h_{i}")
                    s = c2.text_input("Specialty", "Verify...", key=f"s_{i}")
                    if c3.button("✅ Add", key=f"b_{i}"):
                        client.table("rotations").insert({"user_email": st.session_state.user_email, "hospital": h, "specialty": s, "dates": "Imported", "grade": "Imported"}).execute()
                        st.toast(f"Added {h}")

        if rotations: 
            df_rot = pd.DataFrame(rotations).drop(columns=['id', 'user_email'], errors='ignore')
            st.table(df_rot)
            
        with st.form("new_rot", clear_on_submit=True):
            h, s, d, g = st.text_input("Hospital"), st.text_input("Specialty"), st.text_input("Dates"), st.text_input("Grade")
            if st.form_submit_button("Manual Add"):
                client.table("rotations").insert({"user_email": st.session_state.user_email, "hospital": h, "specialty": s, "dates": d, "grade": g}).execute()
                st.rerun()

    # (Procedures, Academic, Vault, and Export remain as they were in your functional version)
    with tabs[2]:
        st.subheader("Procedural Log")
        if procedures: st.table(pd.DataFrame(procedures).drop(columns=['id', 'user_email'], errors='ignore'))
        with st.form("new_proc"):
            n, l, c = st.text_input("Procedure"), st.selectbox("Level", ["Observed", "Supervised", "Independent"]), st.number_input("Count", 1)
            if st.form_submit_button("Log Procedure"):
                client.table("procedures").insert({"user_email": st.session_state.user_email, "procedure": n, "level": l, "count": c}).execute()
                st.rerun()

    with tabs[3]:
        st.subheader("Academic / QIP")
        if projects: st.table(pd.DataFrame(projects).drop(columns=['id', 'user_email'], errors='ignore'))
        with st.form("new_proj"):
            t, title = st.selectbox("Type", ["Audit", "Research", "QIP"]), st.text_input("Title")
            if st.form_submit_button("Add Project"):
                client.table("projects").insert({"user_email": st.session_state.user_email, "type": t, "title": title}).execute()
                st.rerun()

    with tabs[4]:
        st.subheader("🛡️ Verified Vault")
        up = st.file_uploader("Vault File", type=['pdf', 'jpg', 'png'])
        if up and st.button("Upload"):
            client.storage.from_('medical-vault').upload(f"{st.session_state.user_email}/{up.name}", up.getvalue())
            st.success("Saved.")
        files = client.storage.from_('medical-vault').list(st.session_state.user_email)
        if files:
            for f in files:
                c1, c2 = st.columns([0.8, 0.2])
                c1.write(f"📄 {f['name']}")
                res = client.storage.from_('medical-vault').create_signed_url(f"{st.session_state.user_email}/{f['name']}", 60)
                c2.link_button("View", res['signedURL'])

    with tabs[5]:
        st.subheader("Export PDF")
        sel_countries = st.multiselect("Include in PDF Header:", list(COUNTRY_KEY_MAP.keys()), default=active_countries)
        if st.button("🏗️ Compile Portfolio"):
            pdf_bytes = generate_pdf(st.session_state.user_email, profile, rotations, procedures, projects, sel_countries)
            st.download_button("⬇️ Download PDF", pdf_bytes, "Medical_Portfolio.pdf", "application/pdf")

if st.session_state.authenticated: main_dashboard()
else: login_screen()
