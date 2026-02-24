import streamlit as st
import pandas as pd
from supabase import create_client
import google.generativeai as genai
import pdfplumber
import docx
import time

# --- 1. CORE CONFIG ---
st.set_page_config(page_title="Global Medical Passport", page_icon="🏥", layout="wide")

# Connection Setup
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase_client = create_client(URL, KEY)
    
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    else:
        st.error("⚠️ GEMINI_API_KEY missing.")
except Exception as e:
    st.error(f"Config Error: {e}")

# --- 2. SESSION STATE ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'scraped_text' not in st.session_state:
    st.session_state.scraped_text = ""

def handle_login():
    try:
        res = supabase_client.auth.sign_in_with_password({"email": st.session_state.login_email, "password": st.session_state.login_password})
        if res.user:
            st.session_state.authenticated = True
            st.session_state.user_email = res.user.email
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

def run_unified_scan(full_text):
    # Try current stable 2.0 first, then fallbacks
    model_options = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']
    prompt = (
        "Identify clinical rotations, hospitals, and procedures in this CV. "
        "Format as: 'ITEM: [Title] at [Hospital]'. "
        f"\n\nCV Text:\n{full_text[:7000]}"
    )

    for m_name in model_options:
        try:
            model = genai.GenerativeModel(m_name)
            response = model.generate_content(prompt)
            if response.text:
                return response.text
        except Exception as e:
            if "404" in str(e):
                continue # Try the next model name
            return f"API ERROR ({m_name}): {str(e)}"
            
    return "ERROR: All available Gemini models returned 404. Check API Key permissions."

# --- 4. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Clinical Portfolio")
        
        # Connection Health Check
        if st.button("🧪 Connection Health Check"):
            try:
                # Try the list call to see what models are actually enabled
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                st.write("Authorized Models:")
                st.write(models)
            except Exception as e:
                st.error(f"Handshake Failed: {e}")

        st.divider()
        up_file = st.file_uploader("Upload CV", type=['pdf', 'docx'])
        
        if up_file:
            raw_txt = get_raw_text(up_file)
            if raw_txt:
                st.info(f"Loaded {len(raw_txt)} chars.")
                if st.button("🚀 Sync Clinical Portfolio"):
                    with st.spinner("Routing to active model..."):
                        st.session_state.scraped_text = run_unified_scan(raw_txt)
            else:
                st.error("No text found.")

        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    
    tabs = st.tabs(["🌐 Equivalency", "🏥 Clinical Records", "🔬 Raw Data"])

    # 1. EQUIVALENCY
    with tabs[0]:
        st.subheader("International Grade Mapping")
        
        st.info("Mapping identifies your grade for international registration (GMC, AMC, AHPRA).")
        st.table(pd.DataFrame([
            {"Region": "UK", "Equivalent": "Foundation Year 2 (SHO)"},
            {"Region": "US", "Equivalent": "PGY-2 (Resident)"},
            {"Region": "Australia", "Equivalent": "Resident Medical Officer"}
        ]))

    # 2. CLINICAL RECORDS
    with tabs[1]:
        st.subheader("Experience & Logbook")
        
        if st.session_state.scraped_text:
            items = [l.replace("ITEM:", "").strip() for l in st.session_state.scraped_text.split('\n') if "ITEM:" in l.upper()]
            if items:
                for item in items:
                    st.write(f"✅ {item}")
            else:
                st.warning("Analysis complete, but no 'ITEM:' tags found. Review Raw Data tab.")
        else:
            st.info("Upload your CV to populate your medical passport.")

    # 3. RAW DATA
    with tabs[2]:
        st.subheader("AI System Output")
        if st.session_state.scraped_text:
            st.text_area("Full Response:", value=st.session_state.scraped_text, height=300)
        else:
            st.write("No active session data.")

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Passport Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
