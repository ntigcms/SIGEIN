import contextvars

from fastapi import Request, Depends
from templating import templates
from database import get_db
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

import models

audit_was_logged: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "audit_was_logged", default=False
)


def mark_audit_logged() -> None:
    audit_was_logged.set(True)


def get_current_user(request: Request):
    """
    Obtém usuário logado da sessão do SessionMiddleware
    Retorna o EMAIL do usuário (não username)
    """
    return request.session.get("user")  # ✅ Retorna o email



def _infer_tipo(acao: str, tipo: Optional[str] = None) -> str:
    if tipo:
        return tipo
    a = (acao or "").lower()
    if any(k in a for k in ("login", "logout", "sessão", "sessao", "tentativa de login")):
        return "acesso"
    return "operacional"


def registrar_log(
    db: Session,
    usuario: str,
    acao: str,
    ip: str = None,
    user_id: int = None,
    tipo: str = None,
    request: Request = None,
):
    """Registra uma ação no log do sistema."""
    municipio_id = None
    user_agent = None

    if request is not None:
        if ip is None and request.client:
            ip = request.client.host
        user_agent = (request.headers.get("user-agent") or "")[:500] or None

    if user_id is None and usuario:
        u = db.query(models.User).filter(models.User.email == usuario).first()
        if u:
            user_id = u.id
            municipio_id = u.municipio_id
    elif user_id:
        u = db.query(models.User).filter(models.User.id == user_id).first()
        if u:
            municipio_id = u.municipio_id

    novo_log = models.Log(
        usuario=usuario or "—",
        acao=(acao or "")[:255],
        data_hora=datetime.utcnow(),
        ip=(ip or "")[:50] if ip else None,
        user_id=user_id,
        municipio_id=municipio_id,
        tipo=_infer_tipo(acao, tipo),
        user_agent=user_agent,
    )
    db.add(novo_log)
    db.commit()
    mark_audit_logged()


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