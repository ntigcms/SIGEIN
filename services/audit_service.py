from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from dependencies import agora_brasilia
from models import Product, Stock, Movement, Item, Unidade


def _sum_movimentos(
    db: Session,
    product_id: int,
    *,
    unit_destino_id: int | None = None,
    unit_origem_id: int | None = None,
    tipos: list[str],
) -> int:
    q = db.query(func.coalesce(func.sum(Movement.quantidade), 0)).filter(
        Movement.product_id == product_id,
        Movement.tipo.in_(tipos),
    )
    if unit_destino_id is not None:
        q = q.filter(Movement.unit_destino_id == unit_destino_id)
    if unit_origem_id is not None:
        q = q.filter(Movement.unit_origem_id == unit_origem_id)
    return int(q.scalar() or 0)


class AuditService:

    @staticmethod
    def auditar_produto_sem_serie(db: Session, product_id: int):
        resultado = []

        stocks = db.query(Stock).filter(Stock.product_id == product_id).all()

        for stock in stocks:
            unit_id = stock.unit_id

            # Entrada: adiciona na unidade de destino
            qtd_entrada = _sum_movimentos(
                db, product_id, unit_destino_id=unit_id, tipos=["ENTRADA"]
            )
            # Transferência recebida: destino = esta unidade
            qtd_transf_entrada = _sum_movimentos(
                db, product_id, unit_destino_id=unit_id, tipos=["TRANSFERENCIA"]
            )
            # Transferência enviada: origem = esta unidade (move para outra unidade)
            qtd_transf_saida = _sum_movimentos(
                db, product_id, unit_origem_id=unit_id, tipos=["TRANSFERENCIA"]
            )
            # Saída: descarte/doação — reduz só na origem, não é transferência
            qtd_saida = _sum_movimentos(
                db, product_id, unit_origem_id=unit_id, tipos=["SAIDA"]
            )

            saldo_calculado = (
                qtd_entrada
                + qtd_transf_entrada
                - qtd_transf_saida
                - qtd_saida
            )
            saldo_registrado = stock.quantidade or 0
            divergencia = saldo_calculado - saldo_registrado

            resultado.append({
                "unit_id": unit_id,
                "saldo_calculado": saldo_calculado,
                "saldo_registrado": saldo_registrado,
                "divergencia": divergencia,
                "qtd_entrada": qtd_entrada,
                "qtd_transf_entrada": qtd_transf_entrada,
                "qtd_transf_saida": qtd_transf_saida,
                "qtd_saida": qtd_saida,
            })

        return resultado

    @staticmethod
    def auditar_produto_com_serie(db: Session, product_id: int):
        resultado = []

        contagem = (
            db.query(
                Item.unit_id,
                func.count(Item.id).label("quantidade_real"),
            )
            .filter(Item.product_id == product_id, Item.status != "Baixado")
            .group_by(Item.unit_id)
            .all()
        )

        stocks = {
            s.unit_id: s.quantidade or 0
            for s in db.query(Stock).filter(Stock.product_id == product_id).all()
        }

        units_seen = set()

        for unidade in contagem:
            units_seen.add(unidade.unit_id)
            qty_itens = int(unidade.quantidade_real or 0)
            qty_stock = stocks.get(unidade.unit_id)
            resultado.append({
                "unit_id": unidade.unit_id,
                "quantidade_real": qty_itens,
                "saldo_registrado": qty_stock,
                "saldo_calculado": qty_itens,
                "divergencia": (qty_itens - qty_stock) if qty_stock is not None else 0,
                "tem_estoque_cadastrado": qty_stock is not None,
            })

        for unit_id, qty_stock in stocks.items():
            if unit_id not in units_seen:
                resultado.append({
                    "unit_id": unit_id,
                    "quantidade_real": 0,
                    "saldo_registrado": qty_stock,
                    "saldo_calculado": 0,
                    "divergencia": -qty_stock,
                    "tem_estoque_cadastrado": True,
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
                "resultado": dados,
            })

        return relatorio


def build_stock_audit(db: Session) -> dict:
    """Relatório plano para a tela /stock/audit."""
    unidades_map = {
        u.id: u.nome for u in db.query(Unidade.id, Unidade.nome).all()
    }
    rows: list[dict] = []

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
        controle_label = "Tombo/série" if p.controla_por_serie else "Quantidade"

        if p.controla_por_serie:
            dados = AuditService.auditar_produto_com_serie(db, p.id)
            for d in dados:
                unit_name = unidades_map.get(d["unit_id"], "—")
                tem_stock = d.get("tem_estoque_cadastrado", False)
                calc = d.get("saldo_calculado", d.get("quantidade_real", 0))
                reg = d.get("saldo_registrado")
                div = d.get("divergencia", 0)

                if tem_stock:
                    status = "DIVERGENTE" if div != 0 else "OK"
                    metodo = "Itens físicos × estoque cadastrado"
                    reg_display = reg if reg is not None else 0
                else:
                    status = "OK"
                    metodo = "Contagem de itens (sem registro em estoque)"
                    reg_display = "—"
                    div = 0

                rows.append(_audit_row(
                    product=p,
                    type_name=type_name,
                    category_name=category_name,
                    brand_name=brand_name,
                    controle_label=controle_label,
                    unit_id=d["unit_id"],
                    unit_name=unit_name,
                    saldo_calculado=calc,
                    saldo_registrado=reg_display,
                    divergencia=div if tem_stock else 0,
                    status=status,
                    metodo=metodo,
                    controla_por_serie=True,
                ))
        else:
            dados = AuditService.auditar_produto_sem_serie(db, p.id)
            for d in dados:
                unit_name = unidades_map.get(d["unit_id"], "—")
                div = d["divergencia"]
                status = "DIVERGENTE" if div != 0 else "OK"
                detalhe = (
                    f"Entrada {d.get('qtd_entrada', 0)}"
                    f" + Transf. receb. {d.get('qtd_transf_entrada', 0)}"
                    f" - Transf. env. {d.get('qtd_transf_saida', 0)}"
                    f" - Saida {d.get('qtd_saida', 0)}"
                )
                rows.append(_audit_row(
                    product=p,
                    type_name=type_name,
                    category_name=category_name,
                    brand_name=brand_name,
                    controle_label=controle_label,
                    unit_id=d["unit_id"],
                    unit_name=unit_name,
                    saldo_calculado=d["saldo_calculado"],
                    saldo_registrado=d["saldo_registrado"],
                    divergencia=div,
                    status=status,
                    metodo=detalhe,
                    controla_por_serie=False,
                ))

    rows.sort(
        key=lambda r: (
            0 if r["status"] == "DIVERGENTE" else 1,
            -abs(r["divergencia_num"]),
            r["product_name"],
        )
    )

    divergentes = sum(1 for r in rows if r["status"] == "DIVERGENTE")
    ok = sum(1 for r in rows if r["status"] == "OK")
    produtos_chk = len({r["product_id"] for r in rows})
    unidades_chk = len({r["unit_id"] for r in rows if r.get("unit_id")})

    tipos = sorted({r["type_name"] for r in rows if r["type_name"]})
    unidades = sorted({r["unit_name"] for r in rows if r["unit_name"]})
    categorias = sorted({r["category_name"] for r in rows if r["category_name"]})

    return {
        "rows": rows,
        "summary": {
            "total": len(rows),
            "divergentes": divergentes,
            "ok": ok,
            "produtos": produtos_chk,
            "unidades": unidades_chk,
            "updated_at": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S"),
        },
        "filter_options": {
            "tipos": tipos,
            "unidades": unidades,
            "categorias": categorias,
            "statuses": ["Divergente", "Conferido"],
        },
    }


def _audit_row(
    *,
    product: Product,
    type_name: str,
    category_name: str,
    brand_name: str,
    controle_label: str,
    unit_id: int,
    unit_name: str,
    saldo_calculado,
    saldo_registrado,
    divergencia: int,
    status: str,
    metodo: str,
    controla_por_serie: bool,
) -> dict:
    div_num = int(divergencia) if isinstance(divergencia, (int, float)) else 0
    calc_num = saldo_calculado if isinstance(saldo_calculado, (int, float)) else 0
    reg_num = saldo_registrado if isinstance(saldo_registrado, (int, float)) else 0
    if div_num > 0:
        div_label = f"+{div_num}"
    elif div_num < 0:
        div_label = str(div_num)
    else:
        div_label = "0"

    return {
        "product_id": product.id,
        "product_name": product.name,
        "type_name": type_name,
        "category_name": category_name,
        "brand_name": brand_name,
        "unit_id": unit_id,
        "unit_name": unit_name,
        "saldo_calculado": saldo_calculado,
        "saldo_calculado_num": calc_num,
        "saldo_registrado": saldo_registrado,
        "saldo_registrado_num": reg_num,
        "divergencia": div_label,
        "divergencia_num": div_num,
        "status": status,
        "status_label": "Divergente" if status == "DIVERGENTE" else "Conferido",
        "metodo": metodo,
        "controle_label": controle_label,
        "controla_por_serie": controla_por_serie,
        "edit_url": f"/products/edit/{product.id}",
        "movements_url": f"/movements/?type={product.type_id}" if product.type_id else "/movements/",
    }
