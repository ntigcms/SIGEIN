from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.status import HTTP_302_FOUND
from database import get_db
import models
from dependencies import registrar_log
from security import verify_password, hash_password  # ✅ Nosso módulo de hash seguro
from models import StatusUsuarioEnum



router = APIRouter()
templates = Jinja2Templates(directory="templates")

# ✅ ADICIONE ESTA ROTA (GET) - Exibe o formulário de login
@router.get("/login")
def login_form(request: Request):
    """Exibe o formulário de login"""
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    ip = request.client.host

    # Busca usuário
    user = db.query(models.User).filter(
        models.User.email == username
    ).first()

    # ❌ Usuário não existe
    if not user:
        registrar_log(db, usuario=username, acao="Tentativa de login falhou", ip=ip)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Usuário ou senha inválidos"}
        )

    # ❌ Senha incorreta
    if not verify_password(password, user.password):
        registrar_log(db, usuario=username, acao="Tentativa de login falhou", ip=ip)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Usuário ou senha inválidos"}
        )

    # 🔥 MIGRAÇÃO AUTOMÁTICA PARA BCRYPT (se for SHA-256 antigo)
    if not user.password.startswith("$2b$"):
        user.password = hash_password(password)
        db.commit()

    # ✅ Verifica status
    try:
        status = StatusUsuarioEnum(user.status)
    except ValueError:
        status = user.status

    if isinstance(status, StatusUsuarioEnum):
        is_ativo = status == StatusUsuarioEnum.ATIVO
        status_str = status.value
    else:
        is_ativo = str(status).lower() == "ativo"
        status_str = str(status)

    if not is_ativo:
        registrar_log(db, usuario=username, acao=f"Login negado - status: {status_str}", ip=ip)
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": f"Usuário {status_str}. Entre em contato com o administrador."
            }
        )

    # ✅ Login bem-sucedido
    request.session["user"] = user.email
    request.session["user_id"] = user.id
    request.session["municipio_id"] = user.municipio_id
    request.session["perfil"] = (
        user.perfil.value if hasattr(user.perfil, "value")
        else str(user.perfil)
    )

    registrar_log(db, usuario=username, acao="Login bem-sucedido", ip=ip)

    return RedirectResponse(url="/dashboard", status_code=HTTP_302_FOUND)


@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    """Efetua logout do usuário"""
    ip = request.client.host
    
    # Registra logout antes de limpar sessão
    usuario = request.session.get("user")
    if usuario:
        registrar_log(db, usuario=usuario, acao="Logout efetuado", ip=ip)
    
    # ✅ Limpa a sessão do SessionMiddleware
    request.session.clear()
    
    response = RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
    return response