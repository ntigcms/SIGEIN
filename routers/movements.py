from fastapi import APIRouter, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models import Product, Unit, Category, Movement, User, Stock, Item
from database import get_db
from datetime import datetime
from dependencies import get_current_user, registrar_log

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/")
def listar_movimentacoes(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    movements = (
        db.query(Movement)
        .order_by(Movement.data.desc())
        .all()
    )

    return templates.TemplateResponse(
        "movements_list.html",
        {
            "request": request,
            "movements": movements
        }
    )


@router.get("/nova")
def nova_movimentacao_form(
    request: Request,
    db: Session = Depends(get_db)
):
    products = db.query(Product).all()
    units = db.query(Unit).all()
    categories = db.query(Category).all()

    products_js = [
    {
        "id": p.id,
        "type_name": p.type.nome,
        "category_id": p.category_id,
        "controla_por_serie": p.controla_por_serie
    }
    for p in products
]

    return templates.TemplateResponse(
        "movement_form.html",
        {
            "request": request,
            "products": products_js,
            "units": units,
            "categories": categories
        }
    )


@router.post("/")
def movimentacoes_submit(
    product_id: int = Form(...),
    unit_destino_id: int = Form(...),
    tipo: str = Form(...),
    quantidade: int = Form(...),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return {"error": "Produto não encontrado"}

    movimento = Movement(
        product_id=product.id,
        unit_origem_id=product.unit_id,
        unit_destino_id=unit_destino_id,
        quantidade=quantidade,
        tipo=tipo,
        observacao=observacao,
        user_id=user.id,
        data=datetime.utcnow()
    )

    if tipo in ["SAIDA", "TRANSFERENCIA", "AJUSTE"]:
        product.unit_id = unit_destino_id

    db.add(movimento)
    db.commit()

    registrar_log(
        db=db,
        user_id=user.id,
        acao=f"Registrou movimentação {tipo} do produto {product.name}"
    )

    return {"success": True}

@router.get("/movements/stock/{product_id}")
def get_product_stock(product_id: int, db: Session = Depends(get_db)):
    result = []

    # Primeiro: produtos sem série (Stock)
    stocks = (
        db.query(Stock)
        .join(Unit)
        .filter(Stock.product_id == product_id, Stock.quantidade > 0)
        .all()
    )

    for s in stocks:
        result.append({
            "unit_id": s.unit.id,
            "unit_name": s.unit.name,
            "quantidade": s.quantidade
        })

    # Segundo: produtos com série (Item)
    items = (
        db.query(Item.unit_id, Unit.name, func.count(Item.id).label("quantidade"))
        .join(Unit, Item.unit_id == Unit.id)
        .filter(Item.product_id == product_id)
        .group_by(Item.unit_id, Unit.name)
        .all()
    )

    for i in items:
        # Evita duplicar unidades já adicionadas pelo Stock
        if not any(r["unit_id"] == i.unit_id for r in result):
            result.append({
                "unit_id": i.unit_id,
                "unit_name": i.name,
                "quantidade": i.quantidade
            })

    return result