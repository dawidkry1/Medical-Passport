import streamlit as st
import pandas as pd
from supabase import create_client
import google.generativeai as genai
import pdfplumber
import docx
import time

# --- 1. CORE CONFIG ---
st.set_page_config(page_title="Global Medical Passport", page_icon="🏥", layout="wide")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stAppDeployButton {display:none;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

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
    # We try multiple model names to solve the 404
    model_names = ['gemini-1.5-flash', 'models/gemini-1.5-flash', 'gemini-pro']
    last_error = ""
    
    prompt = (
        "Extract every clinical job and hospital from this CV. "
        "Format each as: 'ITEM: [Job Title] at [Hospital]'. "
        f"\n\nCV Text:\n{full_text[:6000]}"
    )

    for name in model_names:
        try:
            model = genai.GenerativeModel(name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            last_error = str(e)
            continue
            
    return f"CRITICAL ERROR: All models failed. Last error: {last_error}"

# --- 4. MAIN DASHBOARD ---
def main_dashboard():
    with st.sidebar:
        st.header("🛂 Clinical Portfolio")
        
        # DEBUG: Help identify why 404 is happening
        if st.button("🔍 List Available Models"):
            try:
                available = [m.name for m in genai.list_models()]
                st.write("Your Key has access to:")
                st.write(available)
            except Exception as e:
                st.error(f"API Access Error: {e}")

        st.divider()
        up_file = st.file_uploader("Upload Medical CV", type=['pdf', 'docx'])
        
        if up_file:
            raw_txt = get_raw_text(up_file)
            if raw_txt:
                st.info(f"File Size: {len(raw_txt)} characters.")
                if st.button("🚀 Sync Portfolio"):
                    with st.spinner("Bypassing 404 and extracting..."):
                        st.session_state.scraped_text = run_unified_scan(raw_txt)
            else:
                st.error("Text Extraction Failed.")

        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🩺 Global Medical Passport")
    
    tabs = st.tabs(["🌐 Equivalency", "🏥 Clinical Records", "🔬 Raw Feed"])

    # 1. EQUIVALENCY
    with tabs[0]:
        st.subheader("International Grade Mapping")
        
        st.write("Mapping your seniority for international medical boards.")
        st.table(pd.DataFrame([
            {"Region": "UK", "Equivalent": "Foundation Year 2 (SHO)"},
            {"Region": "US", "Equivalent": "PGY-2 (Resident)"},
            {"Region": "Australia", "Equivalent": "Resident Medical Officer"}
        ]))

    # 2. CLINICAL RECORDS
    with tabs[1]:
        st.subheader("Extracted Experiences")
        
        if st.session_state.scraped_text:
            # Look for our ITEM: tag
            items = [l.replace("ITEM:", "").strip() for l in st.session_state.scraped_text.split('\n') if "ITEM:" in l.upper()]
            if items:
                for item in items:
                    st.write(f"✅ {item}")
            else:
                st.warning("Model responded but couldn't find clinical items. Check the Raw Feed.")
        else:
            st.info("Sync your CV to begin.")

    # 3. RAW FEED
    with tabs[2]:
        st.subheader("API Diagnostic")
        if st.session_state.scraped_text:
            st.text_area("Response Log", value=st.session_state.scraped_text, height=300)
        else:
            st.write("No data processed.")

# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🏥 Medical Passport Gateway")
    with st.form("login"):
        st.text_input("Email", key="login_email")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("Sign In", on_click=handle_login)
else:
    main_dashboard()
