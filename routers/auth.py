import hashlib
import re

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette.status import HTTP_302_FOUND
from database import get_db
import models
from dependencies import registrar_log
from security import verify_password
from models import StatusUsuarioEnum
from templating import templates

router = APIRouter()


def _hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def _senha_confere(senha_digitada: str, senha_armazenada: str) -> bool:
    if not senha_armazenada:
        return False
    try:
        if verify_password(senha_digitada, senha_armazenada):
            return True
    except (ValueError, TypeError):
        pass
    if senha_digitada == senha_armazenada:
        return True
    return _hash_senha(senha_digitada) == senha_armazenada


@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    ip = request.client.host
    login = username.strip()
    cpf = re.sub(r"\D", "", login)

    user = db.query(models.User).filter(
        or_(
            models.User.email == login,
            models.User.cpf == cpf,
        )
    ).first()

    if not user or not _senha_confere(password, user.password):
        registrar_log(db, usuario=login, acao="Tentativa de login falhou", request=request)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Usuario ou senha invalidos"},
        )

    try:
        status = (
            user.status
            if isinstance(user.status, StatusUsuarioEnum)
            else StatusUsuarioEnum(user.status)
        )
    except ValueError:
        status = user.status

    if isinstance(status, StatusUsuarioEnum):
        is_ativo = status == StatusUsuarioEnum.ATIVO
        status_str = status.value
    else:
        is_ativo = str(status).lower() == "ativo"
        status_str = str(status)

    if not is_ativo:
        registrar_log(db, usuario=login, acao=f"Login negado - status: {status_str}", request=request)
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": f"Usuario {status_str}. Entre em contato com o administrador.",
            },
        )

    request.session["user"] = user.email
    request.session["user_id"] = user.id
    request.session["user_nome"] = user.nome
    request.session["municipio_id"] = user.municipio_id
    request.session["perfil"] = (
        user.perfil.value if hasattr(user.perfil, "value") else str(user.perfil)
    )

    registrar_log(db, usuario=user.email, acao="Login bem-sucedido", request=request)
    return RedirectResponse(url="/dashboard", status_code=HTTP_302_FOUND)


@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    ip = request.client.host
    usuario = request.session.get("user")
    if usuario:
        registrar_log(db, usuario=usuario, acao="Logout efetuado", request=request)
    request.session.clear()
    return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
