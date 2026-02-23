import streamlit as st
import time
import pandas as pd
from supabase import create_client, Client
from fpdf import FPDF
import io
import json

# --- 1. CORE CONFIGURATION ---
st.set_page_config(page_title="Global Medical Passport", page_icon="🏥", layout="wide")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stAppDeployButton {display:none;}
            [data-testid="stToolbar"] {visibility: hidden !important;}
            [data-testid="stDecoration"] {display:none;}
            .stButton>button {border-radius: 5px;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
client = create_client(URL, KEY)

# --- EQUIVALENCY DATA (OMITTED FOR BREVITY - SAME AS BEFORE) ---
# [Ensure your EQUIVALENCY_MAP and COUNTRY_KEY_MAP are still in your local file]

# --- 2. PDF GENERATOR ---
class MedicalCV(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Professional Medical Portfolio', 0, 1, 'C')
        self.ln(10)
    def section_header(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, f" {title}", 0, 1, 'L', fill=True)
        self.ln(3)

# --- 3. DATABASE & STORAGE UTILITIES ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user_email' not in st.session_state: st.session_state.user_email = ""

def fetch_user_data(table_name):
    try:
        res = client.table(table_name).select("*").eq("user_email", st.session_state.user_email).execute()
        return res.data
    except: return []

# --- 4. MAIN DASHBOARD ---
def main_dashboard():
    head_col1, head_col2 = st.columns([0.80, 0.20])
    with head_col1:
        st.title("🩺 Global Medical Passport")
        st.caption(f"Physician Session: {st.session_state.user_email}")
    with head_col2:
        st.write("##")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    profile = fetch_user_data("profiles")
    rotations = fetch_user_data("rotations")
    procedures = fetch_user_data("procedures")
    projects = fetch_user_data("projects")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🌐 Equivalency", "🏥 Rotations", "💉 Procedures", "🔬 Academic", "🛡️ Vault", "📄 Export CV"
    ])

    # [Tabs 1-4 remain same as your working version]

    with tab5:
        st.subheader("🛡️ Secure Credential Vault")
        st.write("Upload medical licenses, diplomas, or certificates (PDF/JPG).")
        
        uploaded_file = st.file_uploader("Upload New Document", type=['pdf', 'jpg', 'png'])
        if uploaded_file is not None:
            if st.button("📤 Sync to Secure Cloud"):
                with st.spinner("Encrypting and uploading..."):
                    file_path = f"{st.session_state.user_email}/{uploaded_file.name}"
                    try:
                        # Upload to Supabase Storage Bucket 'medical-vault'
                        client.storage.from_('medical-vault').upload(file_path, uploaded_file.getvalue())
                        st.success(f"Successfully vaulted: {uploaded_file.name}")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Upload failed: {e}")

        st.divider()
        st.write("### Your Vaulted Documents")
        try:
            files = client.storage.from_('medical-vault').list(st.session_state.user_email)
            if files:
                for f in files:
                    col_f1, col_f2 = st.columns([0.8, 0.2])
                    col_f1.write(f"📄 {f['name']}")
                    # Generate a temporary signed URL for viewing (expires in 60 seconds)
                    res_url = client.storage.from_('medical-vault').create_signed_url(f"{st.session_state.user_email}/{f['name']}", 60)
                    col_f2.link_button("View", res_url['signedURL'])
            else:
                st.info("No documents found in your vault.")
        except:
            st.info("Vault folder is currently empty.")

    # [Tab 6 remains same as your working version]

# --- 5. AUTHENTICATION (WORKING VERSION) ---
def login_screen():
    st.title("🏥 Medical Passport Gateway")
    e = st.text_input("Email", key="auth_email")
    p = st.text_input("Password", type="password", key="auth_pass")
    col1, col2 = st.columns(2)
    if col1.button("Login", use_container_width=True):
        try:
            res = client.auth.sign_in_with_password({"email": e, "password": p})
            if res.user:
                st.session_state.authenticated = True
                st.session_state.user_email = e
                st.rerun()
        except: st.error("Verification failed.")

if st.session_state.authenticated:
    main_dashboard()
else:
    login_screen()
