import streamlit as st
import pandas as pd
from supabase import create_client
import pdfplumber
import docx
import re
from fpdf import FPDF
from datetime import datetime

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

# --- 3. AUTO-DETECTION ENGINE ---
def auto_populate_cv(text):
    exp_pattern = r"\b(SHO|Registrar|Resident|Fellow|Consultant|Intern|Attending|Specialist|HMO|RMO|ST\d|CT\d)\b"
    hosp_pattern = r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*\s(?:Hospital|Medical Center|Clinic|Trust|Infirmary|Health Service))"
    
    roles = re.findall(exp_pattern, text, re.IGNORECASE)
    hosps = re.findall(hosp_pattern, text)
    
    for i in range(min(len(roles), len(hosps))):
        st.session_state.portfolio_data["Experience"].append({
            "Entry": roles[i].upper(), "Details": hosps[i], "Category": "Rotation", "Source": "Auto"
        })

    proc_list = ["Intubation", "Cannulation", "Lumbar Puncture", "Central Line", "Chest Drain", "Suturing"]
    for p in proc_list:
        if p.lower() in text.lower():
            st.session_state.portfolio_data["Procedures"].append({
                "Entry": p, "Details": "Level 3 (Competent)", "Category": "Skill", "Source": "Auto"
            })

    if any(x in text.lower() for x in ["audit", "qip", "research", "teaching"]):
        st.session_state.portfolio_data["Academic"].append({
            "Entry": "Portfolio Evidence", "Details": "Detected from CV", "Category": "Academic", "Source": "Auto"
        })

def get_raw_text(file):
    try:
        if file.name.endswith('.pdf'):
            with pdfplumber.open(file) as pdf:
                return "\n".join([p.extract_text() or "" for p in pdf.pages])
        elif file.name.endswith('.docx'):
            doc = docx.Document(file)
            return "\n".join([p.text for p in doc.paragraphs])
    except: return ""

# --- 4. PDF GENERATOR CLASS ---
class MedicalPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Verified Global Medical Passport', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'C')
        self.ln(10)

    def section_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 10, title, 0, 1, 'L', fill=True)
        self.ln(4)

    def add_table_row(self, col1, col2, col3):
        self.set_font('Arial', '', 10)
        self.cell(60, 8, str(col1), 1)
        self.cell(90, 8, str(col2), 1)
        self.cell(40, 8, str(col3), 1)
        self.ln()

# --- 5. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Portfolio Sync")
        up_file = st.file_uploader("Upload Medical CV", type=['pdf', 'docx'])
        if up_file and st.button("🚀 Sync All Categories"):
            raw_txt = get_raw_text(up_file)
            if raw_txt:
                auto_populate_cv(raw_txt)
                st.success("CV Parsed.")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    tabs = st.tabs(["🌐 Equivalency", "🏥 Experience", "💉 Procedures", "🔬 Academic/QIP", "📄 PDF Export"])

    # TAB 1: EQUIVALENCY
    with tabs[0]:
        st.subheader("Global Jurisdiction Comparison")
        
        base_system = st.radio("Professional Base:", ["United Kingdom (GMC)", "United States (ACGME)"], horizontal=True)
        grade_options = ["FY1", "FY2 / SHO", "Registrar (ST3-ST8)", "Consultant"] if base_system == "United Kingdom (GMC)" else ["Intern (PGY-1)", "Resident (PGY-2+)", "Fellow", "Attending Physician"]
        my_grade = st.selectbox(f"Current {base_system} grade:", grade_options)
        
        target_list = ["United Kingdom (GMC)", "United States (ACGME)", "Poland", "EU (General)", "Dubai (DHA)", "China", "South Korea", "Switzerland"]
        clean_targets = [t for t in target_list if t != base_system]
        selected_targets = st.multiselect("Compare to:", clean_targets, default=["Poland", "Switzerland"])
        
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
            res_df = pd.DataFrame({"Jurisdiction": selected_targets, "Equivalent Grade": [mapping_matrix[t][tier_idx] for t in selected_targets]})
            st.table(res_df)

    # TABS 2, 3, 4: EXPERIENCE, PROCEDURES, ACADEMIC (Standard Tables)
    for i, category in enumerate(["Experience", "Procedures", "Academic"]):
        with tabs[i+1]:
            st.subheader(f"Current {category}")
            if st.session_state.portfolio_data[category]:
                st.table(pd.DataFrame(st.session_state.portfolio_data[category]))
            else:
                st.info(f"No {category.lower()} data found.")

    # TAB 5: PDF EXPORT
    with tabs[4]:
        st.subheader("Final Export")
        st.write("Exporting all sections + Jurisdictional mappings into a single PDF.")
        
        if st.button("🛠️ Generate Final PDF Passport"):
            pdf = MedicalPDF()
            pdf.add_page()
            
            # 1. Jurisdictions
            pdf.section_title("International Seniority Equivalency")
            pdf.set_font('Arial', 'I', 10)
            pdf.cell(0, 8, f"Base System: {base_system} | Current Grade: {my_grade}", 0, 1)
            pdf.ln(2)
            for t in selected_targets:
                pdf.add_table_row(t, mapping_matrix[t][tier_idx], "Verified Mapping")
            
            # 2. Experience
            pdf.ln(10)
            pdf.section_title("Clinical Rotations & Experience")
            for item in st.session_state.portfolio_data["Experience"]:
                pdf.add_table_row(item['Entry'], item['Details'], item['Source'])

            # 3. Procedures
            pdf.ln(10)
            pdf.section_title("Procedural Logbook")
            for item in st.session_state.portfolio_data["Procedures"]:
                pdf.add_table_row(item['Entry'], item['Details'], "Clinical Skill")

            # 4. Academic
            pdf.ln(10)
            pdf.section_title("Academic, Research & QIP")
            for item in st.session_state.portfolio_data["Academic"]:
                pdf.add_table_row(item['Entry'], item['Details'], "Evidence")

            # Export
            pdf_output = pdf.output(dest='S').encode('latin-1')
            st.download_button(
                label="📥 Download Full PDF Passport",
                data=pdf_output,
                file_name=f"Medical_Passport_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
