import re
import html
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import inch
from reportlab.lib import colors

def _ensure_folder(path: str):
    """Helper: Ensures directory exists."""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def format_clinical_text(text: str) -> str:
    """
    Converts raw AI text (Markdown-style) into ReportLab-friendly XML.
    - **text** -> <b>text</b>
    - ## Header -> <b><font size=12>Header</font></b>
    - Handles newlines for Paragraph flow.
    """
    if not text: return ""
    
    # Remove horizontal rules
    text = re.sub(r'^-{3,}', '', text, flags=re.MULTILINE)
    
    # 1. Bold: **text** -> <b>text</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    
    # 2. Bold: __text__ -> <b>text</b>
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    
    # 3. Headers: ## Text -> Bold Larger
    # Clean up leading ##
    text = re.sub(r'^(#+)\s*(.*)', r'<b><font size=12>\2</font></b><br/>', text, flags=re.MULTILINE)
    
    return text.strip()

# ... (get_clinical_image, create_patient_summary_pdf remain same) ...

def create_patient_pdf(patient_id: str, doc_type: str, content: str, patient_persona=None, doc_metadata=None, base_output_folder: str = "documents", image_path: str = None):
    """
    Generates a PDF report for a given patient and document type.
    Embeds clinical images if relevant.
    Rendering: Professional Lab/Consult Report Header.
    """
    # Use the passed folder directly - assuming it is the FULL path to the patient's report folder
    patient_folder = base_output_folder
    _ensure_folder(patient_folder)
        
    if doc_type.startswith("DOC-"):
        filename = f"{doc_type}.pdf" if not doc_type.endswith(".pdf") else doc_type
    else:
        filename = f"Patient_{patient_id}_{doc_type}.pdf"
        
    file_path = os.path.join(patient_folder, filename)
    
    doc = SimpleDocTemplate(file_path, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    
    col_dark_blue = colors.HexColor("#34495e")
    col_gray = colors.gray
    
    # Styles
    style_tit = ParagraphStyle('MainTitle', parent=styles['Heading1'], textColor=col_dark_blue, 
                               borderPadding=0, borderWidth=0, alignment=1)
    style_sub = ParagraphStyle('SubTitle', parent=styles['Normal'], fontSize=9, textColor=col_gray, alignment=0)
    style_sub_right = ParagraphStyle('SubTitleRight', parent=styles['Normal'], fontSize=9, textColor=col_dark_blue, alignment=2)
    style_normal = ParagraphStyle('Justify', parent=styles['Normal'], alignment=4, leading=14) 

    Story = []
    
    # --- PROFESSIONAL HEADER (Face Sheet) ---
    if patient_persona and doc_metadata:
        # Data Extraction
        fac_name = getattr(doc_metadata, 'facility_name', 'General Hospital')
        prov_name = getattr(doc_metadata, 'provider_name', 'Unknown Provider')
        svc_date = getattr(doc_metadata, 'service_date', datetime.now().strftime("%Y-%m-%d"))
        acc_num = getattr(doc_metadata, 'accession_number', f"ACC-{patient_id}-000")
        
        p_name = f"{patient_persona.first_name} {patient_persona.last_name}"
        p_dob = patient_persona.dob
        
        # Calculate Current MRN dynamic if not passed (though generator should pass it, we can re-derive or use generic)
        # Assuming mrn is usually passed but we didn't add it to signature explicitly to avoid breaking changes, 
        # let's try to grab it from persona if stored, or generate.
        # Actually, let's look for 'mrn' in persona dict/object if it was saved.
        # For this context, let's construct it same as generator.
        p_mrn = f"MRN-{patient_id}-{svc_date[:4]}" # Fallback logic
        
        # Left Column: Facility & Provider
        header_left = [
            Paragraph(f"<b>{fac_name}</b>", styles['Heading3']),
            Paragraph(f"123 Medical Center Dr, Suite 100", style_sub),
            Paragraph(f"City, State, 12345", style_sub),
            Spacer(1, 4),
            Paragraph(f"<b>Ordering Provider:</b><br/>{prov_name}", style_sub)
        ]
        
        # Right Column: Patient Demographics & Accession
        header_right = [
            Paragraph(f"<b>PATIENT: {p_name.upper()}</b>", style_sub_right),
            Paragraph(f"MRN: {p_mrn} | DOB: {p_dob}", style_sub_right),
            Paragraph(f"GENDER: {patient_persona.gender.upper()}", style_sub_right),
            Spacer(1, 4),
            Paragraph(f"<b>SERVICE DATE: {svc_date}</b>", style_sub_right),
            Paragraph(f"ACCESSION #: {acc_num}", style_sub_right)
        ]
        
        # Table Layout
        header_table = Table([[header_left, header_right]], colWidths=[3.5*inch, 3.5*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor("#bdc3c7")),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ]))
        Story.append(header_table)
        Story.append(Spacer(1, 20))
        
        # Document Title
        clean_title = doc_type.replace('_', ' ').upper()
        if hasattr(doc_metadata, 'title_hint'):
            clean_title = doc_metadata.title_hint.replace('_', ' ').upper()
            
        Story.append(Paragraph(f"{clean_title}", style_tit))
        Story.append(Spacer(1, 20))
        
    else:
        # Fallback for simple calls
        title_str = doc_type.replace('_', ' ').upper()
        Story.append(Paragraph(f"CLINICAL DOCUMENT: {title_str}", styles['Heading1']))
        Story.append(Spacer(1, 20))
    
    # Check for image
    if image_path and os.path.exists(image_path):
        Story.append(Paragraph("<b>Attached Clinical Imaging:</b>", styles["Heading3"]))
        Story.append(Spacer(1, 5))
        # Keep aspect ratio?
        img = Image(image_path, width=4*inch, height=3*inch, kind='proportional')
        Story.append(img)
        Story.append(Spacer(1, 15))

    # Content
    if not patient_persona: # Only show this generic header if professional header wasn't used
        Story.append(Paragraph(f"<b>REPORT CONTENT:</b>", styles["Heading3"]))
        Story.append(Spacer(1, 10))
    
    # Pre-process content: Markdown to ReportLab XML
    # Step 1: Convert markdown (**bold**, ## headers) to XML tags
    formatted_content = format_clinical_text(content)
    
    # Step 2: Handle newlines for paragraph flow
    formatted_content = formatted_content.replace('\n', '<br/>')
    
    # Step 3: Render with fallback for malformed XML
    try:
        Story.append(Paragraph(formatted_content, style_normal))
    except ValueError as e:
        # Fallback: escape everything if parsing fails
        import html
        safe_content = html.escape(content).replace('\n', '<br/>')
        Story.append(Paragraph(safe_content, style_normal))
        print(f"   ⚠️ PDF Format Warning: Used plain text fallback due to: {e}")
    
    Story.append(Spacer(1, 12))
            
    doc.build(Story)
    return file_path

def get_clinical_image(doc_title: str):
    """
    Returns the path to a matching clinical asset image based on title keywords.
    """
    title_lower = doc_title.lower()
    
    if any(k in title_lower for k in ['ecg', 'ekg', 'rhythm', 'cardio']):
        return "assets/ecg.png"
    if any(k in title_lower for k in ['x-ray', 'xray', 'radiograph', 'chest']):
        return "assets/xray.png"
    if any(k in title_lower for k in ['mri', 'ct', 'scan', 'imaging', 'resonance']):
        return "assets/mri.png"
    return None

def create_patient_summary_pdf(patient_id, summary_data, output_folder: str = None):
    """
    Creates a highly styled Clinical Summary PDF.
    """
    # 1. Folder Management
    if output_folder:
        output_dir = output_folder # Explicit path
    else:
        output_dir = f"documents/{patient_id}" # Fallback
        
    _ensure_folder(output_dir)

    filename = f"Clinical_Summary_Patient_{patient_id}.pdf"
    file_path = os.path.join(output_dir, filename)
    
    doc = SimpleDocTemplate(file_path, pagesize=letter,
                            rightMargin=50, leftMargin=50,
                            topMargin=50, bottomMargin=50)

    # Styles
    styles = getSampleStyleSheet()
    
    # Custom Colors
    col_green = colors.HexColor("#27ae60")
    col_blue = colors.HexColor("#2980b9")
    col_light_blue = colors.HexColor("#f0f7fb")
    col_dark_blue = colors.HexColor("#34495e")
    
    # Custom Styles
    style_tit = ParagraphStyle('MainTitle', parent=styles['Heading1'], textColor=col_green, 
                               borderPadding=10, borderWidth=0, borderBottomWidth=2, borderColor=colors.HexColor("#2ecc71"))
    
    style_h2 = ParagraphStyle('SecTitle', parent=styles['Heading2'], textColor=col_blue, backColor=col_light_blue,
                              borderPadding=8, borderWidth=0, borderLeftWidth=4, borderColor=colors.HexColor("#3498db"), spaceBefore=20)
    
    style_label = ParagraphStyle('Label', parent=styles['Normal'], fontName='Helvetica-Bold', textColor=colors.gray)
    style_val = ParagraphStyle('Value', parent=styles['Normal'])

    Story = []
    
    # --- TITLE ---
    Story.append(Paragraph(f"Patient Clinical Summary (Approval Case)", style_tit))
    Story.append(Spacer(1, 20))
    
    # --- DEMOGRAPHICS GRID (Using Table) ---
    # Row 1: Headers
    data_demo = [
        [Paragraph("<b>Patient Details</b>", styles["Heading3"]), Paragraph("<b>Contact & Provider</b>", styles["Heading3"])],
        [
            Paragraph(f"<b>Name:</b> {summary_data.get('name', 'Unknown')}<br/>"
                      f"<b>DOB:</b> {summary_data.get('dob', '1980-01-01')}<br/>"
                      f"<b>Gender:</b> {summary_data.get('gender', 'Unknown')}<br/>"
                      f"<b>MRN:</b> {summary_data.get('mrn', 'N/A')}", style_val),
            
            Paragraph(f"<b>Address:</b> {summary_data.get('address', 'Unknown')}<br/>"
                      f"<b>Phone:</b> 555-0199<br/>"
                      f"<b>Provider:</b> {summary_data.get('provider', 'Dr. Smith')}<br/>"
                      f"<b>Facility:</b> {summary_data.get('facility', 'General Hospital')}", style_val)
        ]
    ]
    
    t_demo = Table(data_demo, colWidths=[3.5*inch, 3.5*inch])
    t_demo.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    Story.append(t_demo)
    
    # --- DIAGNOSIS ---
    Story.append(Paragraph("Current Diagnoses", style_h2))
    Story.append(Spacer(1, 10))
    
    diag_data = [['Code', 'Condition', 'Status', 'Date Recorded']]
    # Add dummy data or passed data
    for d in summary_data.get('diagnoses', []):
        diag_data.append([d['code'], d['condition'], d['status'], d['date']])
        
    t_diag = Table(diag_data, colWidths=[1*inch, 3*inch, 1.5*inch, 1.5*inch])
    t_diag.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f2f2f2")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    Story.append(t_diag)
    
    # --- TIMELINE ---
    Story.append(Paragraph("Clinical Encounters & Documentation", style_h2))
    Story.append(Spacer(1, 10))
    
    for event in summary_data.get('timeline', []):
        p_event = Paragraph(f"<font color='#34495e' backColor='#34495e'><b>&nbsp;{event['date']}&nbsp;</b></font>&nbsp; <b>{event['title']}</b>", styles["Normal"])
        Story.append(p_event)
        for detail in event['details']:
             Story.append(Paragraph(detail, ParagraphStyle('d', leftIndent=20, parent=styles['Normal'])))
        Story.append(Spacer(1, 10))

    # --- PLAN ---
    Story.append(Paragraph("Proposed Treatment Plan", style_h2))
    Story.append(Spacer(1, 10))
    
    plan_text = f"""
    <b>Procedure:</b> {summary_data.get('procedure', 'N/A')}<br/>
    <b>Outcome:</b> {summary_data.get('outcome', 'N/A')}<br/>
    <b>Clinical Rationale:</b> {summary_data.get('rationale', 'See LMN')}<br/>
    """
    Story.append(Paragraph(plan_text, styles["Normal"]))

    doc.build(Story)
    return file_path

def create_persona_pdf(patient_id: str, patient_name: str, persona: object, generated_reports: list = None, image_map: dict = None, mrn: str = "N/A", output_folder: str = "documents/personas"):
    """
    Generates a comprehensive Patient Master Record from Structured Data.
    - **Header**: Official Record Title.
    - **Face Sheet**: Structured Table (Identity, Contacts, Provider).
    - **Bio Narrative**: The Markdown story.
    - **Clinical Assets**: Reports & Images.
    """
    persona_folder = output_folder
    _ensure_folder(persona_folder)

    safe_name = patient_name.replace(" ", "_").replace("/", "-")
    filename = f"{patient_id}-{safe_name}-persona.pdf"
    file_path = os.path.join(persona_folder, filename)

    doc = SimpleDocTemplate(file_path, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Premium Colors
    col_header = colors.HexColor("#2c3e50") # Dark Blue
    col_accent = colors.HexColor("#e67e22") # Orange
    col_bg = colors.HexColor("#ecf0f1")
    
    style_tit = ParagraphStyle('MainTitle', parent=styles['Heading1'], textColor=col_header, 
                               alignment=1, fontSize=24, spaceAfter=20)
    
    style_h2 = ParagraphStyle('SecTitle', parent=styles['Heading2'], textColor=col_header, backColor=col_bg,
                              borderPadding=6, spaceBefore=15, spaceAfter=10)
    
    style_h3 = ParagraphStyle('SubTitle', parent=styles['Heading3'], textColor=col_accent, spaceBefore=10)
    
    style_normal = ParagraphStyle('Body', parent=styles['Normal'], leading=14, fontSize=10)
    style_label = ParagraphStyle('Lbl', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10)
    
    Story = []

    # --- HEADER ---
    Story.append(Paragraph(f"CONFIDENTIAL PATIENT MASTER RECORD", style_tit))
    Story.append(Paragraph(f"<b>PATIENT ID: {patient_id}  |  MRN: {mrn}</b>", ParagraphStyle('pid', parent=style_normal, alignment=1, fontSize=12)))
    Story.append(Spacer(1, 15))
    
    # --- FACE SHEET (Structured Data) ---
    Story.append(Paragraph("I. REGISTRATION FACE SHEET", style_h2))
    
    # Extract Data safely (assuming Pydantic object)
    p = persona 
    
    # === SECTION 1: PATIENT IDENTITY ===
    data_identity = [
        [Paragraph("<b>PATIENT IDENTITY</b>", style_label), ""],
        ["Name:", f"{p.first_name} {p.last_name}"],
        ["DOB:", f"{p.dob}"],
        ["Gender:", p.gender],
        ["Race:", getattr(p, 'race', 'N/A')],
        ["Height:", getattr(p, 'height', 'N/A')],
        ["Weight:", getattr(p, 'weight', 'N/A')],
        ["Telecom:", p.telecom],
        ["Address:", p.address],
        ["Marital Status:", p.maritalStatus or "N/A"],
        ["Multiple Birth:", f"{'Yes' if p.multipleBirthBoolean else 'No'} (Order: {getattr(p, 'multipleBirthInteger', 1)})"],
    ]
    
    # === SECTION 2: COMMUNICATION ===
    comm = getattr(p, 'communication', None)
    data_communication = [
        [Paragraph("<b>COMMUNICATION</b>", style_label), ""],
        ["Language:", getattr(comm, 'language', 'English') if comm else 'English'],
        ["Preferred:", "Yes" if (getattr(comm, 'preferred', True) if comm else True) else "No"],
    ]
    
    # === SECTION 3: EMERGENCY CONTACT (All Fields) ===
    c = getattr(p, 'contact', None)
    data_contact = [
        [Paragraph("<b>EMERGENCY CONTACT</b>", style_label), ""],
    ]
    if c:
        data_contact.extend([
            ["Relationship:", getattr(c, 'relationship', 'N/A')],
            ["Name:", getattr(c, 'name', 'N/A')],
            ["Telecom:", getattr(c, 'telecom', 'N/A')],
            ["Address:", getattr(c, 'address', 'N/A')],
            ["Gender:", getattr(c, 'gender', 'N/A')],
            ["Organization:", getattr(c, 'organization', 'N/A')],
            ["Period Start:", getattr(c, 'period_start', 'N/A')],
            ["Period End:", getattr(c, 'period_end', 'ongoing')],
        ])
    else:
        data_contact.append(["Details:", "Not Provided"])
    
    # === SECTION 4: PRIMARY PROVIDER ===
    pr = getattr(p, 'provider', None)
    data_provider = [
        [Paragraph("<b>PRIMARY PROVIDER</b>", style_label), ""],
    ]
    if pr:
        data_provider.extend([
            ["General Practitioner:", getattr(pr, 'generalPractitioner', 'N/A')],
            ["Managing Organization:", getattr(pr, 'managingOrganization', 'N/A')],
        ])
    else:
        data_provider.append(["Details:", "Not Provided"])
    
    # === SECTION 5: INSURANCE/PAYER (All Fields) ===
    payer = getattr(p, 'payer', None)
    data_payer = [
        [Paragraph("<b>INSURANCE / PAYER</b>", style_label), ""],
    ]
    if payer:
        data_payer.extend([
            ["Payer ID:", getattr(payer, 'payer_id', 'N/A')],
            ["Payer Name:", getattr(payer, 'payer_name', 'N/A')],
            ["Plan Name:", getattr(payer, 'plan_name', 'N/A')],
            ["Plan Type:", getattr(payer, 'plan_type', 'N/A')],
            ["Group ID:", getattr(payer, 'group_id', 'N/A')],
            ["Group Name:", getattr(payer, 'group_name', 'N/A')],
            ["Member ID:", getattr(payer, 'member_id', 'N/A')],
            ["Policy Number:", getattr(payer, 'policy_number', 'N/A')],
            ["Effective Date:", getattr(payer, 'effective_date', 'N/A')],
            ["Termination Date:", getattr(payer, 'termination_date', 'ongoing')],
            ["Copay:", getattr(payer, 'copay_amount', 'N/A')],
            ["Deductible:", getattr(payer, 'deductible_amount', 'N/A')],
        ])
        # Subscriber Details
        sub = getattr(payer, 'subscriber', None)
        if sub:
            data_payer.extend([
                [Paragraph("<b>SUBSCRIBER</b>", style_label), ""],
                ["Subscriber ID:", getattr(sub, 'subscriber_id', 'N/A')],
                ["Subscriber Name:", getattr(sub, 'subscriber_name', 'N/A')],
                ["Relationship:", getattr(sub, 'subscriber_relationship', 'N/A')],
                ["Subscriber DOB:", getattr(sub, 'subscriber_dob', 'N/A')],
                ["Subscriber Address:", getattr(sub, 'subscriber_address', 'N/A')],
            ])
    else:
        data_payer.append(["Details:", "Not Provided"])
    
    # --- BUILD TABLES ---
    table_style = TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), col_bg),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ])
    
    for data_block, title in [
        (data_identity, "Identity"),
        (data_communication, "Communication"),
        (data_contact, "Contact"),
        (data_provider, "Provider"),
        (data_payer, "Payer"),
    ]:
        t = Table(data_block, colWidths=[1.8*inch, 4.5*inch])
        t.setStyle(table_style)
        Story.append(t)
        Story.append(Spacer(1, 8))
    
    # --- BIO & HISTORY ---
    Story.append(Paragraph("II. MEDICAL BIOGRAPHY & HISTORY", style_h2))
    
    if p.bio_narrative:
        for line in p.bio_narrative.split('\n'):
            line = line.strip()
            if not line: continue
            
            # Use our Regex Formatter!
            line = format_clinical_text(line)
            
            if line.startswith('<b><font size=12>'): # It was a header
                 Story.append(Paragraph(line, style_h3))
            elif line.startswith('• '):
                 Story.append(Paragraph(line, ParagraphStyle('bull', parent=style_normal, leftIndent=15)))
            else:
                 Story.append(Paragraph(line, style_normal))
            Story.append(Spacer(1, 4))
        
    Story.append(Spacer(1, 20))

    # --- REPORTS & IMAGING ---
    if generated_reports:
        # ... (Same as before)
        Story.append(Paragraph("III. CLINICAL REPORTS & IMAGING", style_h2))
        
        for rep in generated_reports:
            # Report Title
            rep_title = rep.title_hint.replace('_', ' ').upper()
            Story.append(Paragraph(f"► {rep_title}", style_h3))
            
            # Check Image
            img_path = None
            if image_map:
                for k, v in image_map.items():
                    if k.startswith(rep.title_hint):
                        img_path = v
                        break
            
            if img_path and os.path.exists(img_path):
                 img = Image(img_path, width=3.5*inch, height=2*inch, kind='proportional')
                 Story.append(img)
                 Story.append(Spacer(1, 5))
            
            # Content
            Story.append(Paragraph("Report Text:", ParagraphStyle('lbl', parent=style_normal, fontName='Helvetica-Bold')))
            
            # Format markdown to styled text with graceful fallback
            formatted_rep = format_clinical_text(rep.content)
            rep_text = formatted_rep[:2000] + "..." if len(formatted_rep) > 2000 else formatted_rep
            rep_text = rep_text.replace('\n', '<br/>')
            
            try:
                Story.append(Paragraph(rep_text, style_normal))
            except ValueError:
                import html
                safe_text = html.escape(rep.content[:2000]).replace('\n', '<br/>')
                Story.append(Paragraph(safe_text, style_normal))
            
            Story.append(Spacer(1, 15))
            Story.append(Paragraph("_" * 60, style_normal)) # Separator

    doc.build(Story)
    return file_path
