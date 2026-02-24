import streamlit as st
import pandas as pd
from supabase import create_client
import pdfplumber
import docx
import re

# --- 1. CORE CONFIG ---
st.set_page_config(page_title="Global Medical Passport", page_icon="🏥", layout="wide")

# Connection Setup
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase_client = create_client(URL, KEY)
except Exception as e:
    st.error(f"Configuration Error: {e}")

# --- 2. SESSION STATE (The Fix for 137/207) ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Ensure the portfolio dictionary and its lists are always initialized
if 'portfolio_data' not in st.session_state:
    st.session_state.portfolio_data = {
        "Experience": [],
        "Procedures": [],
        "Academic": []
    }

def handle_login():
    try:
        res = supabase_client.auth.sign_in_with_password({
            "email": st.session_state.login_email, 
            "password": st.session_state.login_password
        })
        if res.user:
            st.session_state.authenticated = True
    except Exception as e:
        st.error(f"Login failed: {e}")

# --- 3. THE DOCTOR-CENTRIC LOGIC ENGINE ---
def auto_populate_cv(text):
    """Scans CV for clinical markers using standardized keys."""
    # Clinical History Patterns
    exp_pattern = r"\b(SHO|Registrar|Resident|Fellow|Consultant|Intern|Lekarz|Rezydent|Medical Officer)\b"
    hosp_pattern = r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*\s(?:Hospital|Medical Center|Clinic|Trust|Infirmary))"
    
    found_roles = re.findall(exp_pattern, text, re.IGNORECASE)
    found_hosps = re.findall(hosp_pattern, text)
    
    for i in range(min(len(found_roles), len(found_hosps))):
        st.session_state.portfolio_data["Experience"].append({
            "Entry": found_roles[i].upper(), 
            "Details": found_hosps[i], 
            "Type": "Rotation",
            "Source": "Auto"
        })

    # Procedure Patterns
    proc_list = ["Intubation", "Cannulation", "Lumbar Puncture", "Central Line", "Chest Drain", "Suturing"]
    for p in proc_list:
        if p.lower() in text.lower():
            st.session_state.portfolio_data["Procedures"].append({
                "Entry": p, 
                "Details": "Level 3 (Independent)",
                "Type": "Procedure",
                "Source": "Auto"
            })

    # Academic Markers
    if any(x in text.lower() for x in ["audit", "qip", "quality improvement", "teaching"]):
        st.session_state.portfolio_data["Academic"].append({
            "Entry": "Quality/Teaching", 
            "Details": "Identified in CV", 
            "Type": "Academic",
            "Source": "Auto"
        })

def get_raw_text(file):
    try:
        if file.name.endswith('.pdf'):
            with pdfplumber.open(file) as pdf:
                return "\n".join([page.extract_text() or "" for page in pdf.pages])
        elif file.name.endswith('.docx'):
            doc = docx.Document(file)
            return "\n".join([p.text for p in doc.paragraphs])
    except: return ""

# --- 4. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Clinical Portfolio")
        up_file = st.file_uploader("Upload CV (PDF/DOCX)", type=['pdf', 'docx'])
        if up_file:
            raw_txt = get_raw_text(up_file)
            if raw_txt and st.button("🚀 Auto-Populate All Tabs"):
                auto_populate_cv(raw_txt)
                st.success("CV Processed. Check relevant tabs.")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    
    tabs = st.tabs(["🌐 Equivalency", "🏥 Experience", "💉 Procedures", "🔬 Academic/QIP", "📄 Export"])

    # TAB 1: EQUIVALENCY (The Doctor-to-Doctor Translation)
    with tabs[0]:
        st.subheader("International Grade Mapping")
        
        target_country = st.selectbox("Compare your grade to:", ["UK (GMC)", "USA (ACGME)", "Australia (AMC)", "Poland (NIL)"])
        
        base = ["Intern / FY1", "SHO / PGY-2", "Registrar / Fellow", "Consultant / Attending"]
        mapping = {
            "UK (GMC)": ["Foundation Year 1", "Foundation Year 2 / SHO", "Registrar (ST3+)", "Consultant"],
            "USA (ACGME)": ["Intern (PGY-1)", "Resident (PGY-2/3)", "Fellow", "Attending Physician"],
            "Australia (AMC)": ["Intern", "Resident (RMO/HMO)", "Registrar", "Consultant / Specialist"],
            "Poland (NIL)": ["Stażysta", "Rezydent (Młodszy)", "Rezydent (Starszy)", "Specjalista"]
        }
        
        eq_df = pd.DataFrame({"Global Standard": base, f"{target_country} Equivalent": mapping[target_country]})
        st.table(eq_df)

    # TAB 2: EXPERIENCE (Manual + Auto)
    with tabs[1]:
        st.subheader("Clinical History")
        with st.expander("➕ Manually Add Rotation"):
            with st.form("add_exp"):
                role = st.text_input("Role (e.g. SHO)")
                hosp = st.text_input("Hospital")
                if st.form_submit_button("Add Entry"):
                    st.session_state.portfolio_data["Experience"].append({
                        "Entry": role, "Details": hosp, "Type": "Manual Rotation", "Source": "User"
                    })
        
        if st.session_state.portfolio_data["Experience"]:
            st.table(pd.DataFrame(st.session_state.portfolio_data["Experience"]))
        else:
            st.info("No rotations detected. Upload a CV or use the form above.")

    # TAB 3: PROCEDURES
    with tabs[2]:
        st.subheader("Procedural Competency")
        
        with st.expander("➕ Log Manual Procedure"):
            with st.form("add_proc"):
                p_name = st.text_input("Procedure")
                p_lvl = st.selectbox("Competency Level", ["Level 1 (Observed)", "Level 2 (Supervised)", "Level 3 (Independent)"])
                if st.form_submit_button("Log Skill"):
                    st.session_state.portfolio_data["Procedures"].append({
                        "Entry": p_name, "Details": p_lvl, "Type": "Manual Procedure", "Source": "User"
                    })
        
        if st.session_state.portfolio_data["Procedures"]:
            st.table(pd.DataFrame(st.session_state.portfolio_data["Procedures"]))

    # TAB 4: ACADEMIC/QIP
    with tabs[3]:
        st.subheader("Teaching, Audits & Research")
        
        with st.expander("➕ Add Academic Activity"):
            with st.form("add_acad"):
                a_type = st.selectbox("Activity Type", ["Audit/QIP", "Teaching", "Research", "Publication"])
                a_title = st.text_input("Title/Topic")
                if st.form_submit_button("Save"):
                    st.session_state.portfolio_data["Academic"].append({
                        "Entry": a_type, "Details": a_title, "Type": "Manual Academic", "Source": "User"
                    })
        
        if st.session_state.portfolio_data["Academic"]:
            st.table(pd.DataFrame(st.session_state.portfolio_data["Academic"]))

    # TAB 5: EXPORT (Jurisdictional Choice)
    with tabs[4]:
        st.subheader("Generate Global Summary")
        st.write("Select the jurisdictional standards to include in your final export:")
        
        c1, c2 = st.columns(2)
        with c1:
            inc_uk = st.checkbox("Include UK (GMC) Equivalencies", value=True)
            inc_au = st.checkbox("Include Australia (AMC) Equivalencies")
        with c2:
            inc_us = st.checkbox("Include US (ACGME) Equivalencies")
            inc_pl = st.checkbox("Include Poland (NIL) Equivalencies")

        if st.button("🛠️ Export Verified Passport"):
            all_combined = []
            for category in st.session_state.portfolio_data.values():
                all_combined.extend(category)
            
            if all_combined:
                df_export = pd.DataFrame(all_combined)
                csv = df_export.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Passport (CSV)", data=csv, file_name="Verified_Medical_Passport.csv")
            else:
                st.error("No data available to export. Please add clinical data first.")

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
