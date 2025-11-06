from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.status import HTTP_302_FOUND
from database import get_db
import models
from dependencies import sessions, get_current_user, registrar_log  # ⬅️ import do logger

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login_post(request: Request, username: str = Form(...), password: str = Form(...),
               db: Session = Depends(get_db)):
    ip = request.client.host  # pega IP do usuário

    user = db.query(models.User).filter(
        models.User.username == username,
        models.User.password == password
    ).first()

    # Falha no login
    if not user:
        registrar_log(db, usuario=username, acao="Tentativa de login falhou", ip=ip)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Usuário ou senha inválidos"}
        )

    # Login bem-sucedido
    session_id = str(user.id)
    sessions[session_id] = user.username
    response = RedirectResponse(url="/dashboard", status_code=HTTP_302_FOUND)
    response.set_cookie(key="session_id", value=session_id)

    registrar_log(db, usuario=username, acao="Login bem-sucedido", ip=ip)
    return response


@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    ip = request.client.host
    session_id = request.cookies.get("session_id")

    if session_id in sessions:
        usuario = sessions[session_id]
        registrar_log(db, usuario=usuario, acao="Logout efetuado", ip=ip)
        del sessions[session_id]

    response = RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
    response.delete_cookie("session_id")
    return response
