from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from dependencies import get_current_user, get_db
from models import User
from starlette.status import HTTP_302_FOUND
from database import get_db
from dependencies import get_current_user, registrar_log, inject_current_user, template_context
import models
from typing import Optional

router = APIRouter(prefix="/users", tags=["Users"])
templates = Jinja2Templates(directory="templates")

@router.get("/")
def list_users(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    
    users = db.query(User).all()  # Pega todos os usuários do banco
    return templates.TemplateResponse(
        "users_list.html",
        {"request": request, "users": users, "user": user}
    )
# ============================
# Formulário de cadastro
# ============================
@router.get("/add")
def add_user_form(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    return templates.TemplateResponse("user_form.html", {
        "request": request,
        "user": user,
        "action": "add"
    })

# ============================
# Inserção no banco
# ============================
@router.post("/add")
def add_user(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    perfil: str = Form(...),
    status: str = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    novo_usuario = models.User(
        username=nome,
        email=email,
        password=senha,
        role=perfil,
        status=status
    )
    db.add(novo_usuario)
    db.commit()

    registrar_log(db, usuario=user, acao=f"Cadastrou novo usuário {nome} ({perfil})", ip=ip)
    return RedirectResponse("/users", status_code=HTTP_302_FOUND)

# ============================
# GET para pegar dados do usuário
# ============================

@router.get("/edit/{user_id}")
def edit_user_form(
    user_id: int, 
    context: dict = Depends(template_context), 
    db: Session = Depends(get_db)
):
    """Rota para editar usuário."""

    current_user = context.get("current_user")
    if not current_user:
        return RedirectResponse("/login")

    # Busca usuário pelo ID
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return HTMLResponse("Usuário não encontrado", status_code=404)

    # Atualiza contexto com dados do usuário e ação
    context.update({"user": user, "action": "edit"})

    return templates.TemplateResponse("user_form.html", context)


# ============================
# POST para atualizar usuário
# ============================

@router.post("/edit/{user_id}")
def edit_user(
    request: Request,
    user_id: int,
    nome: str = Form(...),
    senha: str = Form(""),  # permite ficar em branco
    perfil: str = Form(...),
    status: str = Form(...),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    # Redireciona para login se não estiver autenticado
    if not current_user:
        return RedirectResponse("/login")

    # Busca usuário
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Atualiza campos
    user.username = nome
    user.role = perfil
    user.status = status

    # Atualiza senha somente se o campo não estiver vazio
    if senha.strip():
        user.password = senha  # Ideal: hash da senha aqui

    db.commit()

    # Redireciona para lista de usuários
    return RedirectResponse("/users", status_code=HTTP_302_FOUND)

# ============================
# Formulário para editar usuário
# ============================


# ============================
# Excluir usuário
# ============================

@router.get("/delete/{user_id}")
def delete_user(request: Request, user_id: int, db: Session = Depends(get_db),
                current_user: str = Depends(get_current_user)):
    # Redireciona para login se não estiver autenticado
    if not current_user:
        return RedirectResponse("/login")

    ip = request.client.host
    user = db.query(models.User).filter(models.User.id == user_id).first()

    if user:
        db.delete(user)
        db.commit()
        registrar_log(db, usuario=current_user, acao=f"Excluiu usuário ID {user_id}", ip=ip)

    return RedirectResponse("/users", status_code=HTTP_302_FOUND)