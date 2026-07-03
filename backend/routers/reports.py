from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from fpdf import FPDF
from fastapi.responses import Response
import models
from models import Finding
from database import get_db
from agents.reporting_agent import ReportingAgent
from core.dependencies import get_current_user

router = APIRouter(prefix="/api", tags=["Reports"])

@router.get("/reports/pdf/{project_id}")
def generate_pdf_report(project_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    findings = db.query(Finding).filter(Finding.project_id == project_id).all()
    
    reporter = ReportingAgent()
    exec_summary = reporter.generate_executive_summary(project.name if project else "Security Audit", findings)
    
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.add_page()
    pdf.set_font("Arial", size=16, style='B')
    pdf.cell(200, 10, txt="Navjeevan Security Intelligence Report", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=f"Project: {project.name if project else 'N/A'}  |  Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=14, style='B')
    pdf.cell(200, 10, txt="Executive Summary", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, txt=exec_summary)
    
    pdf.add_page()
    pdf.set_font("Arial", size=14, style='B')
    pdf.cell(200, 10, txt="Detailed Findings", ln=True)
    pdf.ln(5)
    
    if not findings:
        pdf.set_font("Arial", size=10)
        pdf.cell(200, 10, txt="- No findings extracted yet.", ln=True)
    else:
        for f in findings:
            pdf.set_font("Arial", size=12, style='B')
            pdf.multi_cell(0, 7, txt=f"[{f.severity}] {f.title}")
            pdf.set_font("Arial", size=10)
            pdf.cell(0, 5, txt=f"Target: {f.target} | Tool: {f.tool} | Status: {f.status}", ln=True)
            cvss_val = f.cvss_score if f.cvss_score else 0.0
            poc_str = "Yes" if f.poc_verified else "No"
            # FEATURE 3: PoC Verified added to PDF
            pdf.cell(0, 5, txt=f"CVSS: {cvss_val:.1f} | OWASP: {f.owasp_category or 'N/A'} | Council: {f.council_verdict or 'N/A'} | PoC Verified: {poc_str}", ln=True)
            if f.poc_verification_notes:
                pdf.set_font("Arial", size=9, style='I')
                pdf.multi_cell(0, 5, txt=f"PoC Notes: {f.poc_verification_notes}")
            pdf.ln(3)
            
    pdf.add_page()
    pdf.set_font("Arial", size=14, style='B')
    pdf.cell(200, 10, txt="Tool Performance Summary", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", size=10, style='B')
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(60, 7, "Tool", border=1, fill=True)
    pdf.cell(40, 7, "Findings", border=1, fill=True)
    pdf.cell(40, 7, "Confirmed", border=1, fill=True)
    pdf.cell(40, 7, "False Positive", border=1, fill=True, ln=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", size=10)
    
    tool_stats = {}
    for f in findings:
        if f.tool not in tool_stats: tool_stats[f.tool] = {"total": 0, "confirmed": 0, "fp": 0}
        tool_stats[f.tool]["total"] += 1
        if f.status == "Confirmed": tool_stats[f.tool]["confirmed"] += 1
        elif f.status == "False Positive": tool_stats[f.tool]["fp"] += 1
            
    for tool, stats in tool_stats.items():
        pdf.cell(60, 7, tool, border=1)
        pdf.cell(40, 7, str(stats["total"]), border=1)
        pdf.cell(40, 7, str(stats["confirmed"]), border=1)
        pdf.cell(40, 7, str(stats["fp"]), border=1, ln=True)
            
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    headers = {"Content-Disposition": f"attachment; filename=report_{project_id}.pdf"}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)