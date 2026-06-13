import io
import calendar
from datetime import datetime
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from django.utils.translation import gettext as _


def generate_pdf_report(profile, year, month):
    """Generate a PDF time report for a profile and month.

    Returns a BytesIO buffer containing the PDF.
    """
    from trackable.timetracking.models import VacationEntry

    time_entries = list(profile.get_monthly_entries(year, month).order_by("date"))
    last_day = calendar.monthrange(year, month)[1]
    vacation_entries = list(
        profile.vacation_entries.filter(
            start_date__lte=datetime(year, month, last_day).date(),
            end_date__gte=datetime(year, month, 1).date(),
        ).order_by("start_date")
    )
    total_hours = profile.get_monthly_hours(year, month)
    total_earnings = profile.get_monthly_earnings(year, month)
    total_vacation_days = sum(v.workdays for v in vacation_entries)
    month_name = datetime(year, month, 1).strftime("%B %Y")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#8839ef"),
        spaceAfter=20,
    )

    elements.append(Paragraph(f"{profile.title} - {month_name}", title_style))
    elements.append(Paragraph(f"{profile.position}", styles["Normal"]))
    if profile.address:
        elements.append(Paragraph(profile.address, styles["Normal"]))
    elements.append(Spacer(1, 20))

    # Time entries table
    data = [
        [_("Date"), _("Start"), _("End"), _("Break"), _("Hours"), _("Activity")]
    ]
    for entry in time_entries:
        data.append(
            [
                entry.date.strftime("%d.%m.%Y"),
                entry.start_time.strftime("%H:%M"),
                entry.end_time.strftime("%H:%M"),
                f"{entry.pause_duration}h",
                f"{entry.hours_worked:.2f}h",
                entry.notes or "",
            ]
        )

    table = Table(
        data, colWidths=[1 * inch, 1 * inch, 1 * inch, 1 * inch, 1 * inch, 4 * inch]
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8938eb")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#45475a")),
            ]
        )
    )

    elements.append(table)
    elements.append(Spacer(1, 20))

    totals_data = []
    totals_data.append([_("Total Hours") + ":", f"{total_hours:.2f}h"])
    if total_earnings > 0:
        totals_data.append([_("Total Earnings") + ":", f"{total_earnings:.2f}"])
    if total_vacation_days > 0:
        totals_data.append([_("Vacation Days") + ":", str(total_vacation_days)])

    totals_table = Table(totals_data, colWidths=[2 * inch, 1.5 * inch], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#3b782c")),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(totals_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer
