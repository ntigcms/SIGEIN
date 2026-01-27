from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Category
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_302_FOUND

router = APIRouter(prefix="/categories", tags=["Categorias"])
templates = Jinja2Templates(directory="templates")


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
        {"request": request, "action": "add"}
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
