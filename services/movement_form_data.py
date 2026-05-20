"""Dados compartilhados para o formulário de movimentação (página e modal)."""

from sqlalchemy.orm import Session

from models import Product, Stock, Item, Category, Unidade


def build_movement_form_context(db: Session) -> dict:
    products = db.query(Product).all()
    units = db.query(Unidade).order_by(Unidade.nome).all()
    categories = db.query(Category).all()

    products_js = []
    for p in products:
        units_options = []
        units_set = set()

        if p.controla_por_serie:
            for item in p.items:
                if item.unit_id and item.unit_id not in units_set and item.unit:
                    units_options.append({
                        "unit_id": item.unit.id,
                        "unit_name": item.unit.nome,
                    })
                    units_set.add(item.unit_id)
        else:
            stocks = (
                db.query(Stock)
                .filter(Stock.product_id == p.id, Stock.quantidade > 0)
                .all()
            )
            for s in stocks:
                if s.unit_id and s.unit_id not in units_set and s.unit:
                    units_options.append({"unit_id": s.unit.id, "unit_name": s.unit.nome})
                    units_set.add(s.unit_id)
            items = db.query(Item).filter(Item.product_id == p.id).all()
            for i in items:
                if i.unit_id and i.unit_id not in units_set and i.unit:
                    units_options.append({"unit_id": i.unit.id, "unit_name": i.unit.nome})
                    units_set.add(i.unit_id)

        products_js.append({
            "id": p.id,
            "name": p.name,
            "type_id": p.type_id,
            "type_name": p.type.nome if p.type else None,
            "category_id": p.category_id,
            "controla_por_serie": p.controla_por_serie,
            "units_options": units_options,
        })

    return {
        "products": products_js,
        "units": units,
        "categories": categories,
    }
