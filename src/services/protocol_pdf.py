import os
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, Spacer, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime

def render_protocol_pdf(path, protocol_number, kind, company, employee: dict, asset: dict, created_by, confirmed_at, note) -> str:
    # Create parent directories
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # Determine title based on kind
    if kind == 'handover':
        title = 'Předávací protokol'
    elif kind == 'return':
        title = 'Protokol o vrácení'
    else:
        title = 'Předávací protokol'
    
    # Try to register a Unicode font
    font_path = None
    for path_candidate in [
        '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
        '/Library/Fonts/Arial Unicode.ttf', 
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    ]:
        if os.path.exists(path_candidate):
            font_path = path_candidate
            break
    
    # Register the Unicode font so Czech diacritics render; Helvetica otherwise.
    font_name = 'Helvetica'
    if font_path:
        pdfmetrics.registerFont(TTFont('Unicode', font_path))
        font_name = 'Unicode'

    # Create document
    doc = SimpleDocTemplate(path, pagesize=A4)
    styles = getSampleStyleSheet()
    styles['Normal'].fontName = font_name
    styles['Heading1'].fontName = font_name
    
    # Create custom style for title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=font_name,
        fontSize=16,
        spaceAfter=12,
        alignment=0  # Left aligned
    )
    
    # Create content elements
    elements = []
    
    # Title
    title_para = Paragraph(title, title_style)
    elements.append(title_para)
    
    # Protocol number and company
    protocol_info = f"Číslo protokolu: {protocol_number}<br/>Společnost: {company}"
    protocol_para = Paragraph(protocol_info, styles['Normal'])
    elements.append(protocol_para)
    
    elements.append(Spacer(1, 12))
    
    # Asset table
    asset_data = [
        ['Položka', 'Hodnota'],
        ['Inventární číslo', asset.get('asset_tag', '')],
        ['Typ', asset.get('type', '')],
        ['Značka', asset.get('brand', '')],
        ['Model', asset.get('model', '')],
        ['Sériové číslo', asset.get('serial_number', '')]
    ]
    
    asset_table = Table(asset_data, colWidths=[2*inch, 3*inch])
    elements.append(asset_table)
    
    elements.append(Spacer(1, 12))
    
    # Employee table
    employee_data = [
        ['Položka', 'Hodnota'],
        ['Jméno', employee.get('display_name', '')],
        ['E-mail', employee.get('email', '')],
        ['Oddělení', employee.get('department', '')]
    ]
    
    employee_table = Table(employee_data, colWidths=[2*inch, 3*inch])
    elements.append(employee_table)
    
    elements.append(Spacer(1, 12))
    
    # Created by and confirmed at
    created_info = f"Vytvořil: {created_by}<br/>Potvrzeno: {confirmed_at}"
    created_para = Paragraph(created_info, styles['Normal'])
    elements.append(created_para)
    
    elements.append(Spacer(1, 12))
    
    # Note
    note_para = Paragraph(f"Poznámka: {note}", styles['Normal'])
    elements.append(note_para)
    
    elements.append(Spacer(1, 12))
    
    # Confirmation sentence
    confirmation_sentence = f"Zaměstnanec potvrdil elektronicky dne {confirmed_at}."
    confirmation_para = Paragraph(confirmation_sentence, styles['Normal'])
    elements.append(confirmation_para)
    
    # Build the document
    doc.build(elements)
    
    return path