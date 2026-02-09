from itertools import product
from fastapi.responses import RedirectResponse
from fastapi import APIRouter, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Product, Unit, Category, Movement, User, Stock, Item
from database import get_db
from datetime import datetime
from dependencies import get_current_user, registrar_log
from starlette.status import HTTP_302_FOUND

router = APIRouter(prefix="/movements", tags=["Movimentações"])
templates = Jinja2Templates(directory="templates")


@router.get("/")
def listar_movimentacoes(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    movements = db.query(Movement).order_by(Movement.data.desc()).all()

    return templates.TemplateResponse(
        "movements_list.html",
        {"request": request, "movements": movements, "user": user}
    )


@router.get("/nova")
def nova_movimentacao_form(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")
    
    products = db.query(Product).all()
    units = db.query(Unit).all()
    categories = db.query(Category).all()

    # Envia type_id para agrupamento no frontend
    products_js = [
        {
            "id": p.id,
            "type_id": p.type_id,
            "type_name": p.type.nome,
            "category_id": p.category_id,
            "controla_por_serie": p.controla_por_serie
        }
        for p in products
    ]

    return templates.TemplateResponse(
        "movement_form.html",
        {"request": request, "products": products_js, "units": units, "categories": categories, "user": user}
    )


@router.post("/")
def movimentacoes_submit(
    request: Request,

    type_id: int = Form(...),
    unit_origem_id: int = Form(None),
    unit_destino_id: int = Form(...),
    item_id: int = Form(None),
    tipo: str = Form(...),
    quantidade: int = Form(1),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
    username: str = Depends(get_current_user)  # retorna "admin", por exemplo
):
    if not username:
        return RedirectResponse("/login")

    # 🔹 Recupera o usuário real do DB para pegar o ID
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return {"error": "Usuário não encontrado"}

    product = None
    item = None

    if item_id:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            return {"error": "Item físico não encontrado"}
        product = item.product
        unit_origem_id = item.unit_id
        quantidade = 1
    else:
        product = db.query(Product).filter(Product.type_id == type_id).first()
        if not product:
            return {"error": "Produto não encontrado"}
        if product.controla_por_serie:
            return {"error": "Item físico obrigatório para produtos controlados por série"}
        if not unit_origem_id:
            return {"error": "Unidade de origem obrigatória"}

    movimento = Movement(
        product_id=product.id,
        unit_origem_id=unit_origem_id,
        unit_destino_id=unit_destino_id,
        quantidade=quantidade,
        tipo=tipo,
        observacao=observacao,
        user_id=user.id,  # ✅ agora é integer
        data=datetime.utcnow()
    )

    if product.controla_por_serie and item and tipo in ["SAIDA", "TRANSFERENCIA"]:
        item.unit_id = unit_destino_id
        db.add(item)

    if not product.controla_por_serie:
        stock = db.query(Stock).filter(
            Stock.product_id == product.id,
            Stock.unit_id == unit_origem_id
        ).first()
        if not stock:
            return {"error": "Estoque não encontrado para este produto e unidade"}
        if tipo in ["SAIDA", "TRANSFERENCIA"]:
            stock.quantidade -= quantidade
        elif tipo == "ENTRADA":
            stock.quantidade += quantidade
        db.add(stock)

    db.add(movimento)
    db.commit()

    registrar_log(
    db=db,
    usuario=user.username,  # ✅ string, não objeto
    acao=f"Registrou movimentação {tipo} do produto {product.name}",
    ip=request.client.host  # opcional, se registrar_log aceitar
)

    # 🔹 Redireciona para a lista de movimentações
    return RedirectResponse(url="/movements/", status_code=HTTP_302_FOUND)




@router.get("/movements/stock/type/{type_id}")
def get_product_stock(type_id: int, db: Session = Depends(get_db)):
    result = []

    # Produtos sem série (Stock)
    stocks = (
        db.query(Stock)
        .join(Product)
        .join(Unit)
        .filter(Product.type_id == type_id, Stock.quantidade > 0)
        .all()
    )

    for s in stocks:
        result.append({
            "unit_id": s.unit.id,
            "unit_name": s.unit.name,
            "quantidade": s.quantidade
        })

    # Produtos com série (Item)
    items = (
        db.query(Item.unit_id, Unit.name, func.count(Item.id).label("quantidade"))
        .join(Product)
        .join(Unit, Item.unit_id == Unit.id)
        .filter(Product.type_id == type_id)
        .group_by(Item.unit_id, Unit.name)
        .all()
    )

    for i in items:
        if not any(r["unit_id"] == i.unit_id for r in result):
            result.append({
                "unit_id": i.unit_id,
                "unit_name": i.name,
                "quantidade": i.quantidade
            })

    return result


@router.get("/items/{type_id}")
def get_product_items(type_id: int, db: Session = Depends(get_db)):
    items = (
        db.query(Item)
        .join(Product)
        .join(Unit)
        .filter(Product.type_id == type_id)
        .all()
    )

    return [
        {
            "id": i.id,
            "tombo": i.tombo,
            "num": i.num_tombo_ou_serie,
            "unit_id": i.unit_id,
            "unit_name": i.unit.name
        }
        for i in items
    ]


@router.get("/items/search")
def search_items(
    product_id: int,
    tipo: str,  # TOMBO | SERIE
    q: str = "",
    db: Session = Depends(get_db)
):
    is_tombo = tipo == "TOMBO"

    items = (
        db.query(Item)
        .join(Unit)
        .filter(
            Item.product_id == product_id,
            Item.tombo == is_tombo,
            Item.num_tombo_ou_serie.ilike(f"%{q}%")
        )
        .limit(20)
        .all()
    )

    return [
        {
            "id": i.id,
            "text": i.num_tombo_ou_serie,
            "unit_id": i.unit_id,
            "unit_name": i.unit.name
        }
        for i in items
    ]
