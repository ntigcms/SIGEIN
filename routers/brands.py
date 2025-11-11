from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, registrar_log
from models import Brand
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/brands", tags=["Brands"])
templates = Jinja2Templates(directory="templates")


# LISTAR MARCAS
@router.get("/")
def list_brands(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    brands = db.query(Brand).all()
    return templates.TemplateResponse(
        "brands.html",
        {"request": request, "brands": brands, "user": user}
    )


# FORMULÁRIO DE ADIÇÃO DE MARCA
@router.get("/add")
def add_brand_form(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        "brand_add.html",
        {"request": request, "user": user, "action": "add"}
    )


# ADICIONAR MARCA
@router.post("/add")
def add_brand(
    request: Request,
    nome: str = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    nova_marca = Brand(nome=nome)

    db.add(nova_marca)
    db.commit()
    db.refresh(nova_marca)

    registrar_log(db, usuario=user, acao=f"Cadastrou marca: {nome}", ip=ip)
    return RedirectResponse("/brands", status_code=HTTP_302_FOUND)


# FORMULÁRIO DE EDIÇÃO DE MARCA
@router.get("/edit/{brand_id}")
def edit_brand_form(
    brand_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    marca = db.query(Brand).filter(Brand.id == brand_id).first()
    if not marca:
        return RedirectResponse("/brands")

    return templates.TemplateResponse(
        "brand_add.html",
        {"request": request, "user": user, "marca": marca, "action": "edit"}
    )


# EDITAR MARCA
@router.post("/edit/{brand_id}")
def edit_brand(
    request: Request,
    brand_id: int,
    nome: str = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    marca = db.query(Brand).filter(Brand.id == brand_id).first()
    if marca:
        marca.nome = nome
        db.commit()
        registrar_log(db, usuario=user, acao=f"Editou marca ID {brand_id}", ip=ip)

    return RedirectResponse("/brands", status_code=HTTP_302_FOUND)


# EXCLUIR MARCA
@router.get("/delete/{brand_id}")
def delete_brand(
    request: Request,
    brand_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    marca = db.query(Brand).filter(Brand.id == brand_id).first()
    if marca:
        db.delete(marca)
        db.commit()
        registrar_log(db, usuario=user, acao=f"Excluiu marca ID {brand_id}", ip=ip)

    return RedirectResponse("/brands", status_code=HTTP_302_FOUND)
