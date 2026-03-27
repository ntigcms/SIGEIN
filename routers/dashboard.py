from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from dependencies import get_current_user
from database import get_db
from shared_templates import templates
from services.audit_service import AuditService
from models import Stock, Movement, Product, User, Item
from datetime import datetime, timedelta
from sqlalchemy import or_

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/")
def dashboard_overview(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):

    if not user:
        return {}

    # Nome do usuário para exibir no layout (base.html)
    user_obj = db.query(User).filter(User.email == user).first()
    if not user_obj:
        return {}
    user_display = user_obj.nome if user_obj else user
    is_master = user_obj.perfil == "master"

    # Total de produtos
    products_q = db.query(Product)
    if not is_master:
        products_q = products_q.filter(Product.municipio_id == user_obj.municipio_id)
    total_products = products_q.count()

    # Produtos críticos
    critical_q = db.query(Stock).filter(Stock.quantidade <= Stock.quantidade_minima)
    if not is_master:
        critical_q = critical_q.filter(Stock.municipio_id == user_obj.municipio_id)
    critical_products = critical_q.count()

    # Produtos zerados
    zero_q = db.query(Stock).filter(Stock.quantidade <= 0)
    if not is_master:
        zero_q = zero_q.filter(Stock.municipio_id == user_obj.municipio_id)
    zero_stock_products = zero_q.count()

    # Movimentações recentes
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    movements_q = db.query(Movement).filter(Movement.data >= seven_days_ago)
    if not is_master:
        movements_q = movements_q.outerjoin(Product, Movement.product_id == Product.id).outerjoin(
            Item, Movement.item_id == Item.id
        ).filter(
            or_(
                Product.municipio_id == user_obj.municipio_id,
                Item.municipio_id == user_obj.municipio_id,
            )
        )
    recent_movements_count = movements_q.count()


    # Lista de produtos críticos para tabela
    critical_stock = []
    stocks_q = db.query(Stock)
    if not is_master:
        stocks_q = stocks_q.filter(Stock.municipio_id == user_obj.municipio_id)
    stocks = stocks_q.all()
    for s in stocks:
        status = "OK"
        if s.quantidade <= 0:
            status = "ZERADO"
        elif s.quantidade <= (s.quantidade_minima or 0):
            status = "CRITICO"

        if status in ["ZERADO", "CRITICO"]:
            critical_stock.append({
                "product_name": s.product.name,
                "unit_name": s.unit.nome,
                "quantidade": s.quantidade,
                "quantidade_minima": s.quantidade_minima,
                "status": status
            })

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user_display,
            "total_products": total_products,
            "critical_products": critical_products,
            "zero_stock_products": zero_stock_products,
            "recent_movements_count": recent_movements_count,
            "critical_stock": critical_stock
        }
    )
