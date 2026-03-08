import re
import html
import os
import json
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import inch
from reportlab.lib import colors

def _ensure_folder(path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def format_clinical_text(text: str) -> str:
    if not text: return ""
    
    text = re.sub(r'^-{3,}', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    text = re.sub(r'^(#+)\s*(.*)', r'<b><font size=12>\2</font></b><br/>', text, flags=re.MULTILINE)
    
    return text.strip()

def format_report_content(content):
    try:
        if isinstance(content, str):
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return html.escape(content).replace('\n', '<br/>')
        else:
            data = content

        if not isinstance(data, dict):
            return html.escape(str(data))

        sections = data.get("sections", [])
        # When AI returns JSON without "sections", render all top-level keys so persona PDF is not blank
        if not sections:
            sections = [k for k in data.keys() if k != "sections"]
        output = []

        def _format_value(val, depth=0):
            indent = "&nbsp;" * (depth * 4)
            if isinstance(val, dict):
                parts = []
                for k, v in val.items():
                    key_title = str(k).replace("_", " ").title()
                    if isinstance(v, (dict, list)):
                        parts.append(f"{indent}<b>{key_title}:</b><br/>{_format_value(v, depth + 1)}")
                    else:
                        parts.append(f"{indent}<b>{key_title}:</b> {html.escape(str(v))}")
                return "<br/>".join(parts)
            elif isinstance(val, list):
                parts = []
                for item in val:
                    if isinstance(item, (dict, list)):
                        parts.append(f"{indent}•<br/>{_format_value(item, depth + 1)}")
                    else:
                        parts.append(f"{indent}• {html.escape(str(item))}")
                return "<br/>".join(parts)
            else:
                return f"{indent}{html.escape(str(val))}"

        for sec in sections:
            value = data.get(sec)
            if value is None or value == "":
                continue

            section_title = sec.replace("_", " ").title()
            output.append(f"<b>{section_title}</b>")
            
            formatted_val = _format_value(value, depth=0)
            output.append(formatted_val)
            output.append("")

        return "<br/>".join(output) if output else html.escape(str(content)).replace('\n', '<br/>')

    except Exception as e:
        print(f"Error formatting report: {e}")
        return html.escape(str(content)).replace('\n', '<br/>')

def create_patient_pdf(patient_id: str, doc_type: str, content: str, patient_persona=None, doc_metadata=None, base_output_folder: str = "documents", image_path: str = None, version: int = 1):
    patient_folder = base_output_folder
    _ensure_folder(patient_folder)

    if doc_type.startswith("DOC-"):
        filename = f"{doc_type}.pdf" if not doc_type.endswith(".pdf") else doc_type
    else:
        filename = f"Patient_{patient_id}_v{version}_{doc_type}.pdf"

    file_path = os.path.join(patient_folder, filename)
    
    doc = SimpleDocTemplate(file_path, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    
    col_dark_blue = colors.HexColor("#34495e")
    col_gray = colors.gray
    
    style_tit = ParagraphStyle('cpdf_MainTitle', parent=styles['Heading1'], textColor=col_dark_blue, 
                               borderPadding=0, borderWidth=0, alignment=1)
    style_sub = ParagraphStyle('cpdf_SubTitle', parent=styles['Normal'], fontSize=9, textColor=col_gray, alignment=0)
    style_sub_right = ParagraphStyle('cpdf_SubTitleRight', parent=styles['Normal'], fontSize=9, textColor=col_dark_blue, alignment=2)
    style_normal = ParagraphStyle('cpdf_Justify', parent=styles['Normal'], alignment=4, leading=14) 

    Story = []
    
    if patient_persona and doc_metadata:
        fac_name = getattr(doc_metadata, 'facility_name', 'General Hospital')
        prov_name = getattr(doc_metadata, 'provider_name', 'Unknown Provider')
        svc_date = getattr(doc_metadata, 'service_date', datetime.now().strftime("%Y-%m-%d"))
        acc_num = getattr(doc_metadata, 'accession_number', f"ACC-{patient_id}-000")
        
        p_name = f"{patient_persona.first_name} {patient_persona.last_name}"
        p_dob = patient_persona.dob
        
        p_mrn = f"MRN-{patient_id}-{svc_date[:4]}"
        
        header_left = [
            Paragraph(f"<b>{fac_name}</b>", styles['Heading3']),
            Paragraph(f"123 Medical Center Dr, Suite 100", style_sub),
            Paragraph(f"City, State, 12345", style_sub),
            Spacer(1, 4),
            Paragraph(f"<b>Ordering Provider:</b><br/>{prov_name}", style_sub),
            Paragraph(f"<b>NPI:</b> {getattr(patient_persona.provider, 'formatted_npi', 'N/A')}", style_sub)
        ]
        
        header_right = [
            Paragraph(f"<b>PATIENT: {p_name.upper()}</b>", style_sub_right),
            Paragraph(f"MRN: {p_mrn} | DOB: {p_dob}", style_sub_right),
            Paragraph(f"GENDER: {patient_persona.gender.upper()}", style_sub_right),
            Spacer(1, 4),
            Paragraph(f"<b>SERVICE DATE: {svc_date}</b>", style_sub_right),
            Paragraph(f"ACCESSION #: {acc_num}", style_sub_right)
        ]
        
        header_table = Table([[header_left, header_right]], colWidths=[3.5*inch, 3.5*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor("#bdc3c7")),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ]))
        Story.append(header_table)
        Story.append(Spacer(1, 20))
        
        clean_title = doc_type.replace('_', ' ').upper()
        if hasattr(doc_metadata, 'title_hint'):
            clean_title = doc_metadata.title_hint.replace('_', ' ').upper()
            
        Story.append(Paragraph(f"{clean_title}", style_tit))
        Story.append(Spacer(1, 20))
        
    else:
        title_str = doc_type.replace('_', ' ').upper()
        Story.append(Paragraph(f"CLINICAL DOCUMENT: {title_str}", styles['Heading1']))
        Story.append(Spacer(1, 20))
    
    if image_path and os.path.exists(image_path):
        Story.append(Paragraph("<b>Attached Clinical Imaging:</b>", styles["Heading3"]))
        Story.append(Spacer(1, 5))
        img = Image(image_path, width=4*inch, height=3*inch, kind='proportional')
        Story.append(img)
        Story.append(Spacer(1, 15))

    if not patient_persona:
        Story.append(Paragraph(f"<b>REPORT CONTENT:</b>", styles["Heading3"]))
        Story.append(Spacer(1, 10))
    
    formatted_content = format_clinical_text(content)
    
    formatted_content = formatted_content.replace('\n', '<br/>')
    
    try:
        Story.append(Paragraph(formatted_content, style_normal))
    except ValueError as e:
        import html
        safe_content = html.escape(content).replace('\n', '<br/>')
        Story.append(Paragraph(safe_content, style_normal))
        print(f"   ⚠️ PDF Format Warning: Used plain text fallback due to: {e}")
    
    Story.append(Spacer(1, 12))
            
    doc.build(Story)
    return file_path

def get_clinical_image(doc_title: str):
    return None

def create_annotator_summary_pdf(patient_id: str, annotator_summary, case_details: dict, patient_persona=None, output_folder: str = None, version: int = 1):
    if output_folder is None:
        output_folder = os.path.join("generated_output", "summary")

    os.makedirs(output_folder, exist_ok=True)

    output_path = os.path.join(output_folder, f"Clinical_Summary_Patient_{patient_id}-v{version}.pdf")
    file_path = output_path
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"      🔄 Replaced existing summary")
        except Exception as e:
            print(f"      ⚠️  Could not remove old summary: {e}")
    
    doc = SimpleDocTemplate(file_path, pagesize=letter,
                            rightMargin=50, leftMargin=50,
                            topMargin=50, bottomMargin=50)

    styles = getSampleStyleSheet()
    
    col_primary = colors.HexColor('#2c3e50')
    col_secondary = colors.HexColor('#e74c3c')
    col_success = colors.HexColor('#27ae60')
    col_warning = colors.HexColor('#f39c12')
    col_light_bg = colors.HexColor('#ecf0f1')
    
    style_title = ParagraphStyle('ann_MainTitle', parent=styles['Heading1'], 
                                textColor=col_primary, fontSize=20, alignment=1,
                                spaceAfter=10, spaceBefore=0)
    
    style_subtitle = ParagraphStyle('ann_SubTitle', parent=styles['Normal'],
                                   textColor=col_secondary, fontSize=12, alignment=1,
                                   fontName='Helvetica-Bold', spaceAfter=20)
    
    style_h2 = ParagraphStyle('ann_SecTitle', parent=styles['Heading2'], 
                             textColor=col_primary, backColor=col_light_bg,
                             borderPadding=8, borderLeftWidth=4, borderColor=col_secondary,
                             spaceBefore=15, spaceAfter=10)
    
    style_h3 = ParagraphStyle('ann_SubSecTitle', parent=styles['Heading3'],
                             textColor=col_secondary, spaceBefore=10, spaceAfter=5)
    
    style_normal = ParagraphStyle('ann_Body', parent=styles['Normal'], 
                                 leading=14, fontSize=10, spaceAfter=6)
    
    style_bullet = ParagraphStyle('ann_Bullet', parent=style_normal, 
                                 leftIndent=20, bulletIndent=10)
    
    Story = []

    Story.append(Paragraph("ANNOTATOR VERIFICATION GUIDE", style_title))
    Story.append(Paragraph(f"Patient ID: {patient_id} | For Internal QA Use Only", style_subtitle))
    Story.append(Spacer(1, 10))
    
    import re
    
    target_cpt = "N/A"
    target_cpt_desc = "N/A"
    all_cpt_codes = []
    all_icd_codes = []
    
    case_text = annotator_summary.case_explanation
    
    target_match = re.search(r'Target Procedure:\s*CPT\s*(\d+)\s*[-–]\s*([^\n]+)', case_text, re.IGNORECASE)
    if target_match:
        target_cpt = target_match.group(1).strip()
        target_cpt_desc = target_match.group(2).strip()
    
    cpt_matches = re.findall(r'CPT\s*(\d+)\s*[-–:]\s*([^\n,;]+)', case_text, re.IGNORECASE)
    for code, desc in cpt_matches:
        code_entry = f"{code.strip()} - {desc.strip()}"
        if code_entry not in all_cpt_codes:
            all_cpt_codes.append(code_entry)
    
    icd_matches = re.findall(r'ICD[-\s]*10?\s*:?\s*([A-Z]\d{2}(?:\.\d{1,2})?)\s*[-–:]\s*([^\n,;]+)', case_text, re.IGNORECASE)
    for code, desc in icd_matches:
        code_entry = f"{code.strip()} - {desc.strip()}"
        if code_entry not in all_icd_codes:
            all_icd_codes.append(code_entry)
    
    medical_text = annotator_summary.medical_details
    
    icd_matches_2 = re.findall(r'ICD[-\s]*10?\s*:?\s*([A-Z]\d{2}(?:\.\d{1,2})?)\s*[-–:]\s*([^\n,;]+)', medical_text, re.IGNORECASE)
    for code, desc in icd_matches_2:
        code_entry = f"{code.strip()} - {desc.strip()}"
        if code_entry not in all_icd_codes:
            all_icd_codes.append(code_entry)
    
    if patient_persona and (not all_cpt_codes or not all_icd_codes):
        if hasattr(patient_persona, 'bio_narrative') and patient_persona.bio_narrative:
            bio_text = patient_persona.bio_narrative
            
            bio_cpt_matches = re.findall(r'CPT\s*(\d+)\s*[-–:]\s*([^\n,;]+)', bio_text, re.IGNORECASE)
            for code, desc in bio_cpt_matches:
                code_entry = f"{code.strip()} - {desc.strip()}"
                if code_entry not in all_cpt_codes:
                    all_cpt_codes.append(code_entry)
            
            bio_icd_matches = re.findall(r'ICD[-\s]*10?\s*:?\s*([A-Z]\d{2}(?:\.\d{1,2})?)\s*[-–:]\s*([^\n,;]+)', bio_text, re.IGNORECASE)
            for code, desc in bio_icd_matches:
                code_entry = f"{code.strip()} - {desc.strip()}"
                if code_entry not in all_icd_codes:
                    all_icd_codes.append(code_entry)
    
    case_overview_data = [
        [Paragraph("<b>Expected Outcome:</b>", style_normal), 
         Paragraph(f"<b>{annotator_summary.verification_pointers.expected_outcome}</b>", 
                  ParagraphStyle('ann_outcome', parent=style_normal, 
                                textColor=col_success if 'approval' in annotator_summary.verification_pointers.expected_outcome.lower() else col_warning))]
    ]
    
    if hasattr(annotator_summary.verification_pointers, 'notes') and annotator_summary.verification_pointers.notes:
        notes_text = "<br/>".join([f"• {note}" for note in annotator_summary.verification_pointers.notes])
        case_overview_data.append([
            Paragraph("<b>Verification Notes:</b>", style_normal),
            Paragraph(notes_text, style_normal)
        ])
    
    case_table = Table(case_overview_data, colWidths=[2*inch, 4.5*inch])
    case_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), col_light_bg),
        ('GRID', (0,0), (-1,-1), 1, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    Story.append(case_table)
    Story.append(Spacer(1, 15))
    
    pa_request = getattr(patient_persona, 'pa_request', None)
    procedure_facility = getattr(patient_persona, 'procedure_facility', None)
    expected_procedure_date = getattr(patient_persona, 'expected_procedure_date', None)
    procedure_requested = getattr(patient_persona, 'procedure_requested', None)
    
    if pa_request and procedure_facility and expected_procedure_date:
        Story.append(Paragraph("II. PRIOR AUTHORIZATION REQUEST", style_h2))
        Story.append(Spacer(1, 10))
        
        proc_info_text = f"""
        <b>Requested Procedure:</b> {procedure_requested or 'N/A'}<br/>
        <b>Expected Procedure Date:</b> {expected_procedure_date}<br/>
        <br/>
        <b>Procedure Facility:</b><br/>
        {procedure_facility.facility_name}<br/>
        {procedure_facility.department}<br/>
        {procedure_facility.street_address}<br/>
        {procedure_facility.city}, {procedure_facility.state} {procedure_facility.zip_code}
        """
        
        proc_box = Paragraph(proc_info_text, style_normal)
        proc_table = Table([[proc_box]], colWidths=[6.5*inch])
        proc_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#e8f4f8")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#3498db")),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ]))
        Story.append(proc_table)
        Story.append(Spacer(1, 15))
        
        prev_treats = getattr(pa_request, 'previous_treatments', 'None')
        if isinstance(prev_treats, list):
            prev_treats = "<br/>".join(prev_treats)
        if len(prev_treats) > 1000:
            prev_treats = prev_treats[:997] + "..."

        exp_outs = getattr(pa_request, 'expected_outcome', 'N/A')
        if isinstance(exp_outs, list):
            exp_outs = "<br/>".join(exp_outs)
        if len(exp_outs) > 1000:
             exp_outs = exp_outs[:997] + "..."

        pa_data = [
            [Paragraph("<b>PRIOR AUTHORIZATION DETAILS</b>", style_h3), ""], # Changed style_label to style_h3
            ["Requesting Provider:", Paragraph(getattr(pa_request, 'requesting_provider', 'N/A'), style_normal)],
            ["Urgency Level:", Paragraph(getattr(pa_request, 'urgency_level', 'N/A'), style_normal)],
            ["Clinical Justification:", Paragraph(getattr(pa_request, 'clinical_justification', 'N/A')[:1000], style_normal)],
            ["Supporting Diagnoses:", Paragraph("<br/>".join(getattr(pa_request, 'supporting_diagnoses', ['N/A'])), style_normal)],
            ["Previous Treatments:", Paragraph(prev_treats, style_normal)],
            ["Expected Outcome:", Paragraph(exp_outs, style_normal)],
        ]
        
        pa_table = Table(pa_data, colWidths=[2*inch, 4.5*inch])
        pa_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#fff3cd")),
            ('GRID', (0,0), (-1,-1), 1, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('WORDWRAP', (0,0), (-1,-1), True),
        ]))
        Story.append(pa_table)
        Story.append(Spacer(1, 20))
        
    Story.append(Paragraph("1. Case Explanation", style_h2))
    Story.append(Spacer(1, 5))
    
    case_exp_text = annotator_summary.case_explanation.replace('\n', '<br/>')
    Story.append(Paragraph(case_exp_text, style_normal))
    Story.append(Spacer(1, 10))
    
    Story.append(Paragraph("2. Medical Details (Persona-Specific)", style_h2))
    Story.append(Spacer(1, 5))
    
    medical_details_text = annotator_summary.medical_details.replace('\n', '<br/>')
    Story.append(Paragraph(medical_details_text, style_normal))
    Story.append(Spacer(1, 10))
    
    Story.append(Paragraph("3. Patient Profile Summary", style_h2))
    Story.append(Spacer(1, 5))
    
    profile_text = annotator_summary.patient_profile_summary.replace('\n', '<br/>')
    Story.append(Paragraph(profile_text, style_normal))
    Story.append(Spacer(1, 10))
    
    Story.append(Paragraph("4. Verification Checklist", style_h2))
    Story.append(Spacer(1, 5))
    
    vp = annotator_summary.verification_pointers
    
    if vp.key_verification_items:
        Story.append(Paragraph("<b>Key Verification Items:</b>", style_h3))
        for item in vp.key_verification_items:
            Story.append(Paragraph(f"☐ {item}", style_bullet))
        Story.append(Spacer(1, 8))
    
    if vp.supporting_evidence_checklist:
        Story.append(Paragraph("<b>Supporting Evidence Checklist:</b>", style_h3))
        for evidence in vp.supporting_evidence_checklist:
            Story.append(Paragraph(f"✓ {evidence}", style_bullet))
        Story.append(Spacer(1, 8))
    
    if vp.red_flags and len(vp.red_flags) > 0:
        Story.append(Paragraph("<b>Red Flags to Watch For:</b>", style_h3))
        for flag in vp.red_flags:
            Story.append(Paragraph(f"⚠ {flag}", 
                                 ParagraphStyle('ann_redflag', parent=style_bullet, textColor=col_warning)))
        Story.append(Spacer(1, 8))
    
    if vp.document_references and len(vp.document_references) > 0:
        Story.append(Paragraph("<b>Document References:</b>", style_h3))
        Story.append(Spacer(1, 5))
        
        doc_ref_data = [['Document', 'Should Contain']]
        for ref in vp.document_references:
            doc_name = ref.get('document', 'N/A')
            should_contain = ref.get('should_contain', 'N/A')
            doc_ref_data.append([
                Paragraph(doc_name, style_normal),
                Paragraph(should_contain, style_normal)
            ])
        
        if len(doc_ref_data) > 1:
            doc_ref_table = Table(doc_ref_data, colWidths=[2*inch, 4.5*inch])
            doc_ref_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('WORDWRAP', (0,0), (-1,-1), True),
            ]))
            Story.append(doc_ref_table)
    
    Story.append(Spacer(1, 15))
    
    footer_text = f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | This document is for internal QA purposes only</i>"
    Story.append(Paragraph(footer_text, 
                          ParagraphStyle('ann_footer', parent=style_normal, 
                                        fontSize=8, textColor=colors.grey, alignment=1)))

    doc.build(Story)
    return file_path

def create_patient_summary_pdf(patient_id, summary_data, output_folder: str = None):
    """
    Creates a highly styled Clinical Summary PDF using the template structure.
    """
    import json
    
    # Load template
    template_path = os.path.join(os.path.dirname(__file__), "templates", "summary_template.json")
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template = json.load(f)
    except Exception as e:
        print(f"   ⚠️  Warning: Could not load summary template: {e}. Using defaults.")
        template = {"sections": [], "styling": {}}
    
    # 1. Folder Management
    if output_folder:
        output_dir = output_folder
    else:
        output_dir = f"documents/{patient_id}"
        
    _ensure_folder(output_dir)

    filename = f"Clinical_Summary_Patient_{patient_id}.pdf"
    file_path = os.path.join(output_dir, filename)
    
    doc = SimpleDocTemplate(file_path, pagesize=letter,
                            rightMargin=50, leftMargin=50,
                            topMargin=50, bottomMargin=50)

    # Styles
    styles = getSampleStyleSheet()
    
    # Get colors from template or use defaults
    styling = template.get('styling', {})
    col_primary = colors.HexColor(styling.get('primary_color', '#27ae60'))
    col_secondary = colors.HexColor(styling.get('secondary_color', '#2980b9'))
    col_accent = colors.HexColor(styling.get('accent_color', '#34495e'))
    col_light_blue = colors.HexColor("#f0f7fb")
    
    # Custom Styles
    style_title = ParagraphStyle('summ_MainTitle', parent=styles['Heading1'], textColor=col_primary, 
                               borderPadding=10, borderWidth=0, borderBottomWidth=2, borderColor=col_primary)
    
    style_h2 = ParagraphStyle('summ_SecTitle', parent=styles['Heading2'], textColor=col_secondary, backColor=col_light_blue,
                              borderPadding=8, borderWidth=0, borderLeftWidth=4, borderColor=col_secondary, spaceBefore=20)
    
    style_normal = ParagraphStyle('summ_Normal', parent=styles['Normal'])

    Story = []
    
    # Title
    title = template.get('title', 'Patient Clinical Summary')
    Story.append(Paragraph(title, style_title))
    Story.append(Spacer(1, 20))
    
    # Process sections dynamically based on template
    sections = template.get('sections', [])
    
    for section_name in sections:
        if section_name == 'patient_details':
            # Patient Details Section
            patient_details = template.get('patient_details', {})
            # Merge with actual data
            name = summary_data.get('name', patient_details.get('name', 'Unknown'))
            dob = summary_data.get('dob', patient_details.get('dob', 'N/A'))
            gender = summary_data.get('gender', patient_details.get('gender', 'N/A'))
            mrn = summary_data.get('mrn', patient_details.get('mrn', 'N/A'))
            
            Story.append(Paragraph("<b>Patient Details</b>", style_h2))
            Story.append(Spacer(1, 10))
            
            details_text = f"""
            <b>Name:</b> {name}<br/>
            <b>Date of Birth:</b> {dob}<br/>
            <b>Gender:</b> {gender}<br/>
            <b>MRN:</b> {mrn}
            """
            Story.append(Paragraph(details_text, style_normal))
            Story.append(Spacer(1, 10))
            
        elif section_name == 'diagnoses':
            # Diagnoses Table
            Story.append(Paragraph("Current Diagnoses", style_h2))
            Story.append(Spacer(1, 10))
            
            diag_template = template.get('diagnoses', {})
            columns = diag_template.get('columns', ['code', 'condition', 'status', 'date_recorded'])
            
            # Build table headers
            headers = [col.replace('_', ' ').title() for col in columns]
            table_data = [headers]
            
            # Get data from summary_data or template
            diagnoses = summary_data.get('diagnoses', diag_template.get('data', []))
            for diag in diagnoses:
                row = []
                for col in columns:
                    cell_text = str(diag.get(col, 'N/A'))
                    # Wrap in Paragraph for text wrapping
                    row.append(Paragraph(cell_text, style_normal))
                table_data.append(row)
            
            if len(table_data) > 1:
                t_diag = Table(table_data, colWidths=[0.8*inch, 3.5*inch, 1*inch, 1.2*inch])
                t_diag.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f2f2f2")),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0,0), (-1,0), 8),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('WORDWRAP', (0,0), (-1,-1), True),
                ]))
                Story.append(t_diag)
                Story.append(Spacer(1, 10))
            
        elif section_name == 'encounters_documentation':
            # Encounters & Documentation
            Story.append(Paragraph("Clinical Encounters & Documentation", style_h2))
            Story.append(Spacer(1, 10))
            
            encounters = template.get('encounters_documentation', {})
            narrative = encounters.get('narrative_summary', '')
            if narrative:
                Story.append(Paragraph(narrative, style_normal))
                Story.append(Spacer(1, 10))
            
            # Key findings table
            key_findings = encounters.get('key_findings', [])
            if key_findings:
                Story.append(Paragraph("<b>Key Findings:</b>", style_normal))
                Story.append(Spacer(1, 5))
                
                findings_data = [['Test', 'Date', 'Result']]
                for finding in key_findings:
                    row = [
                        Paragraph(str(finding.get('test', 'N/A')), style_normal),
                        Paragraph(str(finding.get('date', 'N/A')), style_normal),
                        Paragraph(str(finding.get('result', 'N/A')), style_normal)
                    ]
                    findings_data.append(row)
                
                t_findings = Table(findings_data, colWidths=[1.2*inch, 1*inch, 4.3*inch])
                t_findings.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f2f2f2")),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ('WORDWRAP', (0,0), (-1,-1), True),
                ]))
                Story.append(t_findings)
                Story.append(Spacer(1, 10))
        
        elif section_name == 'contact_provider':
            # Contact & Provider Information
            Story.append(Paragraph("Contact & Provider Information", style_h2))
            Story.append(Spacer(1, 10))
            
            contact_info = template.get('contact_provider', {})
            provider_text = f"""
            <b>Provider:</b> {contact_info.get('provider', 'N/A')}<br/>
            <b>Facility:</b> {contact_info.get('facility', 'N/A')}<br/>
            <b>Address:</b> {contact_info.get('address', 'N/A')}<br/>
            <b>Phone:</b> {contact_info.get('phone', 'N/A')}
            """
            Story.append(Paragraph(provider_text, style_normal))
            Story.append(Spacer(1, 10))
            
        elif section_name == 'treatment_plan':
            # Treatment Plan
            Story.append(Paragraph("Proposed Treatment Plan", style_h2))
            Story.append(Spacer(1, 10))
            
            treatment = template.get('treatment_plan', {})
            procedure = summary_data.get('procedure', treatment.get('procedure', 'N/A'))
            outcome = summary_data.get('outcome', treatment.get('outcome', 'N/A'))
            
            plan_text = f"""
            <b>Procedure:</b> {procedure}<br/>
            <b>Outcome:</b> {outcome}
            """
            Story.append(Paragraph(plan_text, style_normal))
            Story.append(Spacer(1, 10))
            
        elif section_name == 'clinical_rationale':
            # Clinical Rationale (NEW SECTION)
            Story.append(Paragraph("Clinical Rationale", style_h2))
            Story.append(Spacer(1, 10))
            
            rationale = template.get('clinical_rationale', {})
            justification = rationale.get('justification_text', '')
            if justification:
                Story.append(Paragraph(justification, style_normal))
                Story.append(Spacer(1, 10))
            
            # Bullet points for clinical necessity
            necessity_points = rationale.get('clinical_necessity_points', [])
            if necessity_points:
                Story.append(Paragraph("<b>Clinical Necessity:</b>", style_normal))
                for point in necessity_points:
                    Story.append(Paragraph(f"• {point}", ParagraphStyle('ann_bullet', leftIndent=20, parent=style_normal)))
                Story.append(Spacer(1, 10))

    doc.build(Story)
    return file_path

def create_persona_pdf(patient_id: str, patient_name: str, persona: object, generated_reports: list = None, image_map: dict = None, mrn: str = "N/A", output_folder: str = "documents/personas", version: int = 1):
    """
    Generates a comprehensive Patient Master Record from Structured Data.
    - **Header**: Official Record Title.
    - **Face Sheet**: Structured Table (Identity, Contacts, Provider).
    - **Bio Narrative**: The Markdown story.
    - **Clinical Assets**: Reports & Images.
    """
    persona_folder = output_folder
    os.makedirs(output_folder, exist_ok=True)
    safe_name = patient_name.replace(' ', '_').replace('/', '-')
    filename = f"{patient_id}-{safe_name}-persona-v{version}.pdf"
    file_path = os.path.join(persona_folder, filename)

    doc = SimpleDocTemplate(file_path, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Premium Colors
    col_header = colors.HexColor("#2c3e50") # Dark Blue
    col_accent = colors.HexColor("#e67e22") # Orange
    col_bg = colors.HexColor("#ecf0f1")
    
    style_tit = ParagraphStyle('persona_MainTitle', parent=styles['Heading1'], textColor=col_header, 
                               alignment=1, fontSize=24, spaceAfter=20)
    
    style_h2 = ParagraphStyle('persona_SecTitle', parent=styles['Heading2'], textColor=col_header, backColor=col_bg,
                              borderPadding=6, spaceBefore=15, spaceAfter=10)
    
    style_h3 = ParagraphStyle('persona_SubTitle', parent=styles['Heading3'], textColor=col_accent, spaceBefore=10)
    
    style_normal = ParagraphStyle('persona_Body', parent=styles['Normal'], leading=14, fontSize=10)
    style_label = ParagraphStyle('persona_Lbl', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10)
    
    Story = []

    # --- HEADER ---
    Story.append(Paragraph(f"CONFIDENTIAL PATIENT MASTER RECORD", style_tit))
    Story.append(Paragraph(f"<b>PATIENT ID: {patient_id}  |  MRN: {mrn}</b>", ParagraphStyle('persona_pid', parent=style_normal, alignment=1, fontSize=12)))
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
            ["NPI:", getattr(pr, 'formatted_npi', 'N/A')],
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
            ["Member ID:", getattr(payer, 'member_id', 'N/A')],
            ["Policy Number:", getattr(payer, 'policy_number', 'N/A')],
            ["Effective Date:", getattr(payer, 'effective_date', 'N/A')],
            ["Termination Date:", getattr(payer, 'termination_date', 'ongoing')],
            ["Copay:", getattr(payer, 'copay_amount', 'N/A')],
            ["Deductible:", getattr(payer, 'deductible_amount', 'N/A')],
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
    Story.append(Spacer(1, 20))
    
    # --- PRIOR AUTHORIZATION REQUEST FORM (NEW) ---
    pa_request = getattr(p, 'pa_request', None)
    procedure_facility = getattr(p, 'procedure_facility', None)
    expected_procedure_date = getattr(p, 'expected_procedure_date', None)
    procedure_requested = getattr(p, 'procedure_requested', None)
    
    section_number = 2  # Start at II
    
    if pa_request and procedure_facility and expected_procedure_date:
        Story.append(Paragraph(f"II. PRIOR AUTHORIZATION REQUEST", style_h2))
        Story.append(Spacer(1, 10))
        
        # Procedure Information Box
        proc_info_text = f"""
        <b>Requested Procedure:</b> {procedure_requested or 'N/A'}<br/>
        <b>Expected Procedure Date:</b> {expected_procedure_date}<br/>
        <br/>
        <b>Procedure Facility:</b><br/>
        {procedure_facility.facility_name}<br/>
        {procedure_facility.department}<br/>
        {procedure_facility.street_address}<br/>
        {procedure_facility.city}, {procedure_facility.state} {procedure_facility.zip_code}
        """
        
        proc_box = Paragraph(proc_info_text, style_normal)
        proc_table = Table([[proc_box]], colWidths=[6.5*inch])
        proc_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#e8f4f8")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#3498db")),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ]))
        Story.append(proc_table)
        Story.append(Spacer(1, 15))
        
        # PA Request Details
        pa_data = [
            [Paragraph("<b>AUTHORIZATION DETAILS</b>", style_h3), ""],
            ["Requesting Provider:", getattr(pa_request, 'requesting_provider', 'N/A')],
            ["Urgency Level:", getattr(pa_request, 'urgency_level', 'N/A')],
            ["Clinical Justification:", Paragraph(getattr(pa_request, 'clinical_justification', 'N/A'), style_normal)],
            ["Supporting Diagnoses:", Paragraph("<br/>".join(getattr(pa_request, 'supporting_diagnoses', ['N/A'])), style_normal)],
            ["Previous Treatments:", Paragraph(getattr(pa_request, 'previous_treatments', 'None'), style_normal)],
            ["Expected Outcome:", Paragraph(getattr(pa_request, 'expected_outcome', 'N/A'), style_normal)],
        ]
        
        pa_table = Table(pa_data, colWidths=[2*inch, 4.5*inch])
        pa_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#fff3cd")),
            ('GRID', (0,0), (-1,-1), 1, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ]))
        Story.append(pa_table)
        Story.append(Spacer(1, 20))
        section_number = 3  # Next section will be III
    
    # --- CLINICAL HISTORY & MEDICATIONS (NEW SECTIONS) ---
    medications_list = getattr(p, 'medications', [])
    allergies_list = getattr(p, 'allergies', [])
    vaccinations_list = getattr(p, 'vaccinations', [])
    therapies_list = getattr(p, 'therapies', [])
    
    if medications_list or allergies_list or vaccinations_list or therapies_list:
        section_roman = ["I", "II", "III", "IV", "V", "VI"][section_number - 1]
        Story.append(Paragraph(f"{section_roman}. CLINICAL HISTORY & ACTIVE CARE", style_h2))
        Story.append(Spacer(1, 10))
        section_number += 1
        
        # 1. Medications
        if medications_list:
            Story.append(Paragraph("<b>Current & Past Medications</b>", style_h3))
            Story.append(Spacer(1, 5))
            med_data = [["Medication / Generic", "Qty", "Prescriber", "Status & Dates", "Reason"]]
            for m in medications_list:
                brand = getattr(m, 'brand', '')
                m_name = brand.strip() if brand and brand.strip() else getattr(m, 'generic_name', '')
                if brand and getattr(m, 'generic_name', ''): 
                    m_name = f"{brand} ({m.generic_name})"
                dates = f"{m.start_date} to {m.end_date}"
                med_data.append([
                    Paragraph(m_name, style_normal),
                    Paragraph(m.qty or "N/A", style_normal),
                    Paragraph(m.prescribed_by or "N/A", style_normal),
                    Paragraph(f"{m.status}<br/>{dates}", style_normal),
                    Paragraph(m.reason or "N/A", style_normal)
                ])
            t = Table(med_data, colWidths=[1.8*inch, 0.6*inch, 1.2*inch, 1.3*inch, 1.5*inch])
            t.setStyle(table_style)
            Story.append(t)
            Story.append(Spacer(1, 10))
            
        # 2. Allergies
        if allergies_list:
            Story.append(Paragraph("<b>Allergies & Adverse Reactions</b>", style_h3))
            Story.append(Spacer(1, 5))
            alg_data = [["Allergen & Type", "Reaction", "Severity", "Onset Date"]]
            for a in allergies_list:
                alg_data.append([
                    Paragraph(f"<b>{getattr(a, 'allergen', '')}</b><br/>{getattr(a, 'allergy_type', '')}", style_normal),
                    Paragraph(getattr(a, 'reaction', '') or "N/A", style_normal),
                    Paragraph(getattr(a, 'severity', '') or "N/A", style_normal),
                    Paragraph(getattr(a, 'onset_date', '') or "N/A", style_normal)
                ])
            t = Table(alg_data, colWidths=[2.0*inch, 2.0*inch, 1.2*inch, 1.2*inch])
            t.setStyle(table_style)
            Story.append(t)
            Story.append(Spacer(1, 10))
            
        # 3. Vaccinations
        if vaccinations_list:
            Story.append(Paragraph("<b>Immunization Record</b>", style_h3))
            Story.append(Spacer(1, 5))
            vax_data = [["Vaccine & Type", "Date", "Provider / Dose", "Reason"]]
            for v in vaccinations_list:
                vax_data.append([
                    Paragraph(f"<b>{v.vaccine_name}</b><br/>{v.vaccine_type}", style_normal),
                    Paragraph(v.date_administered or "N/A", style_normal),
                    Paragraph(f"{v.administered_by or 'N/A'}<br/>Dose: {v.dose_number}", style_normal),
                    Paragraph(v.reason or "N/A", style_normal)
                ])
            t = Table(vax_data, colWidths=[2.0*inch, 1.0*inch, 1.5*inch, 1.9*inch])
            t.setStyle(table_style)
            Story.append(t)
            Story.append(Spacer(1, 10))

        # 4. Therapies (expanded — CPT codes + ICD-10)
        if therapies_list:
            Story.append(Paragraph("<b>Therapy &amp; Behavioral Health</b>", style_h3))
            Story.append(Spacer(1, 5))
            th_data = [["Type", "CPT Code", "Provider / Facility", "Frequency / Status", "ICD-10 Diagnoses"]]
            for th in therapies_list:
                provider = getattr(th, 'provider', '') or ''
                facility = getattr(th, 'facility', '') or ''
                cpt_code = getattr(th, 'cpt_code', 'N/A') or 'N/A'
                cpt_desc = getattr(th, 'cpt_description', '') or ''
                icd_codes = getattr(th, 'icd10_codes', []) or []
                icd_str = '<br/>'.join(icd_codes[:3]) if icd_codes else 'N/A'
                th_data.append([
                    Paragraph(f"<b>{getattr(th, 'therapy_type', '')}</b><br/>{getattr(th, 'reason', '') or ''}", style_normal),
                    Paragraph(f"<b>{cpt_code}</b><br/><i>{cpt_desc}</i>", style_normal),
                    Paragraph(f"{provider}<br/>{facility}", style_normal),
                    Paragraph(f"{getattr(th, 'frequency', '') or ''}<br/>{getattr(th, 'status', '') or ''}", style_normal),
                    Paragraph(icd_str, style_normal)
                ])
            t = Table(th_data, colWidths=[1.4*inch, 1.2*inch, 1.5*inch, 1.0*inch, 1.3*inch])
            t.setStyle(table_style)
            Story.append(t)

            # Behavioral Notes
            beh_notes = getattr(p, 'behavioral_notes', None)
            if beh_notes:
                Story.append(Spacer(1, 5))
                Story.append(Paragraph("<b>Behavioral Context Notes:</b>", style_normal))
                Story.append(Spacer(1, 3))
                Story.append(Paragraph(beh_notes, style_normal))

            Story.append(Spacer(1, 10))

        # 5. Social History
        sh = getattr(p, 'social_history', None)
        if sh:
            Story.append(Paragraph("<b>Social &amp; Lifestyle History</b>", style_h3))
            Story.append(Spacer(1, 5))
            sh_data = [
                ["Tobacco Use", getattr(sh, 'tobacco_use', None) or "(not recorded)"],
                ["Tobacco Frequency", getattr(sh, 'tobacco_frequency', None) or "(not recorded)"],
                ["Alcohol Use", getattr(sh, 'alcohol_use', None) or "(not recorded)"],
                ["Alcohol Frequency", getattr(sh, 'alcohol_frequency', None) or "(not recorded)"],
                ["Illicit Drug Use", getattr(sh, 'illicit_drug_use', None) or "(not recorded)"],
                ["Exercise Habits", getattr(sh, 'exercise_habits', None) or "(not recorded)"],
                ["Diet Notes", getattr(sh, 'diet_notes', None) or "(not recorded)"],
                ["Last Medical Visit", getattr(sh, 'last_medical_visit', None) or "(not recorded)"],
                ["Last Visit Reason", getattr(sh, 'last_visit_reason', None) or "(not recorded)"],
                ["Mental Health History", getattr(sh, 'mental_health_history', None) or "(not recorded)"],
                ["Mental Health (Current)", getattr(sh, 'mental_health_current', None) or "(not recorded)"],
                ["Family History", getattr(sh, 'family_history_relevant', None) or "(not recorded)"],
            ]
            missed = getattr(sh, 'missed_appointment', None)
            if missed is True:
                sh_data.append(["Missed Appointment", f"YES — {getattr(sh, 'missed_appointment_reason', 'reason unknown') or 'reason unknown'}"])
            elif missed is False:
                sh_data.append(["Missed Appointment", "No"])
            early = getattr(sh, 'early_visit_reason', None)
            if early:
                sh_data.append(["Early Visit Reason", early])
            t = Table(sh_data, colWidths=[2.2*inch, 4.2*inch])
            t.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f4f8')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            Story.append(t)
            Story.append(Spacer(1, 10))

        # 6. Current Vital Signs
        vs = getattr(p, 'vital_signs_current', None)
        if vs:
            Story.append(Paragraph("<b>Current Vital Signs</b>", style_h3))
            Story.append(Spacer(1, 5))
            vs_data = [
                ["Recorded Date", getattr(vs, 'recorded_date', 'N/A') or 'N/A'],
                ["Blood Pressure", getattr(vs, 'blood_pressure', None) or "(not recorded)"],
                ["Heart Rate", getattr(vs, 'heart_rate', None) or "(not recorded)"],
                ["BMI", getattr(vs, 'bmi', None) or "(not recorded)"],
                ["O2 Saturation", getattr(vs, 'oxygen_saturation', None) or "(not recorded)"],
                ["Temperature", getattr(vs, 'temperature', None) or "(not recorded)"],
                ["Respiratory Rate", getattr(vs, 'respiratory_rate', None) or "(not recorded)"],
                ["Blood Sugar (Fasting)", getattr(vs, 'blood_sugar_fasting', None) or "(not recorded)"],
                ["Blood Sugar (Post-meal)", getattr(vs, 'blood_sugar_postprandial', None) or "(not recorded)"],
            ]
            t = Table(vs_data, colWidths=[2.2*inch, 4.2*inch])
            t.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f5e9')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            Story.append(t)
            Story.append(Spacer(1, 10))

        # 7. Gender-Specific History
        gsh = getattr(p, 'gender_specific_history', None)
        if gsh:
            Story.append(Paragraph("<b>Gender-Specific Medical History</b>", style_h3))
            Story.append(Spacer(1, 5))
            Story.append(Paragraph(gsh, style_normal))
            Story.append(Spacer(1, 10))
    
    # --- BIO NARRATIVE ---
    section_roman = ["I", "II", "III", "IV", "V", "VI"][section_number - 1]
    Story.append(Paragraph(f"{section_roman}. MEDICAL BIOGRAPHY & HISTORY", style_h2))
    
    if p.bio_narrative:
        for line in p.bio_narrative.split('\n'):
            line = line.strip()
            if not line: continue
            
            # Use our Regex Formatter!
            line = format_clinical_text(line)
            
            if line.startswith('<b><font size=12>'): # It was a header
                 Story.append(Paragraph(line, style_h3))
            elif line.startswith('• '):
                 Story.append(Paragraph(line, ParagraphStyle('persona_bull', parent=style_normal, leftIndent=15)))
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
            
            # Format markdown to styled text with graceful fallback
            rep_text = format_report_content(rep.content)
            
            try:
                Story.append(Paragraph(rep_text, style_normal))
            except ValueError:
                import html
                safe_text = html.escape(rep.content).replace('\n', '<br/>')
                Story.append(Paragraph(safe_text, style_normal))
            
            Story.append(Spacer(1, 15))
            Story.append(Spacer(1,6))
            Story.append(Table([[""]], colWidths=[6.4*inch], style=[
                ('LINEABOVE',(0,0),(-1,-1),0.5,colors.grey)
            ]))
            Story.append(Spacer(1,6))

    doc.build(Story)
    return file_path
