from fpdf import FPDF
import io

# --- PDF GENERATOR CLASS ---
class MedicalCV(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Professional Medical Portfolio / CV', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, 'Generated via Medical Passport Digital Ledger', 0, 1, 'C')
        self.ln(5)

    def section_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 8, title, 0, 1, 'L', fill=True)
        self.ln(2)

def generate_pdf(email, profile, rotations, procedures, projects):
    pdf = MedicalCV()
    pdf.add_page()
    
    # Header Info
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, f"Physician: {email}", 0, 1)
    
    # Global Tier Section
    tier = profile[0]['global_tier'] if profile else "Not Defined"
    pdf.section_title("Global Seniority & Equivalency")
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 6, f"Standardized Level: {tier}")
    pdf.ln(4)

    # Rotations
    pdf.section_title("Clinical Rotations & Placements")
    for r in rotations:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, f"{r['hospital']} - {r['specialty']}", 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f"Role: {r['grade']} | Dates: {r['dates']}", 0, 1)
        pdf.ln(2)

    # Procedures Summary
    pdf.section_title("Procedural Logbook Summary")
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(80, 7, "Procedure", 1)
    pdf.cell(50, 7, "Competency Level", 1)
    pdf.cell(30, 7, "Total Count", 1, 1)
    pdf.set_font('Arial', '', 9)
    for p in procedures:
        pdf.cell(80, 7, p['procedure'], 1)
        pdf.cell(50, 7, p['level'], 1)
        pdf.cell(30, 7, str(p['count']), 1, 1)
    pdf.ln(5)

    # Academic
    pdf.section_title("Academic, QIP & Research")
    for pr in projects:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, f"{pr['type']}: {pr['title']}", 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f"Role: {pr['role']} ({pr['year']})", 0, 1)
        pdf.ln(2)

    return pdf.output(dest='S').encode('latin-1')

# --- UPDATED MAIN DASHBOARD ---
def main_dashboard():
    # ... (Keep your existing Sidebar and Summary Card code here) ...

    # Add the "Export" tab to your tabs list
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🌐 Equivalency", "🏥 Rotations", "💉 Procedures", "🔬 Academic/QIP", "🛡️ Vault", "📄 Export CV"
    ])

    # ... (Keep existing tab logic for 1 through 5) ...

    with tab6:
        st.subheader("Automated CV Generator")
        st.write("This tool compiles all your verified passport data into a professional PDF format.")
        
        # Fetch all data for the PDF
        profile = fetch_user_data("profiles")
        rotations = fetch_user_data("rotations")
        procedures = fetch_user_data("procedures")
        projects = fetch_user_data("projects")

        if st.button("🏗️ Compile Medical CV"):
            with st.spinner("Aggregating clinical data..."):
                pdf_data = generate_pdf(st.session_state.user_email, profile, rotations, procedures, projects)
                
                st.success("CV Compiled Successfully!")
                st.download_button(
                    label="⬇️ Download Professional CV (PDF)",
                    data=pdf_data,
                    file_name=f"Medical_Passport_CV_{st.session_state.user_email.split('@')[0]}.pdf",
                    mime="application/pdf"
                )
