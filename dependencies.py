from fastapi import Request, Depends
from fastapi.templating import Jinja2Templates
from database import get_db
from sqlalchemy.orm import Session
from datetime import datetime
import models

templates = Jinja2Templates(directory="templates")

# ❌ REMOVIDO - Não usamos mais dict em memória
# sessions = {}


def get_current_user(request: Request):
    """
    Obtém usuário logado da sessão do SessionMiddleware
    Retorna o EMAIL do usuário (não username)
    """
    return request.session.get("user")  # ✅ Retorna o email



def registrar_log(db: Session, usuario: str, acao: str, ip: str = None):
    """Registra uma ação no log do sistema"""
    novo_log = models.Log(
        usuario=usuario,
        acao=acao,
        data_hora=datetime.utcnow(),
        ip=ip
    )
    db.add(novo_log)
    db.commit()


def inject_current_user(request: Request):
    """
    Injeta o usuário logado globalmente nos templates
    """
    user = get_current_user(request)
    templates.env.globals['current_user'] = user
    return user


def template_context(request: Request, current_user: str = Depends(get_current_user)):
    """
    Retorna contexto padrão para templates
    """
    return {
        "request": request,
        "current_user": current_user
    }