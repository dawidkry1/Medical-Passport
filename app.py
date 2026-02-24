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
    # This list covers every naming convention known to cause 404s
    model_options = [
        'gemini-2.0-flash', 
        'models/gemini-2.0-flash', 
        'gemini-1.5-flash', 
        'models/gemini-1.5-flash',
        'gemini-pro'
    ]
    
    prompt = (
        "Extract all medical career history from this text. "
        "List hospital names, job titles, and clinical procedures. "
        "Prefix every finding with 'ITEM: '."
        f"\n\nCV DATA:\n{full_text[:7000]}"
    )

    for m_name in model_options:
        try:
            model = genai.GenerativeModel(m_name)
            response = model.generate_content(prompt)
            if response.text:
                return response.text
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                continue # Try next version
            return f"API ERROR ({m_name}): {str(e)}"
            
    return "ERROR: All model versions (2.0, 1.5, Pro) returned 404. Your API Key may not have Model access enabled in Google AI Studio."

# --- 4. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Clinical Portfolio")
        
        # API Handshake Debug
        if st.button("🔍 Check Authorized Models"):
            try:
                m_list = [m.name for m in genai.list_models()]
                st.write("Your Key supports:")
                st.json(m_list)
            except Exception as e:
                st.error(f"Cannot list models: {e}")

        st.divider()
        up_file = st.file_uploader("Upload CV", type=['pdf', 'docx'])
        manual_text = st.text_area("OR Paste CV Text Here", height=150)
        
        target_text = ""
        if up_file: target_text = get_raw_text(up_file)
        elif manual_text: target_text = manual_text

        if target_text and st.button("🚀 Sync Medical Portfolio"):
            with st.spinner("Finding an active Gemini model..."):
                st.session_state.scraped_text = run_unified_scan(target_text)

        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    
    tabs = st.tabs(["🌐 Equivalency", "🏥 Clinical Records", "🔬 Diagnostic"])

    # 1. EQUIVALENCY
    with tabs[0]:
        st.subheader("International Grade Mapping")
        
        st.table(pd.DataFrame([
            {"Region": "UK", "Equivalent": "Foundation Year 2 (SHO)"},
            {"Region": "US", "Equivalent": "PGY-2 (Resident)"},
            {"Region": "Australia", "Equivalent": "Resident Medical Officer"}
        ]))

    # 2. CLINICAL RECORDS
    with tabs[1]:
        st.subheader("Experience & Procedures")
        
        if st.session_state.scraped_text:
            items = [l.replace("ITEM:", "").strip() for l in st.session_state.scraped_text.split('\n') if "ITEM:" in l.upper()]
            if items:
                for item in items:
                    st.write(f"✅ {item}")
            else:
                st.warning("No 'ITEM:' entries found. See Diagnostic tab.")
        else:
            st.info("Paste your CV text or upload a file to begin.")

    # 3. DIAGNOSTIC
    with tabs[2]:
        st.subheader("Raw AI Response")
        if st.session_state.scraped_text:
            st.text_area("Output Log:", value=st.session_state.scraped_text, height=300)
        else:
            st.write("No session data.")

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Passport Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
