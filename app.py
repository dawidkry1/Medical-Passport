import streamlit as st
import time
import pandas as pd
from supabase import create_client, Client

# --- 1. CORE CONFIGURATION ---
st.set_page_config(page_title="Medical Passport", page_icon="🏥", layout="wide")

# Secure connection to Supabase
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
client = create_client(URL, KEY)

# Initialize Session States
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

# --- DATABASE UTILITIES ---
def fetch_user_data(table_name):
    try:
        res = client.table(table_name).select("*").eq("user_email", st.session_state.user_email).execute()
        return res.data
    except Exception as e:
        return []

# --- 2. THE PASSPORT DASHBOARD ---
def main_dashboard():
    st.sidebar.title("🏥 Clinical Session")
    st.sidebar.write(f"**Verified Physician:**\n{st.session_state.user_email}")
    
    if st.sidebar.button("🚪 Log Out", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

    st.title("🩺 Professional Medical Passport")
    st.caption("Global Physician Credential Vault & Clinical Logbook")
    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        "🏥 Clinical Rotations", 
        "💉 Procedural Logbook", 
        "🔬 Academic & QIP", 
        "🛡️ Document Vault"
    ])

    # --- TAB 1: ROTATIONS ---
    with tab1:
        st.subheader("Clinical Experience Ledger")
        rotations = fetch_user_data("rotations")
        if rotations:
            df_rot = pd.DataFrame(rotations).drop(columns=['id', 'user_email'], errors='ignore')
            st.data_editor(df_rot, use_container_width=True, disabled=True)
        else:
            st.info("No clinical rotations logged.")

        with st.expander("➕ Log New Placement"):
            with st.form("new_rotation"):
                c1, c2 = st.columns(2)
                h = c1.text_input("Hospital / Trust")
                s = c2.selectbox("Specialty", ["General Medicine", "General Surgery", "ICU/Anaesthetics", "Emergency Medicine", "Paediatrics", "OBGYN", "Psychiatry", "GP"])
                c3, c4 = st.columns(2)
                d = c3.text_input("Dates (e.g. 2024-2025)")
                r = c4.text_input("Grade (e.g. FY2, Registrar)")
                if st.form_submit_button("Sync to Passport"):
                    client.table("rotations").insert({"user_email": st.session_state.user_email, "hospital": h, "specialty": s, "dates": d, "grade": r}).execute()
                    st.success("Rotation Archived")
                    st.rerun()

    # --- TAB 2: PROCEDURAL LOGBOOK ---
    with tab2:
        st.subheader("Competency & Procedural Skills")
        st.write("Evidence of clinical proficiency for international medical boards.")
        
        procs = fetch_user_data("procedures")
        if procs:
            df_proc = pd.DataFrame(procs).drop(columns=['id', 'user_email'], errors='ignore')
            st.table(df_proc)

        with st.form("new_procedure"):
            p1, p2, p3 = st.columns([2, 2, 1])
            p_name = p1.text_input("Procedure Name", placeholder="e.g. Pleural Aspiration")
            p_level = p2.select_slider("Competency", options=["Observed", "Supervised", "Independent", "Assessor"])
            p_count = p3.number_input("Total Count", min_value=1)
            if st.form_submit_button("Log Competency"):
                client.table("procedures").insert({"user_email": st.session_state.user_email, "procedure": p_name, "level": p_level, "count": p_count}).execute()
                st.rerun()

    # --- TAB 3: ACADEMIC & QIP ---
    with tab3:
        st.subheader("Research, Audit & Quality Improvement")
        projects = fetch_user_data("projects")
        if projects:
            for p in projects:
                with st.container(border=True):
                    st.write(f"**{p['type']}**: {p['title']}")
                    st.caption(f"Role: {p['role']} | Year: {p['year']}")

        with st.expander("➕ Add Project/Publication"):
            with st.form("new_project"):
                p_type = st.selectbox("Category", ["Clinical Audit", "QIP", "Research Publication", "Case Report", "Teaching Program"])
                p_title = st.text_input("Project Title")
                p_role = st.text_input("Your Role (e.g. Lead Auditor)")
                p_year = st.text_input("Year")
                if st.form_submit_button("Submit to Portfolio"):
                    client.table("projects").insert({"user_email": st.session_state.user_email, "type": p_type, "title": p_title, "role": p_role, "year": p_year}).execute()
                    st.rerun()

    # --- TAB 4: DOCUMENT VAULT ---
    with tab4:
        st.subheader("🛡️ Cloud-Synced Credentials")
        uploaded_file = st.file_uploader("Upload Medical Degree / License / ALS", type=["pdf", "jpg", "png"])
        
        if uploaded_file:
            safe_email = st.session_state.user_email.replace("@", "_").replace(".", "_")
            file_path = f"{safe_email}/{uploaded_file.name}"
            if st.button("🚀 Secure Upload"):
                try:
                    file_bytes = uploaded_file.getvalue()
                    m_type = "application/pdf" if uploaded_file.type == "application/pdf" else "image/jpeg"
                    client.storage.from_("credentials").upload(path=file_path, file=file_bytes, file_options={"content-type": m_type, "x-upsert": "true"})
                    st.success("Archived successfully.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error(f"Upload Error: {e}")

        st.divider()
        try:
            safe_email = st.session_state.user_email.replace("@", "_").replace(".", "_")
            files = client.storage.from_("credentials").list(safe_email)
            if files:
                for f in files:
                    if f['name'] == '.emptyFolderPlaceholder': continue
                    c_ico, c_file, c_view = st.columns([1, 8, 3])
                    c_ico.write("📄" if f['name'].endswith('pdf') else "🖼️")
                    c_file.write(f"**{f['name']}**")
                    res = client.storage.from_("credentials").create_signed_url(f"{safe_email}/{f['name']}", 60)
                    c_view.link_button("👁️ View", res['signedURL'], use_container_width=True)
        except: st.info("Vault is currently empty.")

# --- 3. AUTHENTICATION LOGIC ---
def handle_recovery():
    params = st.query_params
    if params.get("type") == "recovery" and params.get("code"):
        st.title("🛡️ Account Recovery")
        new_p = st.text_input("Set New Password", type="password")
        if st.button("Update & Login"):
            try:
                client.auth.exchange_code_for_session({"auth_code": params.get("code")})
                client.auth.update_user({"password": new_p})
                st.success("Password Updated!")
                time.sleep(2)
                st.query_params.clear()
                st.rerun()
            except Exception as e: st.error(f"Recovery failed: {e}")
        return True
    return False

def login_screen():
    st.title("🏥 Medical Passport Gateway")
    mode = st.radio("Access", ["Login", "Register", "Forgot Password"], horizontal=True)
    st.write("---")
    if mode == "Login":
        e = st.text_input("Work Email")
        p = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True):
            try:
                res = client.auth.sign_in_with_password({"email": e, "password": p})
                if res.session:
                    st.session_state.authenticated = True
                    st.session_state.user_email = e
                    st.rerun()
            except: st.error("Authentication failed.")
    elif mode == "Register":
        reg_e = st.text_input("Work Email")
        reg_p = st.text_input("Password", type="password")
        if st.button("Create Physician Account"):
            try:
                client.auth.sign_up({"email": reg_e, "password": reg_p})
                st.success("Check your email for the verification link!")
            except Exception as e: st.error(f"Error: {e}")
    elif mode == "Forgot Password":
        f_e = st.text_input("Email")
        if st.button("Send Recovery Link"):
            actual_url = "https://medical-passport.streamlit.app" 
            client.auth.reset_password_for_email(f_e, options={"redirect_to": f"{actual_url}?type=recovery"})
            st.success("Link sent.")

# --- 4. EXECUTION ---
if not handle_recovery():
    if st.session_state.authenticated:
        main_dashboard()
    else:
        login_screen()
