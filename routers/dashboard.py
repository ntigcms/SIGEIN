from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from dependencies import get_current_user
from database import get_db
from shared_templates import templates
from services.audit_service import AuditService
from models import Stock, Movement, Product, User
from datetime import datetime, timedelta

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/")
def dashboard_overview(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):

    if not user:
        return {}

    # Nome do usuário para exibir no layout (base.html)
    user_obj = db.query(User).filter(User.email == user).first()
    user_display = user_obj.nome if user_obj else user

    # Total de produtos
    total_products = db.query(Product).count()

    # Produtos críticos
    critical_products = db.query(Stock).filter(Stock.quantidade <= Stock.quantidade_minima).count()

    # Produtos zerados
    zero_stock_products = db.query(Stock).filter(Stock.quantidade <= 0).count()

    # Movimentações recentes
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_movements_count = db.query(Movement).filter(Movement.data >= seven_days_ago).count()


    # Lista de produtos críticos para tabela
    critical_stock = []
    stocks = db.query(Stock).all()
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
