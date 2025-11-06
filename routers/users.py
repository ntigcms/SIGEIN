from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from dependencies import get_current_user, get_db
from models import User
from starlette.status import HTTP_302_FOUND
from database import get_db
from dependencies import get_current_user, registrar_log
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

# GET para pegar dados do usuário
@router.get("/users/edit/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return {
        "id": user.id,
        "username": user.username,
        "email": getattr(user, "email", None),  # se existir
        "role": user.role,
        "status": getattr(user, "status", None)
    }

# POST para atualizar usuário
@router.post("/users/edit/{user_id}")
def edit_user(
    request: Request,
    user_id: int,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    status: str = Form(...),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    # Redireciona para login se não estiver autenticado
    if not current_user:
        return RedirectResponse("/login")

    ip = request.client.host
    user = db.query(models.User).filter(models.User.id == user_id).first()

    if user:
        # Atualizando os campos
        user.username = username
        user.password = password  # ideal: usar hash da senha
        user.role = role
        if hasattr(user, "status"):
            user.status = status

        db.commit()
        registrar_log(db, usuario=current_user, acao=f"Editou usuário ID {user_id}", ip=ip)

    return RedirectResponse("/users", status_code=HTTP_302_FOUND)

# ============================
# Formulário para editar usuário
# ============================
@router.get("/edit/{user_id}")
def edit_user_form(user_id: int, request: Request, db: Session = Depends(get_db),
                   current_user: str = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse("/login")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return HTMLResponse("Usuário não encontrado", status_code=404)

    return templates.TemplateResponse("user_form.html", {
        "request": request,
        "user": user,
        "current_user": current_user,
        "action": "edit"
    })

# Excluir usuário
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