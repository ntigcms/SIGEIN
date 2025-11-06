from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user
from fastapi.templating import Jinja2Templates
import models
from datetime import timezone, timedelta
import pytz
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
import io
from fastapi.responses import StreamingResponse
from openpyxl import Workbook

router = APIRouter(prefix="/logs", tags=["Logs"])
templates = Jinja2Templates(directory="templates")  # certifique-se que a pasta existe

@router.get("/")
def listar_logs(request: Request, db: Session = Depends(get_db),
                user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    
    logs = db.query(models.Log).order_by(models.Log.data_hora.desc()).all()
    
    # Definir timezone GMT-3
    gmt3 = pytz.timezone("America/Sao_Paulo")
    
    for log in logs:
        # Se datetime for naive, assumimos que está em UTC
        if log.data_hora.tzinfo is None:
            log.data_hora = log.data_hora.replace(tzinfo=timezone.utc)
        # Converte para GMT-3
        log.data_hora = log.data_hora.astimezone(gmt3)
    
    return templates.TemplateResponse("logs_list.html", {
        "request": request,
        "logs": logs,
        "user": user
    })

@router.get("/export/pdf")
def export_logs_pdf(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    logs = db.query(models.Log).order_by(models.Log.data_hora.desc()).all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []

    styles = getSampleStyleSheet()
    title = Paragraph("Logs do Sistema", styles['Title'])
    elements.append(title)
    elements.append(Paragraph(f"Usuário logado: {user}", styles['Normal']))
    elements.append(Paragraph("<br/>", styles['Normal']))

    data = [["Data/Hora", "Usuário", "Ação"]]
    for log in logs:
        data.append([log.data_hora.strftime("%d/%m/%Y %H:%M:%S"), log.usuario, log.acao])

    table = Table(data, colWidths=[120, 100, 250])
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f2f2f2")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN',(0,0),(-1,-1),'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ])

    for i in range(1, len(data)):
        if i % 2 == 0:
            style.add('BACKGROUND', (0,i), (-1,i), colors.HexColor("#f9f9f9"))

    table.setStyle(style)
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=logs_formatado.pdf"}
    )

@router.get("/export/xlsx")
def export_logs_xlsx(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    logs = db.query(models.Log).order_by(models.Log.data_hora.desc()).all()

    # Criar planilha
    wb = Workbook()
    ws = wb.active
    ws.title = "Logs do Sistema"

    # Cabeçalhos
    ws.append(["Data/Hora", "Usuário", "Ação"])

    # Dados
    for log in logs:
        ws.append([log.data_hora.strftime("%d/%m/%Y %H:%M:%S"), log.usuario, log.acao])

    # Estilo simples (opcional)
    for col in ws.columns:
        max_length = max(len(str(cell.value)) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_length + 2

    # Salvar em memória
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    # Retornar arquivo
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=logs_sistema.xlsx"}
    )