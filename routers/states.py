from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, registrar_log
from models import EquipmentState
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/states", tags=["States"])
templates = Jinja2Templates(directory="templates")


# LISTAR ESTADOS
@router.get("/")
def list_states(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    states = db.query(EquipmentState).all()
    return templates.TemplateResponse(
        "states.html",
        {"request": request, "states": states, "user": user}
    )


# FORMULÁRIO DE ADIÇÃO DE ESTADO
@router.get("/add")
def add_state_form(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        "state_add.html",
        {"request": request, "user": user, "action": "add"}
    )


# ADICIONAR ESTADO
@router.post("/add")
def add_state(
    request: Request,
    nome: str = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    novo_estado = EquipmentState(nome=nome)

    db.add(novo_estado)
    db.commit()
    db.refresh(novo_estado)

    registrar_log(db, usuario=user, acao=f"Cadastrou estado: {nome}", ip=ip)
    return RedirectResponse("/states", status_code=HTTP_302_FOUND)


# FORMULÁRIO DE EDIÇÃO DE ESTADO
@router.get("/edit/{state_id}")
def edit_state_form(
    state_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    estado = db.query(EquipmentState).filter(EquipmentState.id == state_id).first()
    if not estado:
        return RedirectResponse("/states")

    return templates.TemplateResponse(
        "state_add.html",
        {"request": request, "user": user, "estado": estado, "action": "edit"}
    )


# EDITAR ESTADO
@router.post("/edit/{state_id}")
def edit_state(
    request: Request,
    state_id: int,
    nome: str = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    estado = db.query(EquipmentState).filter(EquipmentState.id == state_id).first()
    if estado:
        estado.nome = nome
        db.commit()
        registrar_log(db, usuario=user, acao=f"Editou estado ID {state_id}", ip=ip)

    return RedirectResponse("/states", status_code=HTTP_302_FOUND)


# EXCLUIR ESTADO
@router.get("/delete/{state_id}")
def delete_state(
    request: Request,
    state_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    estado = db.query(EquipmentState).filter(EquipmentState.id == state_id).first()
    if estado:
        db.delete(estado)
        db.commit()
        registrar_log(db, usuario=user, acao=f"Excluiu estado ID {state_id}", ip=ip)

    return RedirectResponse("/states", status_code=HTTP_302_FOUND)
