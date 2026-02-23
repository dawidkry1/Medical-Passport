# --- TAB 1: EQUIVALENCY (Updated Fix) ---
    with tab1:
        st.subheader("Global Seniority Mapping")
        st.info("Translate your current local grade into international equivalents.")
        
        # 1. Fetch current data to pre-fill the selection
        profile_data = fetch_user_data("profiles")
        current_tier_val = profile_data[0]['global_tier'] if profile_data else list(EQUIVALENCY_MAP.keys())[0]
        
        try:
            tier_idx = list(EQUIVALENCY_MAP.keys()).index(current_tier_val)
        except:
            tier_idx = 0

        selected_tier = st.selectbox("Define Your Standardized Level", list(EQUIVALENCY_MAP.keys()), index=tier_idx)
        tier_data = EQUIVALENCY_MAP[selected_tier]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("UK Equivalent", tier_data["UK"])
        c2.metric("US Equivalent", tier_data["US"])
        c3.metric("Aus Equivalent", tier_data["Australia"])
        
        st.write(f"**Clinical Responsibility:** {tier_data['Responsibilities']}")
        
        if st.button("Update Global Tier"):
            try:
                # The 'on_conflict' parameter tells Supabase to overwrite 
                # based on the unique email column
                client.table("profiles").upsert(
                    {"user_email": st.session_state.user_email, "global_tier": selected_tier},
                    on_conflict="user_email"
                ).execute()
                
                st.success("Passport Updated! Your seniority mapping is now synced.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Sync Error: {e}")
