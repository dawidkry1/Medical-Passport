import streamlit as st
import pandas as pd
from supabase import create_client
import google.generativeai as genai
import pdfplumber
import docx
import requests
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
except Exception as e:
    st.error(f"Initialization Error: {e}")

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

# --- 3. THE AI ENGINES ---
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

def run_ollama_scan(full_text):
    """Local Processing - No Quota"""
    url = "http://localhost:11434/api/generate"
    prompt = f"Extract all medical jobs and hospitals. Format: 'ITEM: [Job] at [Hospital]'. CV:\n{full_text[:5000]}"
    payload = {"model": "llama3.2", "prompt": prompt, "stream": False}
    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.json().get('response', 'Empty local response.')
    except:
        return "ERROR: Ollama not detected. Ensure it is running locally."

def run_gemini_scan(full_text):
    """Cloud Processing - Using Flash-Lite for higher quota"""
    try:
        # gemini-1.5-flash-lite is the 'most free' high-throughput model
        model = genai.GenerativeModel('gemini-1.5-flash-lite')
        prompt = f"Extract all clinical rotations and hospital roles. Prefix findings with 'ITEM:'. CV:\n{full_text[:8000]}"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"CLOUD ERROR: {str(e)}"

# --- 4. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Portfolio Control")
        
        # Brain Selection Toggle
        ai_choice = st.radio("Select AI Engine:", ["Local (Ollama)", "Cloud (Gemini Lite)"])
        
        st.divider()
        up_file = st.file_uploader("Upload Medical CV", type=['pdf', 'docx'])
        
        if up_file:
            raw_txt = get_raw_text(up_file)
            if raw_txt and st.button("🚀 Sync Medical History"):
                with st.spinner(f"Processing via {ai_choice}..."):
                    if ai_choice == "Local (Ollama)":
                        st.session_state.scraped_text = run_ollama_scan(raw_txt)
                    else:
                        st.session_state.scraped_text = run_gemini_scan(raw_txt)

        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")

    tabs = st.tabs(["🌐 Equivalency", "🏥 Clinical Records", "🔬 AI Raw Output"])

    # 1. EQUIVALENCY (Doctor-to-Doctor Perspective)
    with tabs[0]:
        st.subheader("International Grade Translation")
        
        st.write("This tool ensures that recruiters and medical boards recognize your seniority.")
        st.table(pd.DataFrame([
            {"Region": "UK (GMC)", "Grade": "FY2 / SHO", "Status": "Verified"},
            {"Region": "US (ACGME)", "Grade": "PGY-2 Resident", "Status": "Equivalent"},
            {"Region": "Australia (AHPRA)", "Grade": "RMO", "Status": "Equivalent"}
        ]))

    # 2. CLINICAL RECORDS
    with tabs[1]:
        st.subheader("Extracted Career Timeline")
        
        if st.session_state.scraped_text:
            items = [l.replace("ITEM:", "").strip() for l in st.session_state.scraped_text.split('\n') if "ITEM:" in l.upper()]
            if items:
                for item in items:
                    st.write(f"🔹 **{item}**")
            else:
                st.warning("No specific items found. Check 'AI Raw Output' for details.")
        else:
            st.info("Upload your CV to populate your clinical history.")

    # 3. AI RAW OUTPUT
    with tabs[2]:
        st.subheader("Diagnostic Stream")
        if st.session_state.scraped_text:
            st.text_area("Full Response Log", value=st.session_state.scraped_text, height=400)
        else:
            st.write("Waiting for data sync...")

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
