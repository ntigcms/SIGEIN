from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from dependencies import get_current_user, registrar_log
import models
from datetime import timezone, timedelta
import pytz
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
import io
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from shared_templates import templates
from cleanup_old_logs import cleanup_old_logs, estimate_old_logs

router = APIRouter(prefix="/logs", tags=["Logs"])

def _logs_scope_query(db: Session, user_obj: models.User):
    """Escopo multi-tenant dos logs com fallback para registros legados sem municipio_id."""
    logs_q = db.query(models.Log)
    if user_obj.perfil == "master":
        return logs_q

    users_municipio = db.query(models.User.email).filter(
        models.User.municipio_id == user_obj.municipio_id
    )
    return logs_q.filter(
        (models.Log.municipio_id == user_obj.municipio_id)
        | (
            models.Log.municipio_id.is_(None)
            & models.Log.usuario.in_(users_municipio)
        )
    )

def _require_master_user(db: Session, user: str):
    if not user:
        return None
    user_obj = db.query(models.User).filter(models.User.email == user).first()
    if not user_obj or user_obj.perfil != "master":
        return None
    return user_obj

@router.get("/")
def listar_logs(request: Request, db: Session = Depends(get_db),
                user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    user_obj = db.query(models.User).filter(models.User.email == user).first()
    if not user_obj:
        return RedirectResponse("/login")

    logs_q = _logs_scope_query(db, user_obj)
    logs = logs_q.order_by(models.Log.data_hora.desc()).all()
    
    # Definir timezone GMT-3
    gmt3 = pytz.timezone("America/Sao_Paulo")
    
    for log in logs:
        # Se datetime for naive, assumimos que está em UTC
        if log.data_hora.tzinfo is None:
            log.data_hora = log.data_hora.replace(tzinfo=timezone.utc)
        # Converte para GMT-3
        log.data_hora = log.data_hora.astimezone(gmt3)
    
    governanca = None
    if user_obj.perfil == "master":
        counts_rows = (
            db.query(models.Log.tipo, func.count(models.Log.id))
            .group_by(models.Log.tipo)
            .all()
        )
        counts_map = {tipo or "operacional": total for tipo, total in counts_rows}
        ultima_retencao = (
            db.query(models.Log)
            .filter(models.Log.tipo == "seguranca", models.Log.acao.ilike("Executou retenção de logs%"))
            .order_by(models.Log.data_hora.desc())
            .first()
        )
        dry_run = estimate_old_logs(
            retention_days_operacional=int(os.getenv("LOG_RETENTION_DAYS_OPERACIONAL", "365")),
            retention_days_seguranca=int(os.getenv("LOG_RETENTION_DAYS_SEGURANCA", "730")),
        )
        governanca = {
            "ultima_retencao": ultima_retencao,
            "total_operacional": counts_map.get("operacional", 0),
            "total_seguranca": counts_map.get("seguranca", 0),
            "total_logs": sum(counts_map.values()),
            "dry_run": dry_run,
        }

    return templates.TemplateResponse("logs_list.html", {
        "request": request,
        "logs": logs,
        "user": user,
        "user_perfil": user_obj.perfil,
        "governanca": governanca,
    })


@router.post("/admin/retention/dry-run")
def retention_dry_run(
    retention_days_operacional: int = Form(365),
    retention_days_seguranca: int = Form(730),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    user_obj = _require_master_user(db, user)
    if not user_obj:
        return JSONResponse({"success": False, "message": "Apenas MASTER pode simular retenção."}, status_code=403)

    result = estimate_old_logs(
        retention_days_operacional=retention_days_operacional,
        retention_days_seguranca=retention_days_seguranca,
    )
    return JSONResponse({"success": True, "result": result})


@router.post("/admin/retention/run")
def run_retention(
    request: Request,
    retention_days_operacional: int = Form(365),
    retention_days_seguranca: int = Form(730),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    user_obj = _require_master_user(db, user)
    if not user_obj:
        return JSONResponse({"success": False, "message": "Apenas MASTER pode executar retenção."}, status_code=403)

    result = cleanup_old_logs(
        retention_days_operacional=retention_days_operacional,
        retention_days_seguranca=retention_days_seguranca,
    )
    registrar_log(
        db=db,
        usuario=user_obj.email,
        acao=(
            "Executou retenção de logs "
            f"(operacional={retention_days_operacional}d, "
            f"seguranca={retention_days_seguranca}d)"
        ),
        ip=request.client.host,
        user_agent=request.headers.get("user-agent"),
        tipo="seguranca",
    )

    return JSONResponse({"success": True, "result": result})

@router.get("/export/pdf")
def export_logs_pdf(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    user_obj = db.query(models.User).filter(models.User.email == user).first()
    if not user_obj:
        return RedirectResponse("/login")

    logs_q = _logs_scope_query(db, user_obj)
    logs = logs_q.order_by(models.Log.data_hora.desc()).all()

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

    user_obj = db.query(models.User).filter(models.User.email == user).first()
    if not user_obj:
        return RedirectResponse("/login")

    logs_q = _logs_scope_query(db, user_obj)
    logs = logs_q.order_by(models.Log.data_hora.desc()).all()

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