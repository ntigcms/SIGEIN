from sqlalchemy.orm import Session
from models import Product, Item, Stock, Movement, Unidade
from datetime import datetime


def _validar_unidade_existe(db: Session, unit_id: int, campo: str) -> None:
    """Verifica se a unidade existe na tabela unidades. Levanta exceção se não existir."""
    if unit_id is None:
        return
    unidade = db.query(Unidade).filter(Unidade.id == unit_id).first()
    if not unidade:
        raise Exception(
            f"A unidade de {campo} (ID {unit_id}) não existe mais no cadastro. "
            "Possível inconsistência: a unidade foi excluída mas há itens/estoque referenciando-a. "
            "Corrija o cadastro do item ou recrie a unidade."
        )


class StockService:

    @staticmethod
    def processar_movimentacao(
        db: Session,
        product_id: int,
        tipo: str,
        user_id: int,
        unit_origem_id: int = None,
        unit_destino_id: int = None,
        item_id: int = None,
        quantidade: int = 1,
        observacao: str = None
    ):

        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:
            raise Exception("Produto não encontrado")

        if product.controla_por_serie:
            return StockService._movimentar_com_serie(
                db, product, tipo, user_id,
                unit_origem_id, unit_destino_id,
                item_id, observacao
            )

        return StockService._movimentar_sem_serie(
            db, product, tipo, user_id,
            unit_origem_id, unit_destino_id,
            quantidade, observacao
        )


    # =====================================================
    # 🔐 PRODUTO COM SÉRIE
    # =====================================================

    @staticmethod
    def _movimentar_com_serie(
        db, product, tipo, user_id,
        unit_origem_id, unit_destino_id,
        item_id, observacao
    ):

        if not item_id:
            raise Exception("Item obrigatório")

        item = db.query(Item).filter(Item.id == item_id).first()

        if not item:
            raise Exception("Item não encontrado")

        if unit_origem_id and item.unit_id != unit_origem_id:
            raise Exception("Item não está na unidade de origem")

        # Valida que a unidade do item existe (evita FK violation se unidade foi excluída)
        _validar_unidade_existe(db, item.unit_id, "origem")
        if unit_destino_id:
            _validar_unidade_existe(db, unit_destino_id, "destino")

        if tipo == "TRANSFERENCIA":
            if not unit_destino_id:
                raise Exception("Unidade destino obrigatória")
            item.unit_id = unit_destino_id

        if tipo == "SAIDA":
            item.status = "Baixado"

        movement = Movement(
            product_id=product.id,
            item_id=item.id,
            unit_origem_id=item.unit_id,
            unit_destino_id=unit_destino_id,
            quantidade=1,
            tipo=tipo,
            observacao=observacao,
            user_id=user_id,
            data=datetime.utcnow()
        )

        db.add(item)
        db.add(movement)
        db.commit()

        return movement


    # =====================================================
    # 📦 PRODUTO SEM SÉRIE
    # =====================================================

    @staticmethod
    def _movimentar_sem_serie(
        db, product, tipo, user_id,
        unit_origem_id, unit_destino_id,
        quantidade, observacao
    ):

        # Valida que as unidades existem (evita FK violation se unidade foi excluída)
        _validar_unidade_existe(db, unit_origem_id, "origem")
        _validar_unidade_existe(db, unit_destino_id, "destino")

        stock_origem = db.query(Stock).filter(
            Stock.product_id == product.id,
            Stock.unit_id == unit_origem_id
        ).first()

        if tipo in ["SAIDA", "TRANSFERENCIA"]:

            if not stock_origem:
                raise Exception("Estoque não encontrado")

            if stock_origem.quantidade < quantidade:
                raise Exception("Estoque insuficiente")

            stock_origem.quantidade -= quantidade
            db.add(stock_origem)

        if tipo in ["ENTRADA", "TRANSFERENCIA"]:

            stock_destino = db.query(Stock).filter(
                Stock.product_id == product.id,
                Stock.unit_id == unit_destino_id
            ).first()

            if not stock_destino:
                stock_destino = Stock(
                    product_id=product.id,
                    unit_id=unit_destino_id,
                    quantidade=0
                )
                db.add(stock_destino)

            stock_destino.quantidade += quantidade
            db.add(stock_destino)

        movement = Movement(
            product_id=product.id,
            unit_origem_id=unit_origem_id,
            unit_destino_id=unit_destino_id,
            quantidade=quantidade,
            tipo=tipo,
            observacao=observacao,
            user_id=user_id,
            data=datetime.utcnow()
        )

        db.add(movement)
        db.commit()

        return movement
