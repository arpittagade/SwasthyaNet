from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def state_rows(phcs: list[dict], outbreak: dict) -> list[dict]:
    rows = []
    for phc in phcs:
        rows.append({"phc": phc["name"], "district": phc["district"], "status": phc["status"], "beds_total": phc["beds"], "beds_occupied": phc["occupied"], "occupancy_pct": phc["occupancy_pct"], "staff_attendance_pct": phc["attendance"], "active_alerts": phc["active_alerts"]})
    return rows


def csv_report(phcs: list[dict], outbreak: dict) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["SwasthyaNet synthetic state health report"])
    writer.writerow(["Generated UTC", datetime.now(timezone.utc).isoformat(timespec="seconds")])
    writer.writerow([])
    writer.writerow(["PHC", "District", "Status", "Beds total", "Beds occupied", "Occupancy %", "Staff attendance %", "Active alerts"])
    for row in state_rows(phcs, outbreak): writer.writerow(row.values())
    writer.writerow([])
    writer.writerow(["Disease trend summary", "Value"])
    writer.writerow(["Total synthetic reports", outbreak["summary"]["total_reports"]])
    writer.writerow(["Leading signal", outbreak["summary"]["leading_signal"]])
    writer.writerow(["Dengue week-over-week change %", outbreak["summary"]["week_over_week"]])
    writer.writerow([])
    writer.writerow(["Weekly outbreak trends"])
    writer.writerow(["Week", "Dengue", "Malaria", "Acute respiratory infection", "Acute diarrhoeal disease"])
    for trend in outbreak["trends"]: writer.writerow([trend["week"], trend["dengue"], trend["malaria"], trend["respiratory"], trend["diarrhoeal"]])
    return output.getvalue().encode("utf-8")


def pdf_report(phcs: list[dict], outbreak: dict) -> bytes:
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet(); story = []
    story.append(Paragraph("SwasthyaNet — State Health Intelligence Report", styles["Title"]))
    story.append(Paragraph("Synthetic hackathon report · No patient-level data · Generated " + datetime.now(timezone.utc).isoformat(timespec="seconds") + " UTC", styles["Normal"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Network summary: {len(phcs)} visible PHC node(s), {sum(p['occupied'] for p in phcs)}/{sum(p['beds'] for p in phcs)} beds occupied, and {sum(p['active_alerts'] for p in phcs)} active alerts.", styles["BodyText"]))
    story.append(Spacer(1, 10))
    table_data = [["PHC", "District", "Status", "Beds", "Occupancy", "Attendance", "Alerts"]]
    for row in state_rows(phcs, outbreak): table_data.append([row["phc"], row["district"], row["status"], f"{row['beds_occupied']}/{row['beds_total']}", f"{row['occupancy_pct']}%", f"{row['staff_attendance_pct']}%", row["active_alerts"]])
    table = Table(table_data, repeatRows=1, colWidths=[34*mm, 25*mm, 18*mm, 20*mm, 22*mm, 22*mm, 15*mm])
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0e9477")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.3,colors.HexColor("#cadbd5")),("FONTSIZE",(0,0),(-1,-1),7),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#eff7f4")]),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.extend([table, Spacer(1, 14), Paragraph("Synthetic disease-outbreak trend summary", styles["Heading2"]), Paragraph(f"Leading signal: {outbreak['summary']['leading_signal']}. Total weekly reports in the selected window: {outbreak['summary']['total_reports']}. Dengue week-over-week change: {outbreak['summary']['week_over_week']}%.", styles["BodyText"]), Spacer(1, 8)])
    trend_data = [["Week", "Dengue", "Malaria", "Respiratory", "Diarrhoeal"]] + [[r["week"],r["dengue"],r["malaria"],r["respiratory"],r["diarrhoeal"]] for r in outbreak["trends"]]
    trend_table=Table(trend_data,repeatRows=1,colWidths=[35*mm,25*mm,25*mm,35*mm,35*mm]); trend_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17352e")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.25,colors.HexColor("#cadbd5")),("FONTSIZE",(0,0),(-1,-1),7)])); story.append(trend_table)
    document.build(story)
    return output.getvalue()
