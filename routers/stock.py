from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, registrar_log
from models import Stock, Product, Unit
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/stock", tags=["Stock"])
templates = Jinja2Templates(directory="templates")


@router.get("/")
def list_stock(request: Request, db: Session = Depends(get_db),
               user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    stock = db.query(Stock).all()
    return templates.TemplateResponse(
        "stock_list.html",
        {"request": request, "stock": stock, "user": user}
    )


@router.get("/add")
def add_stock_form(request: Request, db: Session = Depends(get_db),
                   user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    products = db.query(Product).filter(Product.controla_por_serie == False).all()
    units = db.query(Unit).all()

    return templates.TemplateResponse(
        "stock_form.html",
        {
            "request": request,
            "products": products,
            "units": units,
            "user": user
        }
    )


@router.post("/add")
def add_stock(
    request: Request,
    product_id: int = Form(...),
    unit_id: int = Form(...),
    quantidade: int = Form(...),
    quantidade_minima: int = Form(0),
    localizacao: str = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    stock = Stock(
        product_id=product_id,
        unit_id=unit_id,
        quantidade=quantidade,
        quantidade_minima=quantidade_minima,
        localizacao=localizacao
    )

    db.add(stock)
    db.commit()

    registrar_log(
        db,
        usuario=user,
        acao=f"Entrada de estoque do produto ID {product_id}",
        ip=request.client.host
    )

    return RedirectResponse("/stock", status_code=HTTP_302_FOUND)

@router.get("/stock/{product_id}")
def get_stock_by_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    stocks = (
        db.query(Stock)
        .filter(Stock.product_id == product_id)
        .all()
    )

    return [
        {
            "unit_id": s.unit_id,
            "unit_name": s.unit.name,
            "quantidade": s.quantidade
        }
        for s in stocks
    ]
