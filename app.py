import streamlit as st
import pandas as pd
from supabase import create_client
import google.generativeai as genai
import pdfplumber
import docx

# --- 1. CORE CONFIG ---
st.set_page_config(page_title="Medical Passport Cloud", page_icon="🏥", layout="wide")

# Connection Setup
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase_client = create_client(URL, KEY)
    
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    else:
        st.error("⚠️ GEMINI_API_KEY missing in secrets.")
except Exception as e:
    st.error(f"Initialization Error: {e}")

# --- 2. SESSION STATE ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'scraped_text' not in st.session_state:
    st.session_state.scraped_text = ""

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

# --- 3. EXTRACTION ENGINE ---
def get_raw_text(file):
    text = ""
    try:
        if file.name.endswith('.pdf'):
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + "\n"
        elif file.name.endswith('.docx'):
            doc = docx.Document(file)
            text = "\n".join([p.text for p in doc.paragraphs])
        return text.strip()
    except: return ""

def run_gemini_scan(full_text):
    # Try the new stable 2.0 Lite first, fall back to 1.5 Flash (not lite) if needed
    model_names = ['gemini-2.0-flash-lite', 'gemini-1.5-flash']
    
    prompt = (
        "You are an expert medical recruiter. Extract clinical roles, hospital names, "
        "and specific procedures from this CV. Format each as: 'ITEM: [Role] at [Hospital]'. "
        f"\n\nCV DATA:\n{full_text[:8000]}"
    )

    for m_name in model_names:
        try:
            model = genai.GenerativeModel(m_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if "404" in str(e):
                continue
            return f"API ERROR: {str(e)}"
    
    return "CRITICAL ERROR: No compatible Gemini models found for your API key."

# --- 4. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Clinical Portfolio")
        
        # DEBUG: Find out what models YOUR key actually has
        if st.button("🔍 Scan My Available Models"):
            try:
                models = [m.name for m in genai.list_models()]
                st.write("Your key sees these models:")
                st.json(models)
            except Exception as e:
                st.error(f"Could not list models: {e}")

        st.divider()
        up_file = st.file_uploader("Upload CV (PDF/DOCX)", type=['pdf', 'docx'])
        
        if up_file:
            raw_txt = get_raw_text(up_file)
            if raw_txt:
                st.info(f"Loaded {len(raw_txt)} characters.")
                if st.button("🚀 Sync Clinical Data"):
                    with st.spinner("Analyzing Medical History..."):
                        st.session_state.scraped_text = run_gemini_scan(raw_txt)

        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    
    tabs = st.tabs(["🌐 Equivalency", "🏥 Clinical Records", "🔬 System Log"])

    # 1. EQUIVALENCY (Doctor-to-Doctor Perspective)
    with tabs[0]:
        st.subheader("International Seniority Translation")
        
        st.write("Translating your domestic grade into international standards.")
        st.table(pd.DataFrame([
            {"Region": "United Kingdom", "Equivalent Grade": "Foundation Year 2 / SHO"},
            {"Region": "United States", "Equivalent Grade": "PGY-2 Resident"},
            {"Region": "Australia", "Equivalent Grade": "Resident Medical Officer (RMO)"}
        ]))

    # 2. CLINICAL RECORDS
    with tabs[1]:
        st.subheader("Verified Clinical History")
        
        if st.session_state.scraped_text:
            items = [l.replace("ITEM:", "").strip() for l in st.session_state.scraped_text.split('\n') if "ITEM:" in l.upper()]
            if items:
                for item in items:
                    st.write(f"✅ **{item}**")
            else:
                st.warning("Analysis complete, but no roles were identified. Check System Log.")
        else:
            st.info("Please upload your CV to extract your clinical history.")

    # 3. SYSTEM LOG
    with tabs[2]:
        st.subheader("Raw AI Response")
        if st.session_state.scraped_text:
            st.text_area("Response Text:", value=st.session_state.scraped_text, height=400)
        else:
            st.write("No data processed yet.")

# --- LOGIN GATE ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
