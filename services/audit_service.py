from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Product, Stock, Movement, Item


class AuditService:

    @staticmethod
    def auditar_produto_sem_serie(db: Session, product_id: int):

        resultado = []

        stocks = db.query(Stock).filter(
            Stock.product_id == product_id
        ).all()

        for stock in stocks:

            entradas = db.query(func.coalesce(func.sum(Movement.quantidade), 0)).filter(
                Movement.product_id == product_id,
                Movement.unit_destino_id == stock.unit_id,
                Movement.tipo.in_(["ENTRADA", "TRANSFERENCIA"])
            ).scalar()

            saidas = db.query(func.coalesce(func.sum(Movement.quantidade), 0)).filter(
                Movement.product_id == product_id,
                Movement.unit_origem_id == stock.unit_id,
                Movement.tipo.in_(["SAIDA", "TRANSFERENCIA"])
            ).scalar()

            saldo_calculado = entradas - saidas
            saldo_registrado = stock.quantidade

            divergencia = saldo_calculado - saldo_registrado

            resultado.append({
                "unit_id": stock.unit_id,
                "saldo_calculado": saldo_calculado,
                "saldo_registrado": saldo_registrado,
                "divergencia": divergencia
            })

        return resultado


    @staticmethod
    def auditar_produto_com_serie(db: Session, product_id: int):

        resultado = []

        contagem = db.query(
            Item.unit_id,
            func.count(Item.id).label("quantidade_real")
        ).filter(
            Item.product_id == product_id,
            Item.status != "Baixado"
        ).group_by(Item.unit_id).all()

        for unidade in contagem:
            resultado.append({
                "unit_id": unidade.unit_id,
                "quantidade_real": unidade.quantidade_real
            })

        return resultado


    @staticmethod
    def auditar_tudo(db: Session):

        relatorio = []

        produtos = db.query(Product).all()

        for p in produtos:

            if p.controla_por_serie:
                dados = AuditService.auditar_produto_com_serie(db, p.id)
            else:
                dados = AuditService.auditar_produto_sem_serie(db, p.id)

            relatorio.append({
                "product_id": p.id,
                "product_name": p.name,
                "controla_por_serie": p.controla_por_serie,
                "resultado": dados
            })

        return relatorio
