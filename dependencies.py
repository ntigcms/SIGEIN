from fastapi import Request, Depends
from database import get_db
from sqlalchemy.orm import Session
from datetime import datetime
import models

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
