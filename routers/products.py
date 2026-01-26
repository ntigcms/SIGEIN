from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, registrar_log
from models import Product, EquipmentType, Brand
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/products", tags=["Products"])
templates = Jinja2Templates(directory="templates")


@router.get("/")
def list_products(request: Request, db: Session = Depends(get_db),
                  user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    products = db.query(Product).all()
    return templates.TemplateResponse(
        "products_list.html",
        {"request": request, "products": products, "user": user}
    )


@router.get("/add")
def add_product_form(request: Request, db: Session = Depends(get_db),
                     user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    types = db.query(EquipmentType).all()
    brands = db.query(Brand).all()

    return templates.TemplateResponse(
        "product_form.html",
        {
            "request": request,
            "action": "add",
            "types": types,
            "brands": brands,
            "product": None,
            "user": user
        }
    )


@router.post("/add")
def add_product(
    request: Request,
    name: str = Form(...),
    type_id: int = Form(...),
    brand_id: int = Form(...),
    model: str = Form(None),
    description: str = Form(None),
    controla_por_serie: bool = Form(True),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    product = Product(
        name=name,
        type_id=type_id,
        brand_id=brand_id,
        model=model,
        description=description,
        controla_por_serie=controla_por_serie
    )

    db.add(product)
    db.commit()

    registrar_log(
        db,
        usuario=user,
        acao=f"Cadastrou produto: {name}",
        ip=request.client.host
    )

    return RedirectResponse("/products", status_code=HTTP_302_FOUND)
