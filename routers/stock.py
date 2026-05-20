from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session, aliased, joinedload
from sqlalchemy import func, literal, Integer, case
from services.audit_service import AuditService

from database import get_db
from dependencies import get_current_user, registrar_log
from models import EquipmentType, Stock, Product, Unit, Unidade, Item
from services.movement_form_data import build_movement_form_context
from templating import templates

router = APIRouter(prefix="/stock", tags=["Stock"])


@router.get("/")
def list_stock(request: Request, db: Session = Depends(get_db),
               user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    stock = db.query(Stock).all()
    movement_ctx = build_movement_form_context(db)
    return templates.TemplateResponse(
        "stock_list.html",
        {
            "request": request,
            "stock": stock,
            "user": user,
            "hide_app_header": True,
            "movement_products": movement_ctx["products"],
            "movement_units": movement_ctx["units"],
            "movement_categories": movement_ctx["categories"],
        },
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
            "user": user,
            "hide_app_header": True,
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

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse("/stock/", status_code=HTTP_302_FOUND)

    stock = Stock(
        product_id=product_id,
        unit_id=unit_id,
        municipio_id=product.municipio_id,
        orgao_id=product.orgao_id,
        quantidade=quantidade,
        quantidade_minima=quantidade_minima,
        localizacao=localizacao,
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
        .options(joinedload(Stock.unit))
        .filter(Stock.product_id == product_id)
        .all()
    )

    return [
        {
            "unit_id": s.unit_id,
            "unit_name": s.unit.nome if s.unit else None,
            "quantidade": s.quantidade
        }
        for s in stocks
    ]

@router.get("/overview")
def stock_overview(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return []

    resultado = []

    # ✅ Agrupa produtos por type_id + unit para evitar duplicatas
    agrupamentos = {}

    produtos = db.query(Product).all()

    for p in produtos:

        # 🔹 PRODUTO CONTROLADO POR SÉRIE
        # Agrupa por product_id + unit_id para que cada produto tenha sua própria linha
        # (permite movimentar 1 item sem confundir com itens de outros produtos do mesmo tipo)
        if p.controla_por_serie:
            items = (
                db.query(
                    Unidade.id.label("unit_id"),
                    Unidade.nome.label("unit_name"),
                    func.count(Item.id).label("quantidade")
                )
                .select_from(Item)
                .join(Unidade, Unidade.id == Item.unit_id)
                .filter(Item.product_id == p.id)
                .group_by(Unidade.id, Unidade.nome)
                .all()
            )

            for i in items:
                # Chave única: product_id + unit_id (cada produto = linha separada)
                chave = f"{p.id}_{i.unit_id}"
                
                if chave not in agrupamentos:
                    agrupamentos[chave] = {
                        "type_id": p.type_id,
                        "product_id": p.id,
                        "product_type": p.type.nome if p.type else None,
                        "product_name": p.name,
                        "unit_id": i.unit_id,
                        "unit_name": i.unit_name,
                        "quantidade": 0,
                        "quantidade_minima": 0,
                        "controla_por_serie": True,
                        "product_ids": [p.id]
                    }
                
                agrupamentos[chave]["quantidade"] += i.quantidade

        # 🔹 PRODUTO NORMAL (USA STOCK)
        else:
            stocks = (
                db.query(Stock)
                .options(joinedload(Stock.unit))
                .filter(Stock.product_id == p.id)
                .all()
            )

            for s in stocks:
                chave = f"{p.id}_{s.unit_id}"
                
                if chave not in agrupamentos:
                    agrupamentos[chave] = {
                        "type_id": p.type_id,
                        "product_id": p.id,
                        "product_type": p.type.nome if p.type else None,
                        "product_name": p.name,
                        "unit_id": s.unit_id,
                        "unit_name": s.unit.nome if s.unit else None,
                        "quantidade": 0,
                        "quantidade_minima": s.quantidade_minima or 0,
                        "controla_por_serie": False,
                        "product_ids": [p.id]
                    }
                
                agrupamentos[chave]["quantidade"] += s.quantidade
                agrupamentos[chave]["quantidade_minima"] = max(
                    agrupamentos[chave]["quantidade_minima"], 
                    s.quantidade_minima or 0
                )

    # ✅ Converte agrupamentos em lista e calcula status
    for item in agrupamentos.values():
        status = "OK"
        if item["quantidade"] <= 0:
            status = "ZERADO"
        elif item["quantidade"] <= item["quantidade_minima"]:
            status = "CRITICO"
        
        item["status"] = status
        resultado.append(item)

    return resultado


@router.get("/items-by-type")
def items_by_type(
    type_id: int = None,
    product_id: int = None,
    unit_id: int = None,
    unit_name: str = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Retorna itens/estoque do produto na unidade. Prefira unit_id (evita falha com acentos no nome)."""
    if not user:
        return {"error": "Não autenticado"}

    unidade = None
    if unit_id:
        unidade = db.query(Unidade).filter(Unidade.id == unit_id).first()
    elif unit_name:
        unidade = db.query(Unidade).filter(Unidade.nome == unit_name).first()
    if not unidade:
        return {"error": "Unidade não encontrada"}

    if product_id:
        product_sample = db.query(Product).filter(Product.id == product_id).first()
    else:
        product_sample = db.query(Product).filter(Product.type_id == type_id).first()

    if not product_sample:
        return {"error": "Produto não encontrado"}

    unit_label = unidade.nome

    if product_sample.controla_por_serie:
        items = (
            db.query(Item)
            .filter(
                Item.product_id == product_sample.id,
                Item.unit_id == unidade.id,
            )
            .all()
        )

        return {
            "controla_por_serie": True,
            "product_id": product_sample.id,
            "unit_id": unidade.id,
            "unit_name": unit_label,
            "product_type": product_sample.type.nome if product_sample.type else None,
            "product_name": product_sample.name,
            "items": [
                {
                    "id": i.id,
                    "num": i.num_tombo_ou_serie,
                    "unit": i.unit.nome if i.unit else unit_label,
                    "tombo": i.tombo,
                }
                for i in items
            ],
        }

    filter_expr = (Product.id == product_sample.id) if product_id else (Product.type_id == type_id)
    stocks = (
        db.query(Stock)
        .join(Product, Product.id == Stock.product_id)
        .filter(filter_expr, Stock.unit_id == unidade.id)
        .all()
    )

    total_quantidade = sum(s.quantidade for s in stocks)
    max_minimo = max((s.quantidade_minima or 0 for s in stocks), default=0)

    return {
        "controla_por_serie": False,
        "product_id": product_sample.id,
        "unit_id": unidade.id,
        "unit_name": unit_label,
        "product_type": product_sample.type.nome if product_sample.type else None,
        "product_brand": product_sample.brand.nome if product_sample.brand else None,
        "product_model": product_sample.model,
        "stock": [
            {
                "unit": unit_label,
                "quantidade": total_quantidade,
                "minimo": max_minimo,
            }
        ],
    }


@router.get("/product/{product_id}")
def stock_by_product(
    product_id: int,
    unit_name: str = None,
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        return {"error": "Produto não encontrado"}

    if product.controla_por_serie:
        query = db.query(Item).join(Unidade, Unidade.id == Item.unit_id).filter(Item.product_id == product_id)
        
        if unit_name:
            query = query.filter(Unidade.nome == unit_name)
        
        items = query.all()

        return {
            "controla_por_serie": True,
            "product_type": product.type.nome if product.type else None,
            "product_name": product.name,  # ✅ adicione
            "product_brand": product.brand.nome if product.brand else None,  # ✅ adicione
            "product_model": product.model,  # ✅ adicione
            "items": [
                {
                    "id": i.id,
                    "num": i.num_tombo_ou_serie,
                    "unit": i.unit.nome if i.unit else None,
                    "tombo": i.tombo
                } for i in items
            ]
        }

    stocks = (
        db.query(Stock)
        .options(joinedload(Stock.unit))
        .filter(Stock.product_id == product_id)
        .all()
    )

    return {
        "controla_por_serie": False,
        "product_type": product.type.nome if product.type else None,  # ✅ adicione
        "product_name": product.name,  # ✅ adicione
        "product_brand": product.brand.nome if product.brand else None,  # ✅ adicione
        "product_model": product.model,  # ✅ adicione
        "stock": [
            {
                "unit": s.unit.nome if s.unit else None,
                "quantidade": s.quantidade,
                "minimo": s.quantidade_minima
            } for s in stocks
        ]
    }

@router.get("/item/{item_id}")
def get_item_details(
    item_id: int,
    db: Session = Depends(get_db)
):
    """Retorna detalhes completos de um item para visualização"""
    item = db.query(Item).filter(Item.id == item_id).first()
    
    if not item:
        return {"error": "Item não encontrado"}
    
    return {
        "id": item.id,
        "nome": item.product.name if item.product else None,
        "tipo": item.product.type.nome if item.product and item.product.type else None,
        "marca": item.product.brand.nome if item.product and item.product.brand else None,
        "modelo": item.product.model if item.product else None,
        "estado": item.estado.nome if item.estado else None,
        "status": item.status,
        "unidade": item.unit.nome if item.unit else None,
        "tombo": item.tombo,
        "numero": item.num_tombo_ou_serie,
        "observacao": item.observacao,
        "data_aquisicao": str(item.data_aquisicao) if item.data_aquisicao else None,
        "valor_aquisicao": item.valor_aquisicao,
        "garantia_ate": item.garantia_ate
    }

@router.get("/alerts")
def stock_alerts(db: Session = Depends(get_db)):
    alerts = (
        db.query(Stock)
        .options(joinedload(Stock.product), joinedload(Stock.unit))
        .filter(Stock.quantidade <= Stock.quantidade_minima)
        .all()
    )

    return [
        {
            "product": s.product.name,
            "unit": s.unit.nome if s.unit else None,
            "quantidade": s.quantidade,
            "minimo": s.quantidade_minima
        }
        for s in alerts
    ]

@router.get("/audit")
def audit_stock(db: Session = Depends(get_db),
                user: str = Depends(get_current_user)):

    if not user:
        return []

    return AuditService.auditar_tudo(db)