from sqlalchemy.orm import Session
from models import Stock

def atualizar_estoque(
    db: Session,
    product_id: int,
    unit_id: int,
    quantidade: int,
    tipo: str
):
    stock = db.query(Stock).filter(
        Stock.product_id == product_id,
        Stock.unit_id == unit_id
    ).first()

    if not stock:
        stock = Stock(
            product_id=product_id,
            unit_id=unit_id,
            quantidade=0
        )
        db.add(stock)

    if tipo == "ENTRADA":
        stock.quantidade += quantidade

    elif tipo == "SAIDA":
        if stock.quantidade < quantidade:
            raise Exception("Estoque insuficiente")
        stock.quantidade -= quantidade

    elif tipo == "AJUSTE":
        stock.quantidade = quantidade

    db.commit()
