from datetime import datetime, timezone
from typing import List, Optional
import io

import pytz
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, StreamingResponse
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Log
from templating import templates

router = APIRouter(prefix="/logs", tags=["Logs"])

TZ_BR = pytz.timezone("America/Sao_Paulo")


def _to_local(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_BR)


def _fmt_dt(dt: datetime) -> str:
    local = _to_local(dt)
    return local.strftime("%d/%m/%Y %H:%M:%S") if local else "—"


def _tipo_label(tipo: str) -> str:
    labels = {
        "acesso": "Acesso",
        "operacional": "Operacional",
        "sistema": "Sistema",
    }
    return labels.get((tipo or "").lower(), tipo or "Operacional")


def _tipo_badge_class(tipo: str) -> str:
    t = (tipo or "").lower()
    if t == "acesso":
        return "logs-badge--acesso"
    if t == "sistema":
        return "logs-badge--sistema"
    return "logs-badge--operacional"


def _query_logs(db: Session, limit: Optional[int] = None):
    q = db.query(Log).order_by(Log.data_hora.desc())
    if limit:
        q = q.limit(limit)
    return q.all()


def _build_log_rows(logs: List[Log]) -> List[dict]:
    rows = []
    for log in logs:
        rows.append({
            "id": log.id,
            "data_hora": _fmt_dt(log.data_hora),
            "data_sort": log.data_hora.isoformat() if log.data_hora else "",
            "usuario": log.usuario or "—",
            "tipo": log.tipo or "operacional",
            "tipo_label": _tipo_label(log.tipo),
            "tipo_class": _tipo_badge_class(log.tipo),
            "ip": log.ip or "—",
            "acao": log.acao or "—",
            "user_agent": (log.user_agent or "—")[:80],
        })
    return rows


def _stats(db: Session) -> dict:
    total = db.query(func.count(Log.id)).scalar() or 0
    usuarios_ativos = db.query(func.count(func.distinct(Log.usuario))).filter(
        Log.usuario.isnot(None), Log.usuario != ""
    ).scalar() or 0
    acesso = db.query(func.count(Log.id)).filter(Log.tipo == "acesso").scalar() or 0
    operacional = db.query(func.count(Log.id)).filter(Log.tipo == "operacional").scalar() or 0
    sistema = db.query(func.count(Log.id)).filter(Log.tipo == "sistema").scalar() or 0

    hoje = datetime.now(TZ_BR).date()
    logs_hoje = 0
    for dt, in db.query(Log.data_hora).all():
        if dt and _to_local(dt).date() == hoje:
            logs_hoje += 1

    return {
        "total": total,
        "hoje": logs_hoje,
        "usuarios_ativos": usuarios_ativos,
        "acesso": acesso,
        "operacional": operacional,
        "sistema": sistema,
    }


@router.get("/")
def listar_logs(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    logs = _query_logs(db)
    log_rows = _build_log_rows(logs)
    stats = _stats(db)

    usuarios = sorted({r["usuario"] for r in log_rows if r["usuario"] != "—"})
    tipos = sorted({r["tipo_label"] for r in log_rows})

    return templates.TemplateResponse(
        "logs_list.html",
        {
            "request": request,
            "logs": log_rows,
            "stats": stats,
            "usuarios": usuarios,
            "tipos": tipos,
            "user": user,
            "hide_app_header": True,
        },
    )


def _export_rows(db: Session):
    logs = _query_logs(db)
    return [["Data/Hora", "Usuário", "Tipo", "IP", "Ação"]] + [
        [_fmt_dt(l.data_hora), l.usuario or "", _tipo_label(l.tipo), l.ip or "", l.acao or ""]
        for l in logs
    ]


@router.get("/export/pdf")
def export_logs_pdf(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    data = _export_rows(db)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Auditoria do Sistema — SIGEIN", styles["Title"]))
    elements.append(Paragraph(f"Exportado por: {user}", styles["Normal"]))
    elements.append(Paragraph("<br/>", styles["Normal"]))

    table = Table(data, colWidths=[110, 90, 70, 70, 200])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=auditoria_sigen.pdf"},
    )


@router.get("/export/xlsx")
def export_logs_xlsx(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    data = _export_rows(db)
    wb = Workbook()
    ws = wb.active
    ws.title = "Auditoria"
    for row in data:
        ws.append(row)
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=auditoria_sigen.xlsx"},
    )
