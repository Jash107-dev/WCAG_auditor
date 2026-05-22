import io
from django.shortcuts import render
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from core.models import Page, Issue, Project
import html as html_module


def safe_para(text, style, max_len=None):
    """Escape HTML special chars so ReportLab's XML parser never chokes."""
    if max_len:
        text = text[:max_len]
    # Strip newlines for table cells
    text = text.replace('\n', ' ').replace('\r', '')
    # Escape <, >, & so unclosed tags don't crash the parser
    text = html_module.escape(text)
    return Paragraph(text, style)


def page_report(request, page_id):
    pg = Page.objects.get(id=page_id)
    pg_issues = Issue.objects.filter(page=pg).select_related("rule").order_by(
        # critical first, then by source (deterministic before llm)
        "source", "severity"
    )
    deterministic_count = pg_issues.filter(source="deterministic").count()
    llm_count = pg_issues.filter(source="llm").count()
    # Issues that were AI-enhanced (have llm_analysis) but are deterministic source
    ai_enhanced_count = pg_issues.filter(source="deterministic").exclude(llm_analysis__isnull=True).exclude(llm_analysis="").count()
    return render(request, "reporting/page_report.html", {
        "page": pg,
        "issues": pg_issues,
        "deterministic_count": deterministic_count,
        "llm_count": llm_count,
        "ai_enhanced_count": ai_enhanced_count,
    })


def ada_statement(request, project_id):
    proj = Project.objects.get(id=project_id)
    all_pages = proj.page_set.all()

    total_pages = all_pages.count()
    all_issues = Issue.objects.filter(page__project=proj)
    total_issues = all_issues.count()

    # A page is compliant only if it has NO critical issues
    # Serious/moderate/minor = partial compliance
    critical_page_ids = set(
        all_issues.filter(severity="critical")
        .values_list("page_id", flat=True).distinct()
    )
    non_compliant_pages_count = len(critical_page_ids)
    compliant_pages = total_pages - non_compliant_pages_count
    compliant_pages = max(0, compliant_pages)

    if total_pages > 0:
        percent = round((compliant_pages / total_pages) * 100, 2)
    else:
        percent = 0

    is_compliant = percent >= 80

    return render(request, "reporting/ada_statement.html", {
        "project": proj,
        "total_pages": total_pages,
        "compliant_pages": compliant_pages,
        "total_issues": total_issues,
        "percent_compliant": percent,
        "is_compliant": is_compliant,
    })


def export_pdf(request, project_id):
    proj = Project.objects.get(id=project_id)
    all_pages = proj.page_set.all()
    all_issues = Issue.objects.filter(page__project=proj).select_related("rule", "page")

    total_pages = all_pages.count()
    compliant_pages = all_pages.filter(status="pass").count()
    total_issues = all_issues.count()
    critical = all_issues.filter(severity="critical").count()
    serious = all_issues.filter(severity="serious").count()
    moderate = all_issues.filter(severity="moderate").count()
    minor = all_issues.filter(severity="minor").count()

    if total_pages > 0:
        percent = round((compliant_pages / total_pages) * 100, 2)
    else:
        percent = 0

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        rightMargin=0.75*inch, leftMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch)

    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle("mytitle", parent=styles["Title"], fontSize=20,
        textColor=colors.HexColor("#1a1f36"), spaceAfter=6)
    heading_style = ParagraphStyle("myheading", parent=styles["Heading2"], fontSize=13,
        textColor=colors.HexColor("#1a1f36"), spaceBefore=16, spaceAfter=6)
    normal_style = ParagraphStyle("mynormal", parent=styles["Normal"], fontSize=10,
        textColor=colors.HexColor("#4a5568"), spaceAfter=4)
    small_style = ParagraphStyle("mysmall", parent=styles["Normal"], fontSize=9,
        textColor=colors.HexColor("#8892b0"))

    story.append(Paragraph("WCAG Accessiblity Audit Report", title_style))
    story.append(Paragraph(html_module.escape("Domain: " + proj.domain), normal_style))
    story.append(Paragraph("WCAG Level: " + proj.wcag_level, normal_style))
    story.append(Paragraph("Status: " + proj.status, normal_style))
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph("Summary", heading_style))

    summ_data = [
        ["Metric", "Value"],
        ["Total Pages Scanned", str(total_pages)],
        ["Compliant Pages", str(compliant_pages)],
        ["Overall Compliance", str(percent) + "%"],
        ["Total Issues Found", str(total_issues)],
        ["Critical Issues", str(critical)],
        ["Serious Issues", str(serious)],
        ["Moderate Issues", str(moderate)],
        ["Minor Issues", str(minor)],
    ]

    summ_table = Table(summ_data, colWidths=[3*inch, 2*inch])
    summ_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1f36")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8f9fa"), colors.white]),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summ_table)
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph("ADA Compliance Statement", heading_style))
    if percent >= 80:
        ada_txt = "This site aligns with ADA accessiblity expectations based on WCAG " + proj.wcag_level + " checks."
    else:
        ada_txt = "This site is PARTIALLY compliant. " + str(total_issues) + " issues were found across " + str(total_pages) + " pages."
    story.append(Paragraph(ada_txt, normal_style))
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph("Issues Found", heading_style))

    issue_data = [["Page URL", "Rule", "Severity", "Message"]]
    for issue in all_issues[:100]:
        issue_data.append([
            safe_para(issue.page.url, small_style, max_len=60),
            issue.rule.wcag_id,
            issue.severity,
            safe_para(issue.message, small_style, max_len=120),
        ])

    if len(issue_data) > 1:
        issue_tbl = Table(issue_data, colWidths=[2*inch, 0.7*inch, 0.8*inch, 3*inch])
        issue_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1f36")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8f9fa"), colors.white]),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(issue_tbl)
    else:
        story.append(Paragraph("No issues found.", normal_style))

    doc.build(story)
    buf.seek(0)

    response = HttpResponse(buf, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="wcag_report_' + str(proj.id) + '.pdf"'
    return response
