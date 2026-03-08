"""
Templates Jinja2 compartilhados por todas as rotas.
Inclui global get_user_display_name(request) para exibir o nome do usuário no layout.
"""
from fastapi import Request
from fastapi.templating import Jinja2Templates
from database import SessionLocal
from models import User
from datetime import datetime, timezone

templates = Jinja2Templates(directory="templates")


def tempo_recebido(dt):
    """Formata datetime como 'Recebido há X dias/meses/anos'."""
    if not dt:
        return "-"
    agora = datetime.utcnow()
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    diff = agora - dt
    dias = diff.days
    if dias == 0:
        return "Recebido hoje"
    if dias == 1:
        return "Recebido há 1 dia"
    if dias < 30:
        return f"Recebido há {dias} dias"
    if dias < 365:
        meses = dias // 30
        return f"Recebido há {meses} {'mês' if meses == 1 else 'meses'}"
    anos = dias // 365
    return f"Recebido há {anos} {'ano' if anos == 1 else 'anos'}"


def get_user_display_name(request: Request) -> str:
    """Retorna o nome do usuário logado (para exibir no canto superior direito)."""
    email = request.session.get("user")
    if not email:
        return ""
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        return u.nome if u else email
    finally:
        db.close()


def get_logged_user(request: Request):
    """Retorna o email do usuário logado (compatibilidade)."""
    return request.session.get("user")


def get_meus_dados(request: Request):
    """Retorna dict com dados do usuário logado para a modal Meus Dados, incluindo lotação administrativa."""
    email = request.session.get("user")
    if not email:
        return None
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        if not u:
            return None
        municipio_nome = u.municipio.nome if u.municipio else ""
        orgao_nome = (u.orgao.sigla or u.orgao.nome) if u.orgao else ""
        unidade_nome = (u.unidade.sigla or u.unidade.nome) if u.unidade else ""
        return {
            "id": u.id,
            "nome": u.nome or "",
            "email": u.email or "",
            "perfil": u.perfil or "",
            "status": getattr(u, "status", None) or "",
            "municipio": municipio_nome,
            "orgao": orgao_nome,
            "unidade": unidade_nome,
        }
    finally:
        db.close()


templates.env.globals["get_user_display_name"] = get_user_display_name
templates.env.globals["get_logged_user"] = get_logged_user
templates.env.globals["get_meus_dados"] = get_meus_dados
templates.env.filters["tempo_recebido"] = tempo_recebido
