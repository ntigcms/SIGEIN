from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.status import HTTP_302_FOUND
from database import get_db
import models
from dependencies import get_current_user, registrar_log  # ✅ Removido sessions

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login")
def login_form(request: Request):
    """Exibe formulário de login"""
    # Se já estiver logado, redireciona
    if request.session.get("user"):
        return RedirectResponse("/dashboard", status_code=302)
    
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Processa login do usuário"""
    ip = request.client.host

    # Busca usuário no banco
    user = db.query(models.User).filter(
        models.User.username == username,
        models.User.password == password  # ⚠️ Em produção use hash
    ).first()

    # ❌ Falha no login
    if not user:
        registrar_log(db, usuario=username, acao="Tentativa de login falhou", ip=ip)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Usuário ou senha inválidos"}
        )

    # ✅ Verifica status do usuário
    status = user.status.value if hasattr(user.status, 'value') else user.status
    if status != "ativo":
        registrar_log(db, usuario=username, acao=f"Login negado - status: {status}", ip=ip)
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": f"Usuário {status}. Entre em contato com o administrador."
            }
        )

    # ✅ Login bem-sucedido - Salva na sessão
    request.session["user"] = user.username
    request.session["user_id"] = user.id
    request.session["municipio_id"] = user.municipio_id
    request.session["perfil"] = user.perfil.value if hasattr(user.perfil, 'value') else user.perfil

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