import streamlit as st
import time
import pandas as pd
from supabase import create_client, Client

# --- 1. CORE CONFIGURATION ---
st.set_page_config(page_title="Medical Passport", page_icon="🏥", layout="wide")

# Secure connection to Supabase
# Ensure these are set in your Streamlit Secrets
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
client = create_client(URL, KEY)

# Initialize Session States
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""
if 'rotations' not in st.session_state:
    st.session_state.rotations = [] 

# --- 2. THE PASSPORT DASHBOARD ---
def main_dashboard():
    # Sidebar Navigation
    st.sidebar.title("🏥 Clinical Session")
    st.sidebar.write(f"**Verified User:**\n{st.session_state.user_email}")
    
    if st.sidebar.button("🚪 Log Out", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

    st.title("🩺 Professional Medical Passport")
    st.caption("Permanent Cloud-Synced Ledger & Multimedia Credential Vault")
    st.divider()

    tab1, tab2 = st.tabs(["🏥 Clinical Rotations", "📜 Permanent Credential Vault"])

    # --- TAB 1: ROTATIONS ---
    with tab1:
        st.subheader("Clinical Experience Ledger")
        st.write("Maintain a history of placements. Double-click cells to edit or correct details.")

        if st.session_state.rotations:
            df = pd.DataFrame(st.session_state.rotations)
            edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="rot_edit")
            if st.button("💾 Save Ledger Edits"):
                st.session_state.rotations = edited_df.to_dict('records')
                st.success("Ledger updated locally.")
        else:
            st.info("No rotations logged yet. Use the form below to start your passport.")

        with st.form("new_rotation", clear_on_submit=True):
            st.write("### ➕ Log New Experience")
            c1, c2, c3 = st.columns(3)
            h = c1.text_input("Hospital", placeholder="e.g. St Mary's")
            s = c2.text_input("Specialty", placeholder="e.g. Acute Medicine")
            d = c3.text_input("Dates", placeholder="e.g. 2025-2026")
            if st.form_submit_button("Add to Ledger"):
                if h and s and d:
                    st.session_state.rotations.append({"Hospital": h, "Specialty": s, "Dates": d})
                    st.rerun()
                else:
                    st.error("Please fill in all clinical fields.")

    # --- TAB 2: MULTI-FORMAT STORAGE ---
    with tab2:
        st.subheader("🛡️ Cloud-Synced Documents")
        st.write("Upload certificates or photos of credentials (**PDF, JPG, PNG**).")

        # Upload Section
        uploaded_file = st.file_uploader("Upload Medical Credential", type=["pdf", "jpg", "jpeg", "png"])
        
        if uploaded_file:
            # Create a folder path based on user email
            safe_email = st.session_state.user_email.replace("@", "_").replace(".", "_")
            file_path = f"{safe_email}/{uploaded_file.name}"
            
            if st.button("🚀 Push to Permanent Vault"):
                try:
                    file_bytes = uploaded_file.getvalue()
                    
                    # Detect mime-type for the cloud storage
                    m_type = "application/pdf" if uploaded_file.type == "application/pdf" else "image/jpeg"
                    
                    # Upload to 'credentials' bucket (Ensure this bucket is created in Supabase)
                    client.storage.from_("credentials").upload(
                        path=file_path,
                        file=file_bytes,
                        file_options={"content-type": m_type, "x-upsert": "true"}
                    )
                    st.success(f"Archived: {uploaded_file.name}")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Upload Error: {e}")

        st.divider()
        st.write("### 📂 Your Verified Archives")
        
        try:
            safe_email = st.session_state.user_email.replace("@", "_").replace(".", "_")
            files = client.storage.from_("credentials").list(safe_email)
            
            if files:
                for f in files:
                    if f['name'] == '.emptyFolderPlaceholder': continue
                    
                    col_ico, col_file, col_view = st.columns([1, 8, 3])
                    
                    # Visual distinction for file types
                    ext = f['name'].split('.')[-1].lower()
                    icon = "📄" if ext == "pdf" else "🖼️"
                    
                    col_ico.write(icon)
                    col_file.write(f"**{f['name']}**")
                    
                    # Create a 60-second signed URL for secure viewing
                    res = client.storage.from_("credentials").create_signed_url(f"{safe_email}/{f['name']}", 60)
                    col_view.link_button("👁️ View/Download", res['signedURL'], use_container_width=True)
            else:
                st.info("Cloud vault is empty.")
        except Exception as e:
            st.error("Connect to Supabase Storage to see archives.")

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
        e = st.text_input("Email")
        p = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True):
            try:
                res = client.auth.sign_in_with_password({"email": e, "password": p})
                if res.session:
                    st.session_state.authenticated = True
                    st.session_state.user_email = e
                    st.rerun()
            except: st.error("Login failed. Check your details.")

    elif mode == "Register":
        st.subheader("New Clinical Account")
        reg_e = st.text_input("Work Email")
        reg_p = st.text_input("Password", type="password")
        if st.button("Register", use_container_width=True):
            try:
                res = client.auth.sign_up({"email": reg_e, "password": reg_p})
                if res.user and not res.user.identities:
                    st.warning("This email is already registered.")
                else:
                    st.success("Verification email sent! Please confirm to activate your passport.")
            except Exception as e: st.error(f"Error: {e}")

    elif mode == "Forgot Password":
        st.subheader("Recovery")
        f_e = st.text_input("Email")
        if st.button("Send Link"):
            # Ensure this matches your Streamlit deployment URL
            actual_url = "https://medical-passport.streamlit.app" 
            client.auth.reset_password_for_email(f_e, options={"redirect_to": f"{actual_url}?type=recovery"})
            st.success("Recovery link sent.")

# --- 4. EXECUTION ---
if not handle_recovery():
    if st.session_state.authenticated:
        main_dashboard()
    else:
        login_screen()
