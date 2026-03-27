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



def registrar_log(
    db: Session,
    usuario: str,
    acao: str,
    ip: str = None,
    municipio_id: int = None,
    user_id: int = None,
    user_agent: str = None,
    tipo: str = "operacional",
):
    """Registra uma ação no log do sistema com escopo de município."""
    if usuario and (municipio_id is None or user_id is None):
        user_obj = db.query(models.User).filter(models.User.email == usuario).first()
        if user_obj:
            if municipio_id is None:
                municipio_id = user_obj.municipio_id
            if user_id is None:
                user_id = user_obj.id

    novo_log = models.Log(
        municipio_id=municipio_id,
        user_id=user_id,
        tipo=tipo,
        usuario=usuario,
        acao=acao,
        data_hora=datetime.utcnow(),
        ip=ip,
        user_agent=user_agent
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