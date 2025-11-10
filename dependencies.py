from fastapi import Request, Depends
from fastapi.templating import Jinja2Templates
from database import get_db
from sqlalchemy.orm import Session
from datetime import datetime
import models

templates = Jinja2Templates(directory="templates")
sessions = {}

def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        return sessions[session_id]
    return None

def registrar_log(db: Session, usuario: str, acao: str, ip: str = None):
    """Registra uma ação no log do sistema"""
    novo_log = models.Log(
        usuario=usuario,
        acao=acao,
        data_hora=datetime.utcnow(),  # salva em UTC
        ip=ip
    )
    db.add(novo_log)
    db.commit()

# função para injetar o usuário logado globalmente nos templates
def inject_current_user(request: Request):
    from .dependencies import get_current_user  # se necessário, importar localmente
    user = get_current_user(request)
    templates.env.globals['current_user'] = user  # agora todos os templates têm current_user
    return user


def template_context(request: Request, current_user: str = Depends(get_current_user)):
    return {"request": request, "current_user": current_user}