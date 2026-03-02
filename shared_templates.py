"""
Templates Jinja2 compartilhados por todas as rotas.
Inclui global get_user_display_name(request) para exibir o nome do usuário no layout.
"""
from fastapi import Request
from fastapi.templating import Jinja2Templates
from database import SessionLocal
from models import User

templates = Jinja2Templates(directory="templates")


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


templates.env.globals["get_user_display_name"] = get_user_display_name
templates.env.globals["get_logged_user"] = get_logged_user
