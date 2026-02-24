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

# --- 2. SESSION STATE ---
# Initializing with explicit keys to prevent Line 134/197 errors
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
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

# --- 3. AUTO-POPULATION LOGIC ---
def auto_populate_cv(text):
    """Rule-based extraction for clinical markers."""
    # Clinical History
    exp_pattern = r"\b(SHO|Registrar|Resident|Fellow|Consultant|Intern|Lekarz|Rezydent|Medical Officer)\b"
    hosp_pattern = r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*\s(?:Hospital|Medical Center|Clinic|Trust|Infirmary))"
    
    found_roles = re.findall(exp_pattern, text, re.IGNORECASE)
    found_hosps = re.findall(hosp_pattern, text)
    
    for i in range(min(len(found_roles), len(found_hosps))):
        # We use consistent keys: 'Entry', 'Details', 'Source'
        st.session_state.portfolio_data["Experience"].append({
            "Role/Entry": found_roles[i].upper(), 
            "Institution/Details": found_hosps[i], 
            "Source": "Auto-Detected"
        })

    # Procedures
    proc_list = ["Intubation", "Cannulation", "Lumbar Puncture", "Central Line", "Chest Drain", "Suturing"]
    for p in proc_list:
        if p.lower() in text.lower():
            st.session_state.portfolio_data["Procedures"].append({
                "Procedure/Entry": p, 
                "Competency/Details": "Level 3 (Supervised)",
                "Source": "Auto-Detected"
            })

    # Academic / Audit
    if any(x in text.lower() for x in ["audit", "qip", "quality improvement"]):
        st.session_state.portfolio_data["Academic"].append({
            "Type/Entry": "Audit/QIP", 
            "Title/Details": "Detected Project", 
            "Source": "Auto-Detected"
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
        st.header("🛂 Passport Control")
        up_file = st.file_uploader("Upload Medical CV", type=['pdf', 'docx'])
        if up_file:
            raw_txt = get_raw_text(up_file)
            if raw_txt and st.button("🚀 Auto-Populate from CV"):
                auto_populate_cv(raw_txt)
                st.success("CV Scanned Successfully.")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Medical Career Passport")
    
    tabs = st.tabs(["🌐 Equivalency", "🏥 Experience", "💉 Procedures", "🔬 Academic/QIP", "📄 Export"])

    # TAB 1: EQUIVALENCY
    with tabs[0]:
        st.subheader("International Grade Selection")
        
        target_country = st.selectbox("Compare to Jurisdiction:", ["UK (GMC)", "USA (ACGME)", "Australia (AMC)", "Poland (NIL)"])
        
        base = ["Intern / FY1", "SHO / PGY-2", "Registrar / Fellow", "Consultant / Attending"]
        mapping = {
            "UK (GMC)": ["Foundation Year 1", "Foundation Year 2 / SHO", "Registrar (ST3+)", "Consultant"],
            "USA (ACGME)": ["Intern (PGY-1)", "Resident (PGY-2/3)", "Fellow", "Attending Physician"],
            "Australia (AMC)": ["Intern", "Resident (RMO/HMO)", "Registrar", "Consultant / Specialist"],
            "Poland (NIL)": ["Stażysta", "Rezydent (Młodszy)", "Rezydent (Starszy)", "Specjalista"]
        }
        
        eq_df = pd.DataFrame({"Global Tier": base, f"{target_country} Equivalent": mapping[target_country]})
        st.table(eq_df)

    # TAB 2: EXPERIENCE (Line 134 Fix)
    with tabs[1]:
        st.subheader("Clinical Rotations")
        with st.expander("➕ Add Manual Entry"):
            with st.form("add_exp"):
                r = st.text_input("Role")
                l = st.text_input("Hospital")
                if st.form_submit_button("Save Entry"):
                    st.session_state.portfolio_data["Experience"].append({
                        "Role/Entry": r, "Institution/Details": l, "Source": "Manual"
                    })
        
        # Check if list is not empty AND is a list of dicts
        if st.session_state.portfolio_data["Experience"]:
            st.table(pd.DataFrame(st.session_state.portfolio_data["Experience"]))
        else:
            st.info("No experience data found yet.")

    # TAB 3: PROCEDURES
    with tabs[2]:
        st.subheader("Procedural Logbook")
        
        with st.expander("➕ Log Manual Procedure"):
            with st.form("add_proc"):
                p_name = st.text_input("Procedure Name")
                p_lvl = st.selectbox("Competency Level", ["Level 1 (Observed)", "Level 2 (Supervised)", "Level 3 (Independent)"])
                if st.form_submit_button("Log Procedure"):
                    st.session_state.portfolio_data["Procedures"].append({
                        "Procedure/Entry": p_name, "Competency/Details": p_lvl, "Source": "Manual"
                    })
        
        if st.session_state.portfolio_data["Procedures"]:
            st.table(pd.DataFrame(st.session_state.portfolio_data["Procedures"]))
        else:
            st.info("No procedures logged.")

    # TAB 4: ACADEMIC (Line 197 Fix)
    with tabs[3]:
        st.subheader("Audits, Teaching & Research")
        
        with st.expander("➕ Add Academic Entry"):
            with st.form("add_acad"):
                a_type = st.selectbox("Type", ["Audit/QIP", "Teaching", "Research", "Publication"])
                a_title = st.text_input("Title/Description")
                if st.form_submit_button("Add to Passport"):
                    st.session_state.portfolio_data["Academic"].append({
                        "Type/Entry": a_type, "Title/Details": a_title, "Source": "Manual"
                    })
        
        if st.session_state.portfolio_data["Academic"]:
            st.table(pd.DataFrame(st.session_state.portfolio_data["Academic"]))
        else:
            st.info("No academic entries found.")

    # TAB 5: EXPORT
    with tabs[4]:
        st.subheader("Jurisdictional Export")
        st.write("Choose jurisdictions to include in your verified summary:")
        
        inc_uk = st.checkbox("Include UK (GMC) Equivalency Standards", value=True)
        inc_au = st.checkbox("Include Australia (AMC) Equivalency Standards")

        if st.button("🛠️ Generate Medical Passport"):
            all_entries = []
            for category in st.session_state.portfolio_data.values():
                all_entries.extend(category)
            
            if all_entries:
                df_export = pd.DataFrame(all_entries)
                csv = df_export.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Verified Passport (CSV)", data=csv, file_name="Medical_Passport.csv")
                st.success("Passport generation complete.")
            else:
                st.error("No data found to export. Please upload a CV or enter data manually.")

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
