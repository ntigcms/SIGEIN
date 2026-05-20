from typing import List, Optional

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session, joinedload
from database import get_db
from dependencies import get_current_user, registrar_log
from models import Brand, Category, EquipmentType
from templating import templates

router = APIRouter(prefix="/brands", tags=["Brands"])


def _categories_with_types(db: Session):
    return (
        db.query(Category)
        .options(joinedload(Category.equipment_types))
        .filter(Category.ativo == True)
        .order_by(Category.nome)
        .all()
    )


def _sync_brand_types(db: Session, marca: Brand, type_ids: List[int]) -> None:
    if not type_ids:
        marca.equipment_types = []
        return
    tipos = db.query(EquipmentType).filter(EquipmentType.id.in_(type_ids)).all()
    if len(tipos) != len(set(type_ids)):
        raise HTTPException(status_code=400, detail="Um ou mais tipos selecionados são inválidos.")
    marca.equipment_types = tipos


def _brand_display(brand: Brand) -> dict:
    tipos = sorted(brand.equipment_types, key=lambda t: t.nome)
    cats = sorted({t.category.nome for t in tipos if t.category}, key=str.lower)
    return {
        "categorias": ", ".join(cats) if cats else "—",
        "tipos": ", ".join(t.nome for t in tipos) if tipos else "—",
    }


# LISTAR MARCAS
@router.get("/")
def list_brands(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    brands = (
        db.query(Brand)
        .options(
            joinedload(Brand.equipment_types).joinedload(EquipmentType.category),
        )
        .order_by(Brand.nome)
        .all()
    )
    brands_view = [{"marca": b, **_brand_display(b)} for b in brands]

    categorias_set = set()
    tipos_set = set()
    for b in brands:
        for t in b.equipment_types:
            tipos_set.add(t.nome)
            if t.category:
                categorias_set.add(t.category.nome)
    categorias = sorted(categorias_set, key=str.lower)
    tipos = sorted(tipos_set, key=str.lower)

    return templates.TemplateResponse(
        "brands.html",
        {
            "request": request,
            "brands": brands_view,
            "categorias": categorias,
            "tipos": tipos,
            "user": user,
            "hide_app_header": True,
        },
    )


# FORMULÁRIO DE ADIÇÃO DE MARCA
@router.get("/add")
def add_brand_form(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        "brand_add.html",
        {
            "request": request,
            "user": user,
            "action": "add",
            "categories": _categories_with_types(db),
            "selected_type_ids": [],
        },
    )


# ADICIONAR MARCA
@router.post("/add")
def add_brand(
    request: Request,
    nome: str = Form(...),
    type_ids: Optional[List[int]] = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    ids = type_ids or []
    if not ids:
        raise HTTPException(status_code=400, detail="Selecione ao menos um tipo de equipamento.")

    ip = request.client.host
    nova_marca = Brand(nome=nome.strip())
    db.add(nova_marca)
    db.flush()
    _sync_brand_types(db, nova_marca, ids)
    db.commit()

    registrar_log(db, usuario=user, acao=f"Cadastrou marca: {nome}", ip=ip)
    return RedirectResponse("/brands", status_code=HTTP_302_FOUND)


# FORMULÁRIO DE EDIÇÃO DE MARCA
@router.get("/edit/{brand_id}")
def edit_brand_form(
    brand_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    marca = (
        db.query(Brand)
        .options(joinedload(Brand.equipment_types))
        .filter(Brand.id == brand_id)
        .first()
    )
    if not marca:
        return RedirectResponse("/brands")

    return templates.TemplateResponse(
        "brand_add.html",
        {
            "request": request,
            "user": user,
            "marca": marca,
            "action": "edit",
            "categories": _categories_with_types(db),
            "selected_type_ids": [t.id for t in marca.equipment_types],
        },
    )


# EDITAR MARCA
@router.post("/edit/{brand_id}")
def edit_brand(
    request: Request,
    brand_id: int,
    nome: str = Form(...),
    type_ids: Optional[List[int]] = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    ids = type_ids or []
    if not ids:
        raise HTTPException(status_code=400, detail="Selecione ao menos um tipo de equipamento.")

    ip = request.client.host
    marca = db.query(Brand).filter(Brand.id == brand_id).first()
    if marca:
        marca.nome = nome.strip()
        _sync_brand_types(db, marca, ids)
        db.commit()
        registrar_log(db, usuario=user, acao=f"Editou marca ID {brand_id}", ip=ip)

    return RedirectResponse("/brands", status_code=HTTP_302_FOUND)


# EXCLUIR MARCA
@router.get("/delete/{brand_id}")
def delete_brand(
    request: Request,
    brand_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
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
