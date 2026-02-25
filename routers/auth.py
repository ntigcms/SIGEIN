from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.status import HTTP_302_FOUND
from database import get_db
import models
from dependencies import registrar_log
from security import verify_password  # ✅ Nosso módulo de hash seguro
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
    """Processa login do usuário com hash seguro e status Enum/string"""
    ip = request.client.host

    # Busca usuário no banco pelo e-mail
    user = db.query(models.User).filter(models.User.email == username).first()

    # ❌ Usuário não existe ou senha incorreta
    if not user or not verify_password(password, user.password):
        registrar_log(db, usuario=username, acao="Tentativa de login falhou", ip=ip)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Usuário ou senha inválidos"}
        )

    # ✅ Converte status do usuário para Enum se estiver usando Enum
    try:
        status = StatusUsuarioEnum(user.status)  # se user.status já for string do DB
    except ValueError:
        status = user.status  # fallback: mantém a string original

    # ❌ Bloqueia login se status não for ativo
    if isinstance(status, StatusUsuarioEnum):
        is_ativo = status == StatusUsuarioEnum.ATIVO
        status_str = status.value
    else:
        # Caso seja string, compara ignorando maiúsculas/minúsculas
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

    # ✅ Login bem-sucedido - salva dados na sessão
    request.session["user"] = user.email
    request.session["user_id"] = user.id
    request.session["municipio_id"] = user.municipio_id
    request.session["perfil"] = user.perfil.value if hasattr(user.perfil, "value") else str(user.perfil)

    registrar_log(db, usuario=username, acao="Login bem-sucedido", ip=ip)

    # Redireciona para dashboard
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