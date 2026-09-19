import sys; sys.path.insert(0, '.')
import pymupdf, re
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle

def sanitize_unicode(text: str) -> str:
    # Replace all unicode hyphens/dashes with standard ASCII '-'
    text = re.sub(r'[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]', '-', text)
    # Replace unicode quotation marks with standard ASCII quotes
    text = re.sub(r'[\u2018-\u201B\u2032]', "'", text)
    text = re.sub(r'[\u201C-\u201F\u2033]', '"', text)
    # Replace unicode spaces with standard space
    text = re.sub(r'[\u00A0\u2000-\u200B\u202F\u205F\u3000]', ' ', text)
    # Remove unicode bullets
    text = re.sub(r'[\u2022\u25CF\u25CB\u25AA\u25AB\u25A0\u25A1]', '', text)
    return text

def clean_latex_text(text: str) -> str:
    text = sanitize_unicode(text)
    t = text.replace(r'\%', '%').replace(r'\&', '&amp;').replace(r'\$', '$').replace(r'\_', '_').replace(r'\#', '#')
    t = t.replace(r'---', '—').replace(r'--', ' - ')
    t = t.replace(r'\textasciitilde', '~')
    t = re.sub(r'\\textbf\{([^}]+)\}', r'<b>\1</b>', t)
    t = re.sub(r'\\textit\{([^}]+)\}', r'<i>\1</i>', t)
    t = re.sub(r'\\underline\{([^}]+)\}', r'<u>\1</u>', t)
    t = re.sub(r'\\href\{[^}]+\}\{([^}]+)\}', r'<u>\1</u>', t)
    t = re.sub(r'\\fa[A-Za-z0-9]+\\?\s*', '', t)
    t = re.sub(r'\\(small|large|LARGE|normalsize|scshape|noindent|quad|qquad|hfill)\b\s*', '', t)
    t = re.sub(r'\\\\(\[[^\]]*\])?', '', t)
    t = re.sub(r'\\vspace\{[^}]+\}', '', t)
    t = t.replace('{', '').replace('}', '').strip()
    return t.rstrip('\\').strip()

def render_full_page_pdf(latex_source: str, font_scale: float = 1.0) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=24,
        rightMargin=24,
        topMargin=16,
        bottomMargin=16
    )
    styles = getSampleStyleSheet()

    fs_body = 8.5 * font_scale
    lh_body = 11.2 * font_scale

    title_style = ParagraphStyle(
        'RTitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=14.5 * font_scale, leading=17 * font_scale, alignment=1, textColor=colors.HexColor('#0f172a')
    )
    sub_style = ParagraphStyle(
        'RSub', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8.8 * font_scale, leading=11.5 * font_scale, alignment=1, textColor=colors.HexColor('#1e293b')
    )
    contact_style = ParagraphStyle(
        'RContact', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8.0 * font_scale, leading=10.8 * font_scale, alignment=1, textColor=colors.HexColor('#334155')
    )
    sec_style = ParagraphStyle(
        'RSec', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10.0 * font_scale, leading=12.5 * font_scale, textColor=colors.HexColor('#0f172a'),
        spaceBefore=4 * font_scale, spaceAfter=2 * font_scale
    )
    job_title_style = ParagraphStyle(
        'RJobTitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8.8 * font_scale, leading=11.0 * font_scale, textColor=colors.HexColor('#0f172a')
    )
    job_date_style = ParagraphStyle(
        'RJobDate', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8.2 * font_scale, leading=11.0 * font_scale, alignment=2, textColor=colors.HexColor('#475569')
    )
    job_sub_style = ParagraphStyle(
        'RJobSub', parent=styles['Normal'],
        fontName='Helvetica-Oblique', fontSize=8.2 * font_scale, leading=10.2 * font_scale, textColor=colors.HexColor('#475569')
    )
    bullet_style = ParagraphStyle(
        'RBullet', parent=styles['Normal'],
        fontName='Helvetica', fontSize=fs_body, leading=lh_body, leftIndent=10, firstLineIndent=-10,
        textColor=colors.HexColor('#1e293b'), spaceBefore=1.1 * font_scale, spaceAfter=1.1 * font_scale
    )
    skill_style = ParagraphStyle(
        'RSkill', parent=styles['Normal'],
        fontName='Helvetica', fontSize=fs_body, leading=lh_body, textColor=colors.HexColor('#1e293b'),
        spaceBefore=1.8 * font_scale, spaceAfter=1.8 * font_scale
    )

    story = []
    story.append(Paragraph('<b>ABHIJEET KUMAR</b> | 23HS10002', title_style))
    story.append(Spacer(1, 1))
    story.append(Paragraph('<b>B.S. (Hons.) in ECONOMICS</b> | <b>IIT Kharagpur</b> (CGPA: 8.03 / 10)', sub_style))
    story.append(Paragraph('Minor: Mathematics &amp; Computing | Micro Spl.: Artificial Intelligence and Applications', contact_style))
    story.append(Paragraph('+91 63989 85179 | kumarabhiitkgp@gmail.com | linkedin.com/in/abhijeetkgp | github.com/abhijeet6401', contact_style))
    story.append(Spacer(1, 2))
    story.append(HRFlowable(width='100%', thickness=0.8, color=colors.HexColor('#0f172a'), spaceBefore=1, spaceAfter=3))

    if r'\begin{document}' in latex_source:
        body = latex_source.split(r'\begin{document}')[1].split(r'\end{document}')[0]
    else:
        body = latex_source

    lines = body.splitlines()
    i = 0
    in_header_center = True

    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith('%'):
            i += 1
            continue

        if in_header_center:
            if line.startswith(r'\section'):
                in_header_center = False
            else:
                i += 1
                continue

        # Section Header
        sec_m = re.match(r'\\section\{([^}]+)\}', line)
        if sec_m:
            sec_title = clean_latex_text(sec_m.group(1)).upper()
            story.append(Spacer(1, 2 * font_scale))
            story.append(Paragraph(f'<b>{sec_title}</b>', sec_style))
            story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#94a3b8'), spaceBefore=1, spaceAfter=2.5 * font_scale))
            i += 1
            continue

        # \jobheader{Company}{Tagline}{Role | Location}{Dates}
        jh_m = re.match(r'\\jobheader\{([^}]+)\}\{([^}]+)\}\{([^}]+)\}\{([^}]+)\}', line)
        if jh_m:
            comp = clean_latex_text(jh_m.group(1))
            desc = clean_latex_text(jh_m.group(2))
            role_loc = clean_latex_text(jh_m.group(3))
            dates = clean_latex_text(jh_m.group(4))

            left_cell = Paragraph(f'<b>{comp}</b> | {role_loc}', job_title_style)
            right_cell = Paragraph(f'<b>{dates}</b>', job_date_style)
            tbl = Table([[left_cell, right_cell]], colWidths=[420, 127])
            tbl.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0.5),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(tbl)
            if desc:
                story.append(Paragraph(desc, job_sub_style))
            i += 1
            continue

        # Project / Role / Position Header: \textbf{...} \hfill \textbf{...}
        if line.startswith(r'\textbf{') and r'\hfill' in line:
            parts = line.split(r'\hfill')
            left_txt = clean_latex_text(parts[0])
            right_txt = clean_latex_text(parts[1]) if len(parts) > 1 else ''
            left_cell = Paragraph(f'<b>{left_txt}</b>', job_title_style)
            right_cell = Paragraph(f'<b>{right_txt}</b>', job_date_style)
            tbl = Table([[left_cell, right_cell]], colWidths=[425, 122])
            tbl.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0.5),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(tbl)
            i += 1
            continue

        # Subtitle or description in \textit{...}
        if line.startswith(r'\textit{'):
            desc = clean_latex_text(line)
            if desc:
                story.append(Paragraph(desc, job_sub_style))
            i += 1
            continue

        # Bullet point: \achieve{...}
        achieve_m = re.match(r'\\achieve\{(.+)', line)
        if achieve_m:
            bullet_raw = achieve_m.group(1)
            while not bullet_raw.rstrip().endswith('}') and i + 1 < len(lines):
                i += 1
                bullet_raw += ' ' + lines[i].strip()
            if bullet_raw.endswith('}'):
                bullet_raw = bullet_raw[:-1]
            bullet_txt = clean_latex_text(bullet_raw)
            if bullet_txt:
                story.append(Paragraph(f'• &nbsp; {bullet_txt}', bullet_style))
            i += 1
            continue

        # Bullet point: \item ...
        item_m = re.match(r'\\item\s+(.+)', line)
        if item_m:
            bullet_raw = item_m.group(1)
            while (bullet_raw.count('{') > bullet_raw.count('}') or not bullet_raw.endswith('.')) and i + 1 < len(lines) and not lines[i+1].strip().startswith(r'\item') and not lines[i+1].strip().startswith(r'\end') and not lines[i+1].strip().startswith(r'\section'):
                i += 1
                bullet_raw += ' ' + lines[i].strip()
            bullet_txt = clean_latex_text(bullet_raw)
            if bullet_txt:
                story.append(Paragraph(f'• &nbsp; {bullet_txt}', bullet_style))
            i += 1
            continue

        # Skills & Category text: \textbf{...:} ... or \noindent \textbf{...}
        if line.startswith(r'\textbf{') or line.startswith(r'\noindent'):
            clean_p = clean_latex_text(line)
            if clean_p:
                story.append(Paragraph(clean_p, skill_style))
            i += 1
            continue

        # Fallback for any other meaningful body content
        if not any(line.startswith(p) for p in [r'\begin', r'\end', r'\vspace', r'\\']):
            clean_p = clean_latex_text(line)
            if clean_p and len(clean_p) > 2:
                story.append(Paragraph(clean_p, skill_style))

        i += 1

    doc.build(story)
    return buffer.getvalue()

# Let's test product.tex enriched with Education, Certifications, AND Frost & Sullivan
with open('resumes/product.tex', 'r', encoding='utf-8') as f:
    base_tex = f.read()

edu_cert_block = '''
% ---------- Education & Certifications ----------
\\section{Education \\& Professional Certifications}
\\begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
  \\small
  \\item \\textbf{Indian Institute of Technology (IIT) Kharagpur (2023--2027):} 4YRS B.S. (Hons.) in Economics (\\textbf{CGPA: 8.03 / 10}) | Minor in Mathematics \\& Computing | Micro Specialization in AI \\& Applications.
  \\item \\textbf{Academic Excellence:} CBSE Class 12th: \\textbf{97.00\\%} (Bhartiyam International) | CBSE Class 10th: \\textbf{98.60\\%} (Jaycees Public School).
  \\item \\textbf{Chartered Financial Analyst (CFA) L1 Candidate (Feb 2027):} Derivatives, Quantitative Methods, Economics, Financial Reporting.
  \\item \\textbf{Bloomberg Market Concepts (BMC, Dec 2025):} Economic Indicators, Currencies, Fixed Income, Equities, Portfolio Management.
\\end{itemize}
'''

frost_block = '''
\\jobheader{Frost and Sullivan}{Delivered market research, pricing insights, and predictive demand models for enterprise clients}{Product Strategy \\& Analytics Intern | Mumbai}{May'25 -- Jun'25}
\\begin{achievelist}
  \\achieve{Analyzed \\$23M+ in multi-country consumer sales data by building interactive Power BI dashboards and automating CAGR tracking.}
  \\achieve{Estimated category revenue across 3 product lines, identifying 8.0\\% product returns and seasonal Q4 demand cycles.}
\\end{achievelist}
'''

enriched_tex = base_tex.replace('% ---------- Internships ----------', edu_cert_block + '\n% ---------- Internships ----------\n' + frost_block)

pdf_b = render_full_page_pdf(enriched_tex, font_scale=1.0)
doc = pymupdf.open(stream=pdf_b, filetype='pdf')
print('Page count:', len(doc))
page = doc[0]
blocks = page.get_text('blocks')
max_y1 = max(b[3] for b in blocks if b[4].strip())
print('Max y coordinate:', max_y1, 'out of', page.rect.height)
print('Percentage of page height filled:', (max_y1 / page.rect.height) * 100, '%')
print('Blank space remaining at bottom:', page.rect.height - max_y1, 'points')
