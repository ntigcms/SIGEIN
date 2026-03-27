from fastapi.responses import RedirectResponse, JSONResponse
from fastapi import APIRouter, Request, Form, Depends
from urllib.parse import quote
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from models import Product, Unit, Category, Movement, User, Stock, Item, Unidade
from services.stock_service import StockService
from database import get_db
from datetime import datetime
from dependencies import get_current_user, registrar_log
from starlette.status import HTTP_302_FOUND
from typing import Optional
from shared_templates import templates

from routers import products

router = APIRouter(prefix="/movements", tags=["Movimentações"])

def _user_obj(db: Session, user_email: str):
    if not user_email:
        return None
    return db.query(User).filter(User.email == user_email).first()

def _is_master(user_obj: User) -> bool:
    return bool(user_obj and getattr(user_obj, "perfil", None) == "master")

# -------------------------------
# LISTAR MOVIMENTAÇÕES
# -------------------------------
@router.get("/")
def listar_movimentacoes(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    user_obj = _user_obj(db, user)
    if not user_obj:
        return RedirectResponse("/login")

    movements_q = (
        db.query(Movement)
        .options(
            joinedload(Movement.user),
            joinedload(Movement.product).joinedload(Product.type),
            joinedload(Movement.item),
            joinedload(Movement.unit_origem),
            joinedload(Movement.unit_destino),
        )
    )
    if not _is_master(user_obj):
        movements_q = (
            movements_q
            .outerjoin(Product, Movement.product_id == Product.id)
            .outerjoin(Item, Movement.item_id == Item.id)
            .filter(
                (Product.municipio_id == user_obj.municipio_id)
                | (Item.municipio_id == user_obj.municipio_id)
            )
        )
    movements = (
        movements_q
        .order_by(Movement.data.desc())
        .all()
    )

    return templates.TemplateResponse(
        "movements_list.html",
        {"request": request, "movements": movements, "user": user}
    )


# -------------------------------
# FORMULÁRIO NOVA MOVIMENTAÇÃO
# -------------------------------
@router.get("/nova")
def nova_movimentacao_form(
    request: Request,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    user_obj = _user_obj(db, user)
    if not user_obj:
        return RedirectResponse("/login")

    # Consulta produtos, unidades (Unidade = tabela unidades) e categorias
    products_q = db.query(Product)
    units_q = db.query(Unidade)
    if not _is_master(user_obj):
        products_q = products_q.filter(Product.municipio_id == user_obj.municipio_id)
        units_q = units_q.join(Unidade.orgao).filter(Unidade.orgao.has(municipio_id=user_obj.municipio_id))
    products = products_q.all()
    units = units_q.order_by(Unidade.nome).all()
    categories = db.query(Category).all()

    products_js = []

    for p in products:
        units_options = []

        if p.controla_por_serie:
            # Produto com série: pega unidades dos itens existentes (só itens com unidade válida)
            units_set = set()
            for item in p.items:
                if item.unit_id and item.unit_id not in units_set and item.unit:
                    units_options.append({
                        "unit_id": item.unit.id,
                        "unit_name": item.unit.nome
                    })
                    units_set.add(item.unit_id)
        else:
            # Produto sem série: pega todas as unidades que possuem este produto
            units_set = set()
            # Unidades com estoque
            stocks = db.query(Stock).filter(
                Stock.product_id == p.id,
                Stock.quantidade > 0
                ).all()
            for s in stocks:
                if s.unit_id and s.unit_id not in units_set and s.unit:
                    units_options.append({"unit_id": s.unit.id, "unit_name": s.unit.nome})
                    units_set.add(s.unit_id)
            # Unidades de itens existentes (só itens com unidade válida)
            items = db.query(Item).filter(Item.product_id == p.id).all()
            for i in items:
                if i.unit_id and i.unit_id not in units_set and i.unit:
                    units_options.append({"unit_id": i.unit.id, "unit_name": i.unit.nome})
                    units_set.add(i.unit_id)

        # Adiciona o produto ao JS
        products_js.append({
            "id": p.id,
            "name": p.name,
            "type_id": p.type_id,
            "type_name": p.type.nome if p.type else None,
            "category_id": p.category_id,
            "controla_por_serie": p.controla_por_serie,
            "units_options": units_options
        })

    # Renderiza o template
    return templates.TemplateResponse(
        "movement_form.html",
        {
            "request": request,
            "movimento": {},  # dict vazio para nova movimentação
            "products": products_js,
            "units": units,
            "categories": categories,
            "user": user,
            "error": error
        }
    )



# -------------------------------
# SUBMIT NOVA MOVIMENTAÇÃO
# -------------------------------
@router.post("/")
def movimentacoes_submit(
    request: Request,
    type_id: int = Form(...),
    unit_origem_id: int = Form(None),
    unit_destino_id: int = Form(None),
    item_id: Optional[str] = Form(None),  # recebe string
    tipo: str = Form(...),
    quantidade: int = Form(1),
    observacao: str = Form(""),
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

    # Descobre produto
    if item_id:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            return {"error": "Item não encontrado"}
        if not _is_master(user) and item.municipio_id != user.municipio_id:
            return {"error": "Sem permissão para movimentar este item"}
        product = item.product
    else:
        # Produto sem série
        product_q = db.query(Product).filter(Product.type_id == type_id)
        if not _is_master(user):
            product_q = product_q.filter(Product.municipio_id == user.municipio_id)
        product = product_q.first()
        if not product:
            return {"error": "Produto não encontrado"}

        if product.controla_por_serie:
            return {"error": "Item físico obrigatório para produtos controlados por série"}

        # Se produto sem série e não existe item, cria item "virtual"
        item = db.query(Item).filter(Item.product_id == product.id).first()
        if not item:
            item = Item(
                product_id=product.id,
                tombo=False,
                num_tombo_ou_serie=f"Produto sem série - {product.name}",
                unit_id=unit_origem_id,
                status="Disponível"
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
        return RedirectResponse(
            url=f"/movements/nova?error={quote(err_msg)}",
            status_code=HTTP_302_FOUND
        )

    registrar_log(
        db=db,
        usuario=user.email,
        acao=f"Registrou movimentação {tipo} do produto {product.name}",
        ip=request.client.host,
        user_agent=request.headers.get("user-agent"),
        tipo="operacional",
    )

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

    user_obj = _user_obj(db, user)
    if not user_obj:
        return RedirectResponse("/login")
    mov_municipio_id = movimento.product.municipio_id if movimento.product else (movimento.item.municipio_id if movimento.item else None)
    if not _is_master(user_obj) and mov_municipio_id != user_obj.municipio_id:
        return RedirectResponse("/movements/")

    products_q = db.query(Product)
    units_q = db.query(Unidade)
    if not _is_master(user_obj):
        products_q = products_q.filter(Product.municipio_id == user_obj.municipio_id)
        units_q = units_q.join(Unidade.orgao).filter(Unidade.orgao.has(municipio_id=user_obj.municipio_id))
    products = products_q.all()
    units = units_q.order_by(Unidade.nome).all()
    categories = db.query(Category).all()

    products_js = []

    for p in products:
        units_options = []

        if p.controla_por_serie:
            units_set = set()
            for item in p.items:
                if item.unit_id and item.unit_id not in units_set and item.unit:
                    units_options.append({
                        "unit_id": item.unit.id,
                        "unit_name": item.unit.nome
                    })
                    units_set.add(item.unit_id)
        else:
            units_set = set()
            stocks = db.query(Stock).filter(
                Stock.product_id == p.id,
                Stock.quantidade > 0
            ).all()
            for s in stocks:
                if s.unit_id and s.unit_id not in units_set and s.unit:
                    units_options.append({"unit_id": s.unit.id, "unit_name": s.unit.nome})
                    units_set.add(s.unit_id)

        products_js.append({
            "id": p.id,
            "name": p.name,
            "type_id": p.type_id,
            "type_name": p.type.nome if p.type else None,
            "category_id": p.category_id,
            "controla_por_serie": p.controla_por_serie,
            "units_options": units_options  # ✅ igual ao /nova
        })

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
            "products": products_js,
            "units": units,
            "categories": categories,
            "user": user
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
    mov_municipio_id = movimento.product.municipio_id if movimento.product else (movimento.item.municipio_id if movimento.item else None)
    if not _is_master(user) and mov_municipio_id != user.municipio_id:
        return {"error": "Sem permissão para editar esta movimentação"}

    product = None
    item = None

    if item_id:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            return {"error": "Item físico não encontrado"}
        if not _is_master(user) and item.municipio_id != user.municipio_id:
            return {"error": "Sem permissão para editar item de outro município"}
        product = item.product
        unit_origem_id = item.unit_id
        quantidade = 1
    else:
        product_q = db.query(Product).filter(Product.type_id == type_id)
        if not _is_master(user):
            product_q = product_q.filter(Product.municipio_id == user.municipio_id)
        product = product_q.first()
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
        ip=request.client.host,
        user_agent=request.headers.get("user-agent"),
        tipo="operacional",
    )

    return RedirectResponse(url="/movements/", status_code=HTTP_302_FOUND)


# -------------------------------
# DELETE MOVIMENTAÇÃO
# -------------------------------
@router.post("/delete/{movement_id}")
def delete_movement(
    movement_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return JSONResponse({"success": False, "message": "Usuário não autenticado."})

    user_obj = _user_obj(db, user)
    if not user_obj:
        return JSONResponse({"success": False, "message": "Usuário não autenticado."})

    movement = db.query(Movement).filter(Movement.id == movement_id).first()
    if not movement:
        return JSONResponse({"success": False, "message": "Movimentação não encontrada."})
    mov_municipio_id = movement.product.municipio_id if movement.product else (movement.item.municipio_id if movement.item else None)
    if not _is_master(user_obj) and mov_municipio_id != user_obj.municipio_id:
        return JSONResponse({"success": False, "message": "Sem permissão para excluir esta movimentação."})

    # Exemplo: bloquear exclusão se tiver regras específicas
    if movement.tipo == "Saída com Pendência":  # Exemplo
        return JSONResponse({"success": False, "message": "Não é possível excluir esta movimentação."})

    db.delete(movement)
    db.commit()

    registrar_log(
        db=db,
        usuario=user_obj.email,
        acao=f"Excluiu movimentação ID {movement_id}",
        ip=request.client.host,
        user_agent=request.headers.get("user-agent"),
        tipo="operacional",
    )

    return JSONResponse({"success": True})


# -------------------------------
# API AUXILIARES
# -------------------------------
@router.get("/movements/stock/type/{type_id}")
def get_product_stock(type_id: int, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    user_obj = _user_obj(db, user)
    if not user_obj:
        return []
    result = []

    # 1️⃣ Estoque por unidades (Stock)
    stocks = (
        db.query(Stock)
        .join(Product)
        .join(Unit)
        .filter(Product.type_id == type_id, Stock.quantidade > 0)
    )
    if not _is_master(user_obj):
        stocks = stocks.filter(Product.municipio_id == user_obj.municipio_id)
    stocks = stocks.all()

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
    )
    if not _is_master(user_obj):
        items = items.filter(Product.municipio_id == user_obj.municipio_id)
    items = items.group_by(Item.unit_id, Unit.name).all()

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
def get_product_items(type_id: int, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    user_obj = _user_obj(db, user)
    if not user_obj:
        return []
    items_result = []

    # 1️⃣ Itens físicos já cadastrados (controla por série ou não)
    items = (
        db.query(Item)
        .join(Product)
        .join(Unidade, Item.unit_id == Unidade.id)  # Só itens cuja unidade existe
        .filter(Product.type_id == type_id)
    )
    if not _is_master(user_obj):
        items = items.filter(Product.municipio_id == user_obj.municipio_id)
    items = items.all()

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
    )
    if not _is_master(user_obj):
        products_sem_serie = products_sem_serie.filter(Product.municipio_id == user_obj.municipio_id)
    products_sem_serie = products_sem_serie.all()

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
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    user_obj = _user_obj(db, user)
    if not user_obj:
        return []
    is_tombo = tipo.upper() == "TOMBO"

    items = (
        db.query(Item)
        .join(Product, Item.product_id == Product.id)
        .filter(
            Item.product_id == product_id,
            Item.tombo == is_tombo,
            Item.num_tombo_ou_serie.ilike(f"%{q}%")
        )
    )
    if not _is_master(user_obj):
        items = items.filter(Product.municipio_id == user_obj.municipio_id)
    items = items.limit(20).all()

    return [
        {
            "id": i.id,
            "text": i.num_tombo_ou_serie,
            "unit_id": i.unit_id,
            "unit_name": i.unit.nome
        }
        for i in items
    ]
