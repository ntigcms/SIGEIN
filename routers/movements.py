from fastapi.responses import RedirectResponse, JSONResponse
from fastapi import APIRouter, Request, Form, Depends, Query
from urllib.parse import quote
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from models import Product, Unit, Category, Movement, User, Stock, Item, Unidade
from services.stock_service import StockService
from services.movement_form_data import build_movement_form_context
from database import get_db
from datetime import datetime
from dependencies import get_current_user, registrar_log
from starlette.status import HTTP_302_FOUND
from typing import Optional
from templating import templates

from routers import products

router = APIRouter(prefix="/movements", tags=["Movimentações"])


# -------------------------------
# LISTAR MOVIMENTAÇÕES
# -------------------------------
@router.get("/")
def listar_movimentacoes(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    movements = (
        db.query(Movement)
        .options(
            joinedload(Movement.user),
            joinedload(Movement.product).joinedload(Product.type),
            joinedload(Movement.item),
            joinedload(Movement.unit_origem),
            joinedload(Movement.unit_destino),
        )
        .order_by(Movement.data.desc())
        .all()
    )

    def _filtro_label(valor: str | None) -> str:
        return (valor or "").strip()

    tipos = sorted(
        {
            _filtro_label(m.product.type.nome)
            for m in movements
            if m.product and m.product.type
        }
    )
    origens = sorted(
        {_filtro_label(m.unit_origem.nome) for m in movements if m.unit_origem}
    )
    destinos = sorted(
        {_filtro_label(m.unit_destino.nome) for m in movements if m.unit_destino}
    )
    tombos = sorted(
        {
            _filtro_label(m.item.num_tombo_ou_serie)
            for m in movements
            if m.item and m.item.num_tombo_ou_serie
        }
    )
    tipos_mov = sorted({_filtro_label(m.tipo) for m in movements if m.tipo})
    usuarios = sorted({_filtro_label(m.user.nome) for m in movements if m.user})
    datas = sorted(
        {m.data.strftime("%d/%m/%Y %H:%M") for m in movements if m.data}
    )

    return templates.TemplateResponse(
        "movements_list.html",
        {
            "request": request,
            "movements": movements,
            "user": user,
            "hide_app_header": True,
            "tipos": tipos,
            "origens": origens,
            "destinos": destinos,
            "tombos": tombos,
            "tipos_mov": tipos_mov,
            "usuarios": usuarios,
            "datas": datas,
        },
    )


# -------------------------------
# FORMULÁRIO NOVA MOVIMENTAÇÃO
# -------------------------------
@router.get("/nova")
def nova_movimentacao_form(
    request: Request,
    error: Optional[str] = None,
    type_id_q: Optional[int] = Query(None, alias="type"),
    product_id: Optional[int] = None,
    unit_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    prefill = {}
    product = None
    if product_id:
        product = (
            db.query(Product)
            .options(joinedload(Product.type))
            .filter(Product.id == product_id)
            .first()
        )
    elif type_id_q:
        product = (
            db.query(Product)
            .options(joinedload(Product.type))
            .filter(Product.type_id == type_id_q)
            .first()
        )
    if product:
        prefill = {
            "category_id": product.category_id,
            "type_id": product.type_id,
            "product_id": product.id,
            "unit_origem_id": unit_id,
            "controla_por_serie": product.controla_por_serie,
        }

    ctx = build_movement_form_context(db)

    return templates.TemplateResponse(
        "movement_form.html",
        {
            "request": request,
            "movimento": {},
            "prefill": prefill,
            "products": ctx["products"],
            "movement_units": ctx["units"],
            "movement_categories": ctx["categories"],
            "user": user,
            "error": error,
            "hide_app_header": True,
        },
    )



# -------------------------------
# SUBMIT NOVA MOVIMENTAÇÃO
# -------------------------------
def _movement_wants_json(request: Request, ajax: Optional[str]) -> bool:
    if ajax == "1":
        return True
    return "application/json" in (request.headers.get("accept") or "")


@router.post("/")
def movimentacoes_submit(
    request: Request,
    type_id: int = Form(...),
    product_id: Optional[str] = Form(None),
    unit_origem_id: int = Form(None),
    unit_destino_id: int = Form(None),
    item_id: Optional[str] = Form(None),  # recebe string
    tipo: str = Form(...),
    quantidade: int = Form(1),
    observacao: str = Form(""),
    ajax: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    username: str = Depends(get_current_user)
):
    if not username:
        return RedirectResponse("/login")

    user = db.query(User).filter(User.email == username).first()
    if not user:
        return {"error": "Usuário não encontrado"}

    # Converte item_id vazio para None
    if not item_id or item_id == "":
        item_id = None
    else:
        item_id = int(item_id)

    product_id_int = None
    if product_id and str(product_id).strip().isdigit():
        product_id_int = int(product_id)

    # Descobre produto
    if item_id:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            return {"error": "Item não encontrado"}
        product = item.product
    elif product_id_int:
        product = db.query(Product).filter(Product.id == product_id_int).first()
        if not product:
            err = "Produto não encontrado"
            if _movement_wants_json(request, ajax):
                return JSONResponse({"success": False, "message": err}, status_code=400)
            return {"error": err}
    else:
        product = db.query(Product).filter(Product.type_id == type_id).first()
        if not product:
            err = "Produto não encontrado"
            if _movement_wants_json(request, ajax):
                return JSONResponse({"success": False, "message": err}, status_code=400)
            return {"error": err}

    if not item_id:
        if product.controla_por_serie:
            err = "Item físico obrigatório para produtos controlados por série"
            if _movement_wants_json(request, ajax):
                return JSONResponse({"success": False, "message": err}, status_code=400)
            return {"error": err}

        item = db.query(Item).filter(Item.product_id == product.id).first()
        if not item:
            item = Item(
                product_id=product.id,
                municipio_id=product.municipio_id,
                orgao_id=product.orgao_id,
                tombo=False,
                num_tombo_ou_serie=f"Produto sem série - {product.name}",
                unit_id=unit_origem_id,
                status="Disponível",
            )
            db.add(item)
            db.commit()
            db.refresh(item)
        item_id = item.id


    # 🔥 AQUI É ONDE ENTRA O SERVICE
    from services.stock_service import StockService

    try:
        StockService.processar_movimentacao(
            db=db,
            product_id=product.id,
            tipo=tipo,
            user_id=user.id,
            unit_origem_id=unit_origem_id,
            unit_destino_id=unit_destino_id,
            item_id=item_id,
            quantidade=quantidade,
            observacao=observacao
        )

    except Exception as e:
        err_msg = str(e)
        if _movement_wants_json(request, ajax):
            return JSONResponse({"success": False, "message": err_msg}, status_code=400)
        return RedirectResponse(
            url=f"/movements/nova?error={quote(err_msg)}",
            status_code=HTTP_302_FOUND,
        )

    registrar_log(
        db=db,
        usuario=user.email,
        acao=f"Registrou movimentação {tipo} do produto {product.name}",
        ip=request.client.host
    )

    if _movement_wants_json(request, ajax):
        return JSONResponse({
            "success": True,
            "message": "Movimentação registrada com sucesso.",
        })
    return RedirectResponse(url="/movements/", status_code=HTTP_302_FOUND)




# -------------------------------
# FORMULÁRIO EDITAR MOVIMENTAÇÃO
# -------------------------------
@router.get("/edit/{movement_id}")
def editar_movimentacao_form(
    movement_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    movimento = db.query(Movement).filter(Movement.id == movement_id).first()
    if not movimento:
        return {"error": "Movimentação não encontrada"}

    ctx = build_movement_form_context(db)

    movimento_dict = {
        "id": movimento.id,
        "quantidade": movimento.quantidade,
        "tipo": movimento.tipo,
        "observacao": movimento.observacao,
        "unit_origem_id": movimento.unit_origem_id,  # ✅ estava faltando!
        "unit_destino_id": movimento.unit_destino_id,
        "product": {
            "id": movimento.product.id if movimento.product else None,
            "type_id": movimento.product.type_id if movimento.product else None,
            "category_id": movimento.product.category_id if movimento.product else None
        },
        "item": None
    }

    if movimento.item:
        movimento_dict["item"] = {
            "id": movimento.item.id,
            "tombo": movimento.item.tombo,
            "num": movimento.item.num_tombo_ou_serie,
            "unit_id": movimento.item.unit_id,
            "unit_name": movimento.item.unit.nome if movimento.item.unit else None
        }

    return templates.TemplateResponse(
        "movement_form.html",
        {
            "request": request,
            "movimento": movimento_dict,
            "prefill": {},
            "products": ctx["products"],
            "movement_units": ctx["units"],
            "movement_categories": ctx["categories"],
            "user": user,
        }
    )



# -------------------------------
# UPDATE MOVIMENTAÇÃO
# -------------------------------
@router.post("/edit/{movement_id}")
def movimentacoes_update(
    movement_id: int,
    request: Request,
    type_id: int = Form(...),
    unit_origem_id: int = Form(None),
    unit_destino_id: int = Form(...),
    item_id: int = Form(None),
    tipo: str = Form(...),
    quantidade: int = Form(1),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
    username: str = Depends(get_current_user)
):
    if not username:
        return RedirectResponse("/login")

    movimento = db.query(Movement).filter(Movement.id == movement_id).first()
    if not movimento:
        return {"error": "Movimentação não encontrada"}

    user = db.query(User).filter(User.email == username).first()
    if not user:
        return {"error": "Usuário não encontrado"}

    product = None
    item = None

    if item_id:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            return {"error": "Item físico não encontrado"}
        product = item.product
        unit_origem_id = item.unit_id
        quantidade = 1
    else:
        product = db.query(Product).filter(Product.type_id == type_id).first()
        if not product:
            return {"error": "Produto não encontrado"}
        if product.controla_por_serie:
            return {"error": "Item físico obrigatório para produtos controlados por série"}
        if not unit_origem_id:
            return {"error": "Unidade de origem obrigatória"}

    # Atualiza o movimento
    movimento.product_id = product.id
    movimento.item_id = item.id if item else None
    movimento.unit_origem_id = unit_origem_id
    movimento.unit_destino_id = unit_destino_id
    movimento.quantidade = quantidade
    movimento.tipo = tipo
    movimento.observacao = observacao
    movimento.user_id = user.id
    movimento.data = datetime.utcnow()

    if product.controla_por_serie and item and tipo in ["SAIDA", "TRANSFERENCIA"]:
        item.unit_id = unit_destino_id
        db.add(item)

    db.add(movimento)
    db.commit()

    registrar_log(
        db=db,
        usuario=user.email,
        acao=f"Editou movimentação {tipo} do produto {product.name}",
        ip=request.client.host
    )

    return RedirectResponse(url="/movements/", status_code=HTTP_302_FOUND)


# -------------------------------
# DELETE MOVIMENTAÇÃO
# -------------------------------
@router.post("/delete/{movement_id}")
def delete_movement(movement_id: int, db: Session = Depends(get_db), user: str = Depends(get_current_user)):

    movement = db.query(Movement).filter(Movement.id == movement_id).first()
    if not movement:
        return JSONResponse({"success": False, "message": "Movimentação não encontrada."})

    # Exemplo: bloquear exclusão se tiver regras específicas
    if movement.tipo == "Saída com Pendência":  # Exemplo
        return JSONResponse({"success": False, "message": "Não é possível excluir esta movimentação."})

    db.delete(movement)
    db.commit()

    return JSONResponse({"success": True})


# -------------------------------
# API AUXILIARES
# -------------------------------
@router.get("/movements/stock/type/{type_id}")
def get_product_stock(type_id: int, db: Session = Depends(get_db)):
    result = []

    # 1️⃣ Estoque por unidades (Stock)
    stocks = (
        db.query(Stock)
        .join(Product)
        .join(Unit)
        .filter(Product.type_id == type_id, Stock.quantidade > 0)
        .all()
    )

    for s in stocks:
        result.append({
            "unit_id": s.unit.id,
            "unit_name": s.unit.nome,
            "quantidade": s.quantidade
        })

    # 2️⃣ Itens físicos (Itens sem série e com série)
    items = (
        db.query(Item.unit_id, Unit.name, func.count(Item.id).label("quantidade"))
        .join(Product)
        .join(Unit, Item.unit_id == Unit.id)
        .filter(Product.type_id == type_id)
        .group_by(Item.unit_id, Unit.name)
        .all()
    )

    for i in items:
        # Se já existe no result (Stock), só somar quantidade? Ou ignorar duplicados
        if not any(r["unit_id"] == i.unit_id for r in result):
            result.append({
                "unit_id": i.unit_id,
                "unit_name": i.name,
                "quantidade": i.quantidade
            })
        else:
            # Adiciona quantidade dos itens físicos ao estoque existente
            for r in result:
                if r["unit_id"] == i.unit_id:
                    r["quantidade"] += i.quantidade

    return result


@router.get("/items/{type_id}")
def get_product_items(
    type_id: int,
    product_id: Optional[int] = None,
    unit_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    items_result = []

    # 1️⃣ Itens físicos já cadastrados (controla por série ou não)
    q = (
        db.query(Item)
        .join(Product)
        .join(Unidade, Item.unit_id == Unidade.id)  # Só itens cuja unidade existe
        .filter(Product.type_id == type_id)
    )
    if product_id:
        q = q.filter(Item.product_id == product_id)
    if unit_id:
        q = q.filter(Item.unit_id == unit_id)
    items = q.all()

    for i in items:
        items_result.append({
            "id": i.id,
            "tombo": i.tombo,
            "num": i.num_tombo_ou_serie if i.num_tombo_ou_serie else f"Produto sem série - {i.product.name}",
            "unit_id": i.unit_id,
            "unit_name": i.unit.nome
        })

    # 2️⃣ Produtos sem série que ainda não têm Item cadastrado
    products_sem_serie = (
        db.query(Product)
        .filter(Product.type_id == type_id, Product.controla_por_serie == False)
        .all()
    )

    for p in products_sem_serie:
        # Verifica se já existe um Item para este produto
        item_exists = db.query(Item).filter(Item.product_id == p.id).first()
        if not item_exists:
            # Cria um registro “virtual” para mostrar no select
            items_result.append({
                "id": None,  # sem ID porque não existe Item
                "tombo": False,
                "num": f"Produto sem série - {p.name}",
                "unit_id": 11,  # unidade GCM
                "unit_name": "GCM"
            })

    return items_result


@router.get("/items/search")
def search_items(
    product_id: int,
    tipo: str,
    q: str = "",
    db: Session = Depends(get_db)
):
    is_tombo = tipo.upper() == "TOMBO"

    items = (
        db.query(Item)
        .filter(
            Item.product_id == product_id,
            Item.tombo == is_tombo,
            Item.num_tombo_ou_serie.ilike(f"%{q}%")
        )
        .limit(20)
        .all()
    )

    return [
        {
            "id": i.id,
            "text": i.num_tombo_ou_serie,
            "unit_id": i.unit_id,
            "unit_name": i.unit.nome
        }
        for i in items
    ]
