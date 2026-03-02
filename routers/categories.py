from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Category
from shared_templates import templates
from starlette.status import HTTP_302_FOUND

router = APIRouter(prefix="/categories", tags=["Categorias"])


@router.get("/")
def list_categories(request: Request, db: Session = Depends(get_db)):
    categories = db.query(Category).order_by(Category.nome).all()
    return templates.TemplateResponse(
        "categories_list.html",
        {"request": request, "categories": categories}
    )


@router.get("/add")
def add_category_form(request: Request):
    return templates.TemplateResponse(
        "category_form.html",
        {"request": request, "action": "add", "category": None}
    )


@router.post("/add")
def add_category(
    nome: str = Form(...),
    descricao: str = Form(None),
    db: Session = Depends(get_db)
):
    category = Category(nome=nome, descricao=descricao)
    db.add(category)
    db.commit()
    return RedirectResponse("/categories", status_code=HTTP_302_FOUND)


@router.get("/edit/{category_id}")
def edit_category_form(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        return RedirectResponse("/categories")
    return templates.TemplateResponse(
        "category_form.html",
        {"request": request, "action": "edit", "category": category}
    )


@router.post("/edit/{category_id}")
def edit_category(
    category_id: int,
    nome: str = Form(...),
    descricao: str = Form(None),
    db: Session = Depends(get_db)
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if category:
        category.nome = nome
        category.descricao = descricao
        db.commit()
    return RedirectResponse("/categories", status_code=HTTP_302_FOUND)


@router.get("/delete/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if category:
        db.delete(category)
        db.commit()
    return RedirectResponse("/categories", status_code=HTTP_302_FOUND)
