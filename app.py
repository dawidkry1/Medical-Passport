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

# --- 3. MEDICAL AUTO-DETECTION ---
def auto_populate_cv(text):
    """Rule-based extraction for clinical markers."""
    exp_pattern = r"\b(SHO|Registrar|Resident|Fellow|Consultant|Intern|Attending|Specialist|HMO|RMO|ST\d|CT\d)\b"
    hosp_pattern = r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*\s(?:Hospital|Medical Center|Clinic|Trust|Infirmary|Health Service))"
    
    found_roles = re.findall(exp_pattern, text, re.IGNORECASE)
    found_hosps = re.findall(hosp_pattern, text)
    
    for i in range(min(len(found_roles), len(found_hosps))):
        st.session_state.portfolio_data["Experience"].append({
            "Entry": found_roles[i].upper(), 
            "Details": found_hosps[i], 
            "Category": "Clinical Rotation",
            "Source": "Auto-Detected"
        })

    proc_list = ["Intubation", "Cannulation", "Lumbar Puncture", "Central Line", "Chest Drain", "Suturing", "Ventilation"]
    for p in proc_list:
        if p.lower() in text.lower():
            st.session_state.portfolio_data["Procedures"].append({
                "Entry": p, "Details": "Level 3 (Competent)", "Category": "Skill", "Source": "Auto"
            })

    if any(x in text.lower() for x in ["audit", "qip", "research", "teaching", "publication"]):
        st.session_state.portfolio_data["Academic"].append({
            "Entry": "Portfolio Evidence", "Details": "Identified in CV", "Category": "Academic", "Source": "Auto"
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
        st.header("🛂 Portfolio Sync")
        up_file = st.file_uploader("Upload Medical CV", type=['pdf', 'docx'])
        if up_file:
            raw_txt = get_raw_text(up_file)
            if raw_txt and st.button("🚀 Auto-Populate All Categories"):
                auto_populate_cv(raw_txt)
                st.success("CV Data Parsed.")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    
    tabs = st.tabs(["🌐 Dynamic Equivalency", "🏥 Experience", "💉 Procedures", "🔬 Academic/QIP", "📄 Export"])

    # TAB 1: DYNAMIC EQUIVALENCY (UK/USA Cross-Base)
    with tabs[0]:
        st.subheader("Global Jurisdiction Comparison")
        
        
        # 1. Base System Toggle
        base_system = st.radio("Select Your Professional Base:", ["United Kingdom (GMC)", "United States (ACGME)"], horizontal=True)
        
        # 2. Select Grade based on base system
        if base_system == "United Kingdom (GMC)":
            grade_options = ["FY1", "FY2 / SHO", "Registrar (ST3-ST8)", "Consultant"]
            default_targets = ["United States (ACGME)", "Poland", "Switzerland"]
        else:
            grade_options = ["Intern (PGY-1)", "Resident (PGY-2+)", "Fellow", "Attending Physician"]
            default_targets = ["United Kingdom (GMC)", "Poland", "Switzerland"]
            
        my_grade = st.selectbox(f"Select your current {base_system} grade:", grade_options)
        
        # 3. Target Jurisdictions (Including the alternate base system)
        target_list = ["United Kingdom (GMC)", "United States (ACGME)", "Poland", "EU (General)", "Dubai (DHA)", "China", "South Korea", "Switzerland"]
        
        # Remove the base system from the target list to avoid self-comparison
        clean_target_list = [t for t in target_list if t != base_system]
        
        selected_targets = st.multiselect("Compare to following jurisdictions:", clean_target_list, default=[t for t in default_targets if t != base_system])
        
        # Mapping Dictionary (Unified by Tier Index)
        tier_idx = grade_options.index(my_grade)
        
        mapping_matrix = {
            "United Kingdom (GMC)": ["FY1", "FY2 / SHO", "Registrar (ST3-ST8)", "Consultant"],
            "United States (ACGME)": ["Intern (PGY-1)", "Resident (PGY-2+)", "Fellow", "Attending Physician"],
            "Poland": ["Stażysta", "Rezydent (Młodszy)", "Rezydent (Starszy)", "Lekarz Specjalista"],
            "EU (General)": ["Junior Doctor", "Senior Resident", "Specialist Registrar", "Specialist / Consultant"],
            "Dubai (DHA)": ["Intern", "Resident / GP", "Registrar", "Consultant"],
            "China": ["Intern", "Resident", "Attending Physician", "Chief Physician"],
            "South Korea": ["Intern", "Resident", "Fellow", "Specialist / Professor"],
            "Switzerland": ["Unterassistenzarzt", "Assistenzarzt", "Oberarzt", "Leitender Arzt / Chefarzt"]
        }
        
        if selected_targets:
            res = {"Jurisdiction": [], "Equivalent Grade": []}
            for target in selected_targets:
                res["Jurisdiction"].append(target)
                res["Equivalent Grade"].append(mapping_matrix[target][tier_idx])
            
            st.table(pd.DataFrame(res))
        else:
            st.warning("Select target countries to view comparisons.")

    # TAB 2: EXPERIENCE
    with tabs[1]:
        st.subheader("Clinical Rotations")
        with st.expander("➕ Add Manual Entry"):
            with st.form("exp_form"):
                e_role = st.text_input("Role")
                e_hosp = st.text_input("Hospital")
                if st.form_submit_button("Save"):
                    st.session_state.portfolio_data["Experience"].append({"Entry": e_role, "Details": e_hosp, "Category": "Rotation", "Source": "Manual"})
        
        if st.session_state.portfolio_data["Experience"]:
            st.table(pd.DataFrame(st.session_state.portfolio_data["Experience"]))

    # TAB 3: PROCEDURES
    with tabs[2]:
        st.subheader("Procedural Competency")
        
        with st.expander("➕ Log Procedure"):
            with st.form("proc_form"):
                p_name = st.text_input("Procedure Name")
                p_lvl = st.selectbox("Level", ["Level 1 (Observed)", "Level 2 (Supervised)", "Level 3 (Independent)"])
                if st.form_submit_button("Log"):
                    st.session_state.portfolio_data["Procedures"].append({"Entry": p_name, "Details": p_lvl, "Category": "Skill", "Source": "Manual"})
        
        if st.session_state.portfolio_data["Procedures"]:
            st.table(pd.DataFrame(st.session_state.portfolio_data["Procedures"]))

    # TAB 4: ACADEMIC/QIP
    with tabs[3]:
        st.subheader("Audit & Research")
        
        with st.expander("➕ Add Academic Activity"):
            with st.form("acad_form"):
                a_type = st.selectbox("Type", ["Audit/QIP", "Research", "Teaching", "Publication"])
                a_title = st.text_input("Title/Description")
                if st.form_submit_button("Save Entry"):
                    st.session_state.portfolio_data["Academic"].append({"Entry": a_type, "Details": a_title, "Category": "Academic", "Source": "Manual"})
        
        if st.session_state.portfolio_data["Academic"]:
            st.table(pd.DataFrame(st.session_state.portfolio_data["Academic"]))

    # TAB 5: EXPORT
    with tabs[4]:
        st.subheader("Tailored CV Export")
        st.write("Confirming Jurisdictions for Export:")
        for t in selected_targets:
            st.write(f"✅ {t} (Mapped as: {mapping_matrix[t][tier_idx]})")
            
        if st.button("🛠️ Export Final Passport"):
            all_data = []
            for cat in st.session_state.portfolio_data.values():
                all_data.extend(cat)
            
            if all_data:
                # Append jurisdictional statements based on the toggled targets
                for t in selected_targets:
                    all_data.append({
                        "Entry": f"{t} Status", 
                        "Details": mapping_matrix[t][tier_idx], 
                        "Category": "Jurisdictional Equivalency", 
                        "Source": "Verified Algorithm"
                    })
                
                df_export = pd.DataFrame(all_data)
                csv = df_export.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Passport (CSV)", data=csv, file_name="Verified_Medical_Passport.csv")
            else:
                st.error("No clinical data to export.")

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Passport Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
