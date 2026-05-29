"""Consolidação de alertas de estoque (crítico e zerado)."""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from dependencies import agora_brasilia
from models import Product, Stock, Unidade, Item


def _status_estoque(quantidade: int, quantidade_minima: int) -> str | None:
    minimo = quantidade_minima or 0
    if quantidade <= 0:
        return "ZERADO"
    if minimo > 0 and quantidade <= minimo:
        return "CRITICO"
    return None


def build_stock_alerts(db: Session) -> dict:
    alerts: list[dict] = []

    produtos = (
        db.query(Product)
        .options(
            joinedload(Product.type),
            joinedload(Product.category),
            joinedload(Product.brand),
        )
        .all()
    )

    for p in produtos:
        type_name = p.type.nome if p.type else "—"
        category_name = p.category.nome if p.category else "—"
        brand_name = p.brand.nome if p.brand else "—"

        if p.controla_por_serie:
            rows = (
                db.query(
                    Unidade.id.label("unit_id"),
                    Unidade.nome.label("unit_name"),
                    func.count(Item.id).label("quantidade"),
                )
                .select_from(Item)
                .join(Unidade, Unidade.id == Item.unit_id)
                .filter(Item.product_id == p.id)
                .group_by(Unidade.id, Unidade.nome)
                .all()
            )

            units_with_items = {r.unit_id for r in rows}

            for r in rows:
                qty = int(r.quantidade or 0)
                minimo = 0
                status = _status_estoque(qty, minimo)
                if not status:
                    continue
                alerts.append(
                    _alert_row(
                        product=p,
                        type_name=type_name,
                        category_name=category_name,
                        brand_name=brand_name,
                        unit_id=r.unit_id,
                        unit_name=r.unit_name,
                        quantidade=qty,
                        quantidade_minima=minimo,
                        status=status,
                        controla_por_serie=True,
                    )
                )

            # Unidades com estoque cadastrado mas sem itens físicos
            stocks_ref = (
                db.query(Stock)
                .options(joinedload(Stock.unit))
                .filter(Stock.product_id == p.id, Stock.quantidade_minima > 0)
                .all()
            )
            for s in stocks_ref:
                if s.unit_id in units_with_items:
                    continue
                qty = 0
                minimo = s.quantidade_minima or 0
                status = _status_estoque(qty, minimo)
                if not status:
                    continue
                unit_name = s.unit.nome if s.unit else "—"
                alerts.append(
                    _alert_row(
                        product=p,
                        type_name=type_name,
                        category_name=category_name,
                        brand_name=brand_name,
                        unit_id=s.unit_id,
                        unit_name=unit_name,
                        quantidade=qty,
                        quantidade_minima=minimo,
                        status=status,
                        controla_por_serie=True,
                    )
                )
        else:
            stocks = (
                db.query(Stock)
                .options(joinedload(Stock.unit))
                .filter(Stock.product_id == p.id)
                .all()
            )
            for s in stocks:
                qty = s.quantidade or 0
                minimo = s.quantidade_minima or 0
                status = _status_estoque(qty, minimo)
                if not status:
                    continue
                unit_name = s.unit.nome if s.unit else "—"
                alerts.append(
                    _alert_row(
                        product=p,
                        type_name=type_name,
                        category_name=category_name,
                        brand_name=brand_name,
                        unit_id=s.unit_id,
                        unit_name=unit_name,
                        quantidade=qty,
                        quantidade_minima=minimo,
                        status=status,
                        controla_por_serie=False,
                        stock_id=s.id,
                    )
                )

    alerts.sort(
        key=lambda a: (
            0 if a["status"] == "ZERADO" else 1,
            -a["deficit"],
            a["quantidade"],
            a["product_name"],
        )
    )

    zerado = sum(1 for a in alerts if a["status"] == "ZERADO")
    critico = sum(1 for a in alerts if a["status"] == "CRITICO")
    units_affected = len({a["unit_id"] for a in alerts if a.get("unit_id")})

    tipos = sorted({a["type_name"] for a in alerts if a["type_name"]})
    unidades = sorted({a["unit_name"] for a in alerts if a["unit_name"]})
    categorias = sorted({a["category_name"] for a in alerts if a["category_name"]})

    return {
        "alerts": alerts,
        "summary": {
            "total": len(alerts),
            "zerado": zerado,
            "critico": critico,
            "units_affected": units_affected,
            "updated_at": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S"),
        },
        "filter_options": {
            "tipos": tipos,
            "unidades": unidades,
            "categorias": categorias,
            "statuses": ["Zerado", "Crítico"],
        },
    }


def _alert_row(
    *,
    product: Product,
    type_name: str,
    category_name: str,
    brand_name: str,
    unit_id: int,
    unit_name: str,
    quantidade: int,
    quantidade_minima: int,
    status: str,
    controla_por_serie: bool,
    stock_id: int | None = None,
) -> dict:
    minimo = quantidade_minima or 0
    deficit = max(0, minimo - quantidade) if minimo > 0 else (1 if quantidade <= 0 else 0)
    if minimo > 0:
        nivel_pct = min(100, round((quantidade / minimo) * 100))
    else:
        nivel_pct = 0 if quantidade <= 0 else 100

    return {
        "product_id": product.id,
        "product_name": product.name,
        "type_name": type_name,
        "category_name": category_name,
        "brand_name": brand_name,
        "unit_id": unit_id,
        "unit_name": unit_name,
        "quantidade": quantidade,
        "quantidade_minima": minimo,
        "deficit": deficit,
        "nivel_pct": nivel_pct,
        "status": status,
        "status_label": "Zerado" if status == "ZERADO" else "Crítico",
        "controla_por_serie": controla_por_serie,
        "controle_label": "Tombo/série" if controla_por_serie else "Quantidade",
        "stock_id": stock_id,
        "movement_url": f"/movements/nova?product_id={product.id}&unit_id={unit_id}",
        "edit_url": f"/products/edit/{product.id}",
    }
