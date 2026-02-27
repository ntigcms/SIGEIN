from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, literal, Integer, case
from services.audit_service import AuditService

from database import get_db
from dependencies import get_current_user, registrar_log
from models import EquipmentType, Stock, Product, Unidade, Item, User
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_


router = APIRouter(prefix="/stock", tags=["Stock"])
templates = Jinja2Templates(directory="templates")

PERFIL_MASTER = "master"
PERFIL_GESTOR_MUNICIPAL = "admin_municipal"


def _user_obj(db: Session, user: str):
    if not user:
        return None
    return db.query(User).filter(User.email == user).first()


@router.get("/")
def list_stock(request: Request, db: Session = Depends(get_db),
               user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    user_obj = _user_obj(db, user)
    perfil = getattr(user_obj, "perfil", None) if user_obj else None

    q = db.query(Stock).join(Product)
    if perfil == PERFIL_MASTER:
        pass
    elif perfil == PERFIL_GESTOR_MUNICIPAL:
        q = q.filter(or_(Stock.municipio_id == user_obj.municipio_id, Product.municipio_id == user_obj.municipio_id))
    else:
        q = q.filter(Stock.unit_id == user_obj.unidade_id)
    stock = q.all()
    return templates.TemplateResponse(
        "stock_list.html",
        {"request": request, "stock": stock, "user": user}
    )


@router.get("/add")
def add_stock_form(request: Request, db: Session = Depends(get_db),
                   user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    user_obj = _user_obj(db, user)
    perfil = getattr(user_obj, "perfil", None) if user_obj else None

    products = db.query(Product).filter(Product.controla_por_serie == False)
    units = db.query(Unidade)
    if perfil == PERFIL_MASTER:
        pass
    elif perfil == PERFIL_GESTOR_MUNICIPAL:
        products = products.filter(Product.municipio_id == user_obj.municipio_id)
        # unidades do município: via orgaos
        from models import Orgao
        units = units.join(Orgao, Unidade.orgao_id == Orgao.id).filter(Orgao.municipio_id == user_obj.municipio_id)
    else:
        products = products.filter(or_(Product.unidade_id == user_obj.unidade_id, (Product.unidade_id.is_(None)) & (Product.orgao_id == user_obj.orgao_id)))
        units = units.filter(Unidade.id == user_obj.unidade_id)

    products = products.all()
    units = units.order_by(Unidade.nome).all()

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

    user_obj = _user_obj(db, user)
    perfil = getattr(user_obj, "perfil", None) if user_obj else None

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse("/stock/add")
    unidade = db.query(Unidade).filter(Unidade.id == unit_id).first()
    if not unidade:
        return RedirectResponse("/stock/add")

    if perfil == PERFIL_MASTER:
        pass
    elif perfil == PERFIL_GESTOR_MUNICIPAL:
        from models import Orgao
        orgao = db.query(Orgao).filter(Orgao.id == unidade.orgao_id).first()
        if not orgao or orgao.municipio_id != user_obj.municipio_id:
            return RedirectResponse("/stock/add")
    else:
        if unit_id != user_obj.unidade_id:
            return RedirectResponse("/stock/add")

    stock = Stock(
        product_id=product_id,
        unit_id=unit_id,
        municipio_id=product.municipio_id,
        orgao_id=product.orgao_id,
        quantidade=quantidade,
        quantidade_minima=quantidade_minima,
        localizacao=localizacao
    )
    db.add(stock)
    db.commit()
    registrar_log(db, usuario=user, acao=f"Entrada de estoque do produto ID {product_id}", ip=request.client.host)
    return RedirectResponse("/stock", status_code=HTTP_302_FOUND)


@router.get("/stock/{product_id}")
def get_stock_by_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    stocks = db.query(Stock).filter(Stock.product_id == product_id).all()
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

    user_obj = _user_obj(db, user)
    produtos = db.query(Product).all()
    if user_obj and getattr(user_obj, "perfil", None) != "master":
        produtos = [p for p in produtos if p.orgao_id == user_obj.orgao_id]

    resultado = []
    agrupamentos = {}

    for p in produtos:
        if p.controla_por_serie:
            items = (
                db.query(
                    Unidade.id.label("unit_id"),
                    Unidade.nome.label("unit_name"),
                    func.count(Item.id).label("quantidade")
                )
                .join(Unidade, Unidade.id == Item.unit_id)
                .filter(Item.product_id == p.id)
                .group_by(Unidade.id, Unidade.nome)
                .all()
            )
            for i in items:
                chave = f"{p.type_id}_{i.unit_id}"
                if chave not in agrupamentos:
                    agrupamentos[chave] = {
                        "type_id": p.type_id,
                        "product_type": p.type.nome if p.type else None,
                        "unit_id": i.unit_id,
                        "unit_name": i.unit_name,
                        "quantidade": 0,
                        "quantidade_minima": 0,
                        "controla_por_serie": True,
                        "product_ids": []
                    }
                agrupamentos[chave]["quantidade"] += i.quantidade
                if p.id not in agrupamentos[chave]["product_ids"]:
                    agrupamentos[chave]["product_ids"].append(p.id)
        else:
            for s in db.query(Stock).filter(Stock.product_id == p.id).all():
                chave = f"{p.type_id}_{s.unit_id}"
                if chave not in agrupamentos:
                    agrupamentos[chave] = {
                        "type_id": p.type_id,
                        "product_type": p.type.nome if p.type else None,
                        "unit_id": s.unit_id,
                        "unit_name": s.unit.nome if s.unit else None,
                        "quantidade": 0,
                        "quantidade_minima": s.quantidade_minima or 0,
                        "controla_por_serie": False,
                        "product_ids": []
                    }
                agrupamentos[chave]["quantidade"] += s.quantidade
                agrupamentos[chave]["quantidade_minima"] = max(
                    agrupamentos[chave]["quantidade_minima"], s.quantidade_minima or 0
                )
                if p.id not in agrupamentos[chave]["product_ids"]:
                    agrupamentos[chave]["product_ids"].append(p.id)

    for item in agrupamentos.values():
        item["status"] = "OK" if item["quantidade"] > item["quantidade_minima"] else ("ZERADO" if item["quantidade"] <= 0 else "CRITICO")
        resultado.append(item)
    return resultado


@router.get("/items-by-type")
def items_by_type(
    type_id: int,
    unit_name: str,
    db: Session = Depends(get_db)
):
    """Retorna todos os itens de um tipo de produto em uma unidade específica (Unidade.nome)"""
    product_sample = db.query(Product).filter(Product.type_id == type_id).first()
    if not product_sample:
        return {"error": "Tipo de produto não encontrado"}

    if product_sample.controla_por_serie:
        items = (
            db.query(Item)
            .join(Product, Product.id == Item.product_id)
            .join(Unidade, Unidade.id == Item.unit_id)
            .filter(Product.type_id == type_id, Unidade.nome == unit_name)
            .all()
        )
        return {
            "controla_por_serie": True,
            "product_type": product_sample.type.nome if product_sample.type else None,
            "items": [
                {"id": i.id, "num": i.num_tombo_ou_serie, "unit": i.unit.nome if i.unit else None, "tombo": i.tombo}
                for i in items
            ]
        }

    stocks = (
        db.query(Stock)
        .join(Product, Product.id == Stock.product_id)
        .join(Unidade, Unidade.id == Stock.unit_id)
        .filter(Product.type_id == type_id, Unidade.nome == unit_name)
        .all()
    )
    total_quantidade = sum(s.quantidade for s in stocks)
    max_minimo = max((s.quantidade_minima or 0 for s in stocks), default=0)
    return {
        "controla_por_serie": False,
        "product_type": product_sample.type.nome if product_sample.type else None,
        "product_brand": product_sample.brand.nome if product_sample.brand else None,
        "product_model": product_sample.model,
        "stock": [{"unit": unit_name, "quantidade": total_quantidade, "minimo": max_minimo}]
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
            "product_name": product.name,
            "product_brand": product.brand.nome if product.brand else None,
            "product_model": product.model,
            "items": [
                {"id": i.id, "num": i.num_tombo_ou_serie, "unit": i.unit.nome if i.unit else None, "tombo": i.tombo}
                for i in items
            ]
        }

    stocks = db.query(Stock).filter(Stock.product_id == product_id).all()
    return {
        "controla_por_serie": False,
        "product_type": product.type.nome if product.type else None,
        "product_name": product.name,
        "product_brand": product.brand.nome if product.brand else None,
        "product_model": product.model,
        "stock": [
            {"unit": s.unit.nome if s.unit else None, "quantidade": s.quantidade, "minimo": s.quantidade_minima}
            for s in stocks
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
        .join(Product)
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