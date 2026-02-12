from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, literal, Integer, case

from database import get_db
from dependencies import get_current_user, registrar_log
from models import EquipmentType, Stock, Product, Unit, Item
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

@router.get("/overview")
def stock_overview(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return []

    resultado = []

    produtos = db.query(Product).all()

    for p in produtos:

        # 🔹 PRODUTO CONTROLADO POR SÉRIE
        if p.controla_por_serie:
            items = (
                db.query(
                    Unit.name.label("unit_name"),
                    func.count(Item.id).label("quantidade")
                )
                .join(Unit, Unit.id == Item.unit_id)
                .filter(Item.product_id == p.id)
                .group_by(Unit.name)
                .all()
            )

            for i in items:
                resultado.append({
                    "product_id": p.id,
                    "product_name": p.name,
                    "product_type": p.type.nome,
                    "unit_name": i.unit_name,
                    "quantidade": i.quantidade,
                    "quantidade_minima": 0,
                    "controla_por_serie": True,
                    "status": "OK" if i.quantidade > 0 else "ZERADO"
                })

        # 🔹 PRODUTO NORMAL (USA STOCK)
        else:
            stocks = (
                db.query(Stock)
                .join(Unit)
                .filter(Stock.product_id == p.id)
                .all()
            )

            for s in stocks:
                status = "OK"
                if s.quantidade <= 0:
                    status = "ZERADO"
                elif s.quantidade <= (s.quantidade_minima or 0):
                    status = "CRITICO"

                resultado.append({
                    "product_id": p.id,
                    "product_name": p.name,
                    "product_type": p.type.nome,
                    "unit_name": s.unit.name,
                    "quantidade": s.quantidade,
                    "quantidade_minima": s.quantidade_minima,
                    "controla_por_serie": False,
                    "status": status
                })

    return resultado


@router.get("/product/{product_id}")
def stock_by_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        return {"error": "Produto não encontrado"}

    if product.controla_por_serie:
        items = (
            db.query(Item)
            .join(Unit)
            .filter(Item.product_id == product_id)
            .all()
        )

        return {
            "controla_por_serie": True,
            "items": [
                {
                    "id": i.id,
                    "num": i.num_tombo_ou_serie,
                    "unit": i.unit.name
                } for i in items
            ]
        }

    stocks = (
        db.query(Stock)
        .join(Unit)
        .filter(Stock.product_id == product_id)
        .all()
    )

    return {
        "controla_por_serie": False,
        "stock": [
            {
                "unit": s.unit.name,
                "quantidade": s.quantidade,
                "minimo": s.quantidade_minima
            } for s in stocks
        ]
    }

@router.get("/alerts")
def stock_alerts(db: Session = Depends(get_db)):
    alerts = (
        db.query(Stock)
        .join(Product)
        .filter(Stock.quantidade <= Stock.quantidade_minima)
        .all()
    )

    return [
        {
            "product": s.product.name,
            "unit": s.unit.name,
            "quantidade": s.quantidade,
            "minimo": s.quantidade_minima
        }
        for s in alerts
    ]
