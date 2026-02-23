import streamlit as st
import time
import pandas as pd
from supabase import create_client, Client

# --- 1. CORE CONFIGURATION ---
st.set_page_config(page_title="Medical Passport", page_icon="", layout="wide")

# Secure connection to Supabase
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
client = create_client(URL, KEY)

EQUIVALENCY_MAP = {
    "Tier 1: Junior (Intern/FY1)": {
        "UK": "Foundation Year 1", "US": "PGY-1 (Intern)", "Australia": "Intern",
        "Responsibilities": "Ward based, supervised prescribing, basic procedures."
    },
    "Tier 2: Intermediate (SHO/Resident)": {
        "UK": "FY2 / Core Trainee", "US": "PGY-2/3 (Resident)", "Australia": "Resident / RMO",
        "Responsibilities": "Front-door assessment, managing acute cases, procedural proficiency."
    },
    "Tier 3: Senior (Registrar/Fellow)": {
        "UK": "ST3+ / Registrar", "US": "Chief Resident / Fellow", "Australia": "Registrar",
        "Responsibilities": "Leading teams, specialty decision making, independent in core procedures."
    },
    "Tier 4: Expert (Consultant/Attending)": {
        "UK": "Consultant / SAS", "US": "Attending Physician", "Australia": "Consultant / Specialist",
        "Responsibilities": "Final clinical accountability, service leadership, senior training."
    }
}

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

# --- DATABASE UTILITIES ---
def fetch_user_data(table_name):
    try:
        res = client.table(table_name).select("*").eq("user_email", st.session_state.user_email).execute()
        return res.data
    except:
        return []

# --- 2. THE PASSPORT DASHBOARD ---
def main_dashboard():
    st.sidebar.title("🏥 Clinical Session")
    st.sidebar.write(f"**Verified Physician:**\n{st.session_state.user_email}")
    
    if st.sidebar.button("🚪 Log Out", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

    st.title("🩺 Professional Medical Passport")
    st.caption("International Physician Credential Vault & Equivalency Ledger")
    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🌐 Equivalency", "🏥 Rotations", "💉 Procedures", "🔬 Academic/QIP", "🛡️ Vault"
    ])

    # --- TAB 1: EQUIVALENCY ---
    with tab1:
        st.subheader("Global Seniority Mapping")
        st.info("Mapping your local seniority to international standards ensures your CV is interpreted correctly by overseas boards.")
        
        current_profile = fetch_user_data("profiles")
        current_tier_val = current_profile[0]['global_tier'] if current_profile else list(EQUIVALENCY_MAP.keys())[0]
        
        tier_idx = list(EQUIVALENCY_MAP.keys()).index(current_tier_val) if current_tier_val in EQUIVALENCY_MAP else 0
        selected_tier = st.selectbox("Current Global Equivalent", list(EQUIVALENCY_MAP.keys()), index=tier_idx)
        
        tier_data = EQUIVALENCY_MAP[selected_tier]
        c1, c2, c3 = st.columns(3)
        c1.metric("UK System", tier_data["UK"])
        c2.metric("US System", tier_data["US"])
        c3.metric("Australia", tier_data["Australia"])
        
        if st.button("💾 Lock Equivalency to Passport"):
            try:
                # Standard Upsert
                client.table("profiles").upsert({
                    "user_email": st.session_state.user_email, 
                    "global_tier": selected_tier
                }).execute()
                st.success("Global Mapping Updated!")
                st.rerun()
            except Exception as e:
                st.error(f"Postgrest Error: {e}")

    # --- TAB 2: ROTATIONS ---
    with tab2:
        st.subheader("Clinical Experience Ledger")
        rotations = fetch_user_data("rotations")
        if rotations:
            st.data_editor(pd.DataFrame(rotations).drop(columns=['id', 'user_email'], errors='ignore'), use_container_width=True, disabled=True)
        
        with st.expander("➕ Log New Placement"):
            with st.form("new_rotation"):
                c1, c2 = st.columns(2)
                h, s = c1.text_input("Hospital"), c2.selectbox("Specialty", ["General Medicine", "Surgery", "ICU", "A&E", "Pediatrics", "OBGYN", "GP", "Psychiatry"])
                d, r = st.columns(2)
                dates, grade = d.text_input("Dates (e.g. 2024-2025)"), r.text_input("Local Grade")
                if st.form_submit_button("Sync to Cloud"):
                    client.table("rotations").insert({"user_email": st.session_state.user_email, "hospital": h, "specialty": s, "dates": dates, "grade": grade}).execute()
                    st.rerun()

    # --- TAB 3: PROCEDURES ---
    with tab3:
        st.subheader("Procedural Logbook")
        procs = fetch_user_data("procedures")
        if procs:
            df_p = pd.DataFrame(procs).drop(columns=['id', 'user_email'], errors='ignore')
            st.dataframe(df_p, use_container_width=True)
            st.area_chart(df_p.set_index('procedure')['count'])

        with st.form("new_procedure"):
            p1, p2, p3 = st.columns([2, 2, 1])
            p_name = p1.text_input("Procedure")
            p_level = p2.select_slider("Independence", options=["Observed", "Supervised", "Independent", "Assessor"])
            p_count = p3.number_input("Lifetime Count", min_value=1)
            if st.form_submit_button("Log Skill"):
                client.table("procedures").insert({"user_email": st.session_state.user_email, "procedure": p_name, "level": p_level, "count": p_count}).execute()
                st.rerun()

    # --- TAB 4: ACADEMIC & QIP ---
    with tab4:
        st.subheader("Research, Audit & Leadership")
        projects = fetch_user_data("projects")
        for p in projects:
            with st.container(border=True):
                st.write(f"**{p['type']}**: {p['title']}")
                st.caption(f"Role: {p['role']} | Year: {p['year']}")

        with st.form("new_project"):
            p_type = st.selectbox("Category", ["Clinical Audit", "QIP", "Research Publication", "Teaching", "Leadership"])
            p_title, p_role, p_year = st.text_input("Project Title"), st.text_input("Your Role"), st.text_input("Year")
            if st.form_submit_button("Submit"):
                client.table("projects").insert({"user_email": st.session_state.user_email, "type": p_type, "title": p_title, "role": p_role, "year": p_year}).execute()
                st.rerun()

    # --- TAB 5: DOCUMENT VAULT ---
    with tab5:
        st.subheader("🛡️ Verified Credential Vault")
        uploaded_file = st.file_uploader("Upload Medical Degree / License", type=["pdf", "jpg", "png"])
        if uploaded_file and st.button("🚀 Push to Secure Vault"):
            safe_email = st.session_state.user_email.replace("@", "_").replace(".", "_")
            client.storage.from_("credentials").upload(f"{safe_email}/{uploaded_file.name}", uploaded_file.getvalue(), {"content-type": "application/pdf" if "pdf" in uploaded_file.type else "image/jpeg", "x-upsert": "true"})
            st.success("Archived.")
            st.rerun()

        st.divider()
        try:
            safe_email = st.session_state.user_email.replace("@", "_").replace(".", "_")
            for f in client.storage.from_("credentials").list(safe_email):
                if f['name'] == '.emptyFolderPlaceholder': continue
                col_i, col_f, col_v = st.columns([1, 8, 3])
                col_i.write("📄" if f['name'].endswith('pdf') else "🖼️")
                col_f.write(f"**{f['name']}**")
                res = client.storage.from_("credentials").create_signed_url(f"{safe_email}/{f['name']}", 60)
                col_v.link_button("👁️ View", res['signedURL'], use_container_width=True)
        except: st.info("Vault empty.")

# --- 3. AUTHENTICATION ---
def login_screen():
    st.title("🏥 Medical Passport Gateway")
    mode = st.radio("Access", ["Login", "Register"], horizontal=True)
    e, p = st.text_input("Work Email"), st.text_input("Password", type="password")
    
    if mode == "Login" and st.button("Sign In"):
        try:
            res = client.auth.sign_in_with_password({"email": e, "password": p})
            if res.session:
                st.session_state.authenticated, st.session_state.user_email = True, e
                st.rerun()
        except: st.error("Login failed. Verify your email if you haven't yet.")
        
    elif mode == "Register" and st.button("Create Account"):
        try:
            client.auth.sign_up({"email": e, "password": p})
            st.success("Verification link sent! Click it to enable data saving.")
        except Exception as ex: st.error(f"Registration error: {ex}")

if st.session_state.authenticated:
    main_dashboard()
else:
    login_screen()
