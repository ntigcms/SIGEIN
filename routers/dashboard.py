from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from dependencies import get_current_user
from database import get_db
from templating import templates
from models import Stock, Movement, Product, User
from datetime import datetime, timedelta

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/")
def dashboard_overview(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    total_products = db.query(Product).count()
    critical_products = (
        db.query(Stock).filter(Stock.quantidade <= Stock.quantidade_minima).count()
    )
    zero_stock_products = db.query(Stock).filter(Stock.quantidade <= 0).count()

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_movements_count = (
        db.query(Movement).filter(Movement.data >= seven_days_ago).count()
    )

    user_display = user
    user_row = db.query(User).filter(User.email == user).first()
    if user_row:
        user_display = user_row.nome.split()[0] if user_row.nome else user

    critical_stock = []
    stocks = db.query(Stock).all()
    for s in stocks:
        status = "OK"
        if s.quantidade <= 0:
            status = "ZERADO"
        elif s.quantidade <= (s.quantidade_minima or 0):
            status = "CRITICO"

        if status in ("ZERADO", "CRITICO"):
            unit_name = getattr(s.unit, "nome", None) or getattr(s.unit, "name", "")
            critical_stock.append(
                {
                    "product_name": s.product.name,
                    "unit_name": unit_name,
                    "quantidade": s.quantidade,
                    "quantidade_minima": s.quantidade_minima,
                    "status": status,
                }
            )

    critical_stock.sort(key=lambda x: (0 if x["status"] == "ZERADO" else 1, x["quantidade"]))

    total_stock_rows = len(stocks) or 1
    stock_ok = max(0, total_stock_rows - critical_products)
    health_percent = round((stock_ok / total_stock_rows) * 100)
    pct_ok = round((stock_ok / total_stock_rows) * 100, 1)
    pct_critical = round((critical_products / total_stock_rows) * 100, 1)
    pct_zero = round((zero_stock_products / total_stock_rows) * 100, 1)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "hide_app_header": True,
            "user_display": user_display,
            "total_products": total_products,
            "critical_products": critical_products,
            "zero_stock_products": zero_stock_products,
            "recent_movements_count": recent_movements_count,
            "critical_stock": critical_stock,
            "health_percent": health_percent,
            "stock_ok": stock_ok,
            "pct_ok": pct_ok,
            "pct_critical": pct_critical,
            "pct_zero": pct_zero,
        },
    )
