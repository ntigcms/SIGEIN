from fastapi import APIRouter, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models import Product, Unit, Category, Movement, User
from database import get_db
from datetime import datetime
from dependencies import get_current_user, registrar_log

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/movimentacoes")
def movimentacoes_form(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).all()
    units = db.query(Unit).all()
    categories = db.query(Category).all()

    # Preparar produtos em formato JS para o template
    products_js = [
        {
            "id": p.id,
            "name": p.name,
            "category_id": p.category_id,
            "unit_id": p.unit.id if p.unit else None,
            "unit_name": p.unit.name if p.unit else ""
        }
        for p in products
    ]

    return templates.TemplateResponse("movimentacao.html", {
        "request": request,
        "products": products_js,
        "units": units,
        "categories": categories
    })


@router.post("/movimentacoes")
def movimentacoes_submit(
    request: Request,
    product_id: int = Form(...),
    unit_destino_id: int = Form(...),
    tipo: str = Form(...),
    quantidade: int = Form(...),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)  # Usuário logado
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return {"error": "Produto não encontrado"}

    movimento = Movement(
        product_id=product.id,
        unit_origem_id=product.unit.id if product.unit else None,
        unit_destino_id=unit_destino_id,
        quantidade=quantidade,
        tipo=tipo,
        observacao=observacao,
        user_id=user.id,
        data=datetime.utcnow()
    )

    # Atualizar a unidade do produto se for saída ou ajuste de destino
    if tipo == "SAIDA" or tipo == "AJUSTE":
        product.unit_id = unit_destino_id

    db.add(movimento)
    db.commit()

    return {"success": True, "message": "Movimentação registrada!"}
