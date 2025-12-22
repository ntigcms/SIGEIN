from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, registrar_log
from models import Unit
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/units", tags=["Units"])
templates = Jinja2Templates(directory="templates")


# LISTAR UNIDADES
@router.get("/")
def list_units(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    units = db.query(Unit).all()  # ✅ pegando todos os registros da tabela Unit
    return templates.TemplateResponse(
        "units.html",  # seu template
        {"request": request, "units": units, "user": user}
    )


# FORMULÁRIO DE ADIÇÃO DE UNIDADE
@router.get("/add")
def add_unit_form(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        "unit_add.html",
        {"request": request, "user": user, "action": "add"}
    )


# ADICIONAR UNIDADE
@router.post("/add")
def add_unit(
    request: Request,
    name: str = Form(...),
    manager: str = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    new_unit = Unit(name=name, manager=manager)

    db.add(new_unit)
    db.commit()
    db.refresh(new_unit)

    registrar_log(db, usuario=user, acao=f"Cadastrou unidade: {name}", ip=ip)
    return RedirectResponse("/units", status_code=HTTP_302_FOUND)


# FORMULÁRIO DE EDIÇÃO DE UNIDADE
@router.get("/edit/{unit_id}")
def edit_unit_form(
    unit_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    unidade = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unidade:
        return RedirectResponse("/units")

    return templates.TemplateResponse(
        "unit_add.html",
        {"request": request, "user": user, "unidade": unidade, "action": "edit"}
    )


# EDITAR UNIDADE
@router.post("/edit/{unit_id}")
def edit_unit(
    request: Request,
    unit_id: int,
    name: str = Form(...),
    manager: str = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    unidade = db.query(Unit).filter(Unit.id == unit_id).first()
    if unidade:
        unidade.name = name
        unidade.manager = manager
        db.commit()
        registrar_log(db, usuario=user, acao=f"Editou unidade ID {unit_id}", ip=ip)

    return RedirectResponse("/units", status_code=HTTP_302_FOUND)


# EXCLUIR UNIDADE
@router.get("/delete/{unit_id}")
def delete_unit(
    request: Request,
    unit_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    unidade = db.query(Unit).filter(Unit.id == unit_id).first()
    if unidade:
        db.delete(unidade)
        db.commit()
        registrar_log(db, usuario=user, acao=f"Excluiu unidade ID {unit_id}", ip=ip)

    return RedirectResponse("/units", status_code=HTTP_302_FOUND)
