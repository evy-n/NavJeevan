from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from fpdf import FPDF
from fastapi.responses import Response
import models
from models import Finding
from database import get_db

router = APIRouter(prefix="/api", tags=["Reports"])

@router.get("/reports/pdf/{project_id}")
def generate_pdf_report(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    findings = db.query(Finding).filter(Finding.project_id == project_id).all()
    
    sev_count = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
    for f in findings:
        if f.severity in sev_count: sev_count[f.severity] += 1
            
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=15, style='B')
    pdf.cell(200, 10, txt="Navjeevan Security Report", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=f"Project: {project.name}  |  Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", size=12, style='B')
    pdf.cell(200, 10, txt="Severity Summary:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=f"Critical: {sev_count['Critical']} | High: {sev_count['High']} | Medium: {sev_count['Medium']} | Low: {sev_count['Low']} | Info: {sev_count['Info']}", ln=True)
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12, style='B')
    pdf.cell(200, 10, txt="Detailed Findings:", ln=True)
    pdf.set_font("Arial", size=10)
    
    if not findings:
        pdf.cell(200, 10, txt="- No findings extracted yet.", ln=True)
    else:
        for f in findings:
            pdf.multi_cell(0, 10, txt=f"- [{f.severity}] {f.title} (Confidence: {f.confidence}%)")
            
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    headers = {"Content-Disposition": f"attachment; filename=report_{project_id}.pdf"}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)