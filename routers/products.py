from typing import Optional

from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from database import get_db
from dependencies import get_current_user, registrar_log
from models import (
    Product, EquipmentType, Brand, Category, EquipmentState,
    Item, Movement, Stock, User, Unidade, Orgao, Municipio, Estado,
)
from templating import templates
from datetime import datetime

router = APIRouter(prefix="/products", tags=["Products"])


def _user_obj(db: Session, user: str):
    if not user:
        return None
    return db.query(User).filter(User.email == user).first()


def _brand_valid_for_type(db: Session, brand_id: int, type_id: int) -> bool:
    return (
        db.query(Brand)
        .filter(Brand.id == brand_id, Brand.equipment_types.any(EquipmentType.id == type_id))
        .first()
        is not None
    )


def _fmt_data(d) -> str:
    if not d:
        return "—"
    return d.strftime("%d/%m/%Y")


def _fmt_valor(val) -> str:
    if val is None:
        return "—"
    txt = f"{val:,.2f}"
    return "R$ " + txt.replace(",", "§").replace(".", ",").replace("§", ".")


def _product_list_display(product: Product) -> dict:
    """Dados agregados para exibição na grid (unidade/data/valor sem repetição)."""
    unidade = "—"
    data_aquisicao = "—"
    valor = "—"
    seen_units = set()

    for item in product.items or []:
        if item.unit and item.unit.name not in seen_units:
            seen_units.add(item.unit.name)
            if unidade == "—":
                unidade = item.unit.name
        if data_aquisicao == "—" and item.data_aquisicao:
            data_aquisicao = _fmt_data(item.data_aquisicao)
        if valor == "—" and item.valor_aquisicao is not None:
            valor = _fmt_valor(item.valor_aquisicao)

    return {
        "categoria": product.category.nome if product.category else "—",
        "unidade": unidade,
        "data_aquisicao": data_aquisicao,
        "valor": valor,
    }


# ----------------- LIST -----------------
@router.get("/")
def list_products(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    products = (
        db.query(Product)
        .options(
            joinedload(Product.category),
            joinedload(Product.type),
            joinedload(Product.brand),
            joinedload(Product.items).joinedload(Item.unit),
        )
        .all()
    )

    tipos = sorted({p.type.nome for p in products if p.type})
    marcas = sorted({p.brand.nome for p in products if p.brand})
    categorias = sorted({p.category.nome for p in products if p.category})

    products_view = [
        {"product": p, **_product_list_display(p)}
        for p in products
    ]

    return templates.TemplateResponse(
        "products_list.html",
        {
            "request": request,
            "products": products_view,
            "user": user,
            "tipos": tipos,
            "marcas": marcas,
            "categorias": categorias,
            "hide_app_header": True,
        }
    )


# ----------------- ADD FORM -----------------
@router.get("/add")
def add_product_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    user_obj = _user_obj(db, user)
    if not user_obj:
        return RedirectResponse("/login")

    is_master = getattr(user_obj, "perfil", None) == "master"

    # Lotação do usuário (para exibição quando não for Master)
    lotacao = None
    if not is_master:
        unidade = db.query(Unidade).filter(Unidade.id == user_obj.unidade_id).first()
        orgao = (
            db.query(Orgao)
            .options(joinedload(Orgao.municipio).joinedload(Municipio.estado))
            .filter(Orgao.id == user_obj.orgao_id)
            .first()
        )
        if unidade and orgao and orgao.municipio and orgao.municipio.estado:
            lotacao = {
                "estado": orgao.municipio.estado.nome,
                "municipio": orgao.municipio.nome,
                "orgao": orgao.nome,
                "unidade": unidade.nome,
            }

    # Unidades: sempre do órgão ao qual o usuário está cadastrado (para não-Master).
    # Master carrega Unidade via JS conforme o Órgão selecionado.
    if is_master:
        units = []  # preenchido no front por /api/unidades/{orgao_id}
    else:
        units = (
            db.query(Unidade)
            .filter(Unidade.orgao_id == user_obj.orgao_id, Unidade.ativo == True)
            .order_by(Unidade.nome)
            .all()
        )

    # Estados geográficos (para Master escolher Estado/Município/Órgão/Unidade)
    estados_geograficos = db.query(Estado).order_by(Estado.nome).all() if is_master else []

    categorias = db.query(Category).order_by(Category.nome).all()
    tipos = db.query(EquipmentType).all()
    estados = db.query(EquipmentState).all()  # estado físico do item (equipment_states)

    return templates.TemplateResponse(
        "product_form.html",
        {
            "request": request,
            "action": "add",
            "categories": categorias,
            "tipos": tipos,
            "estados": estados,
            "units": units,
            "lotacao": lotacao,
            "is_master": is_master,
            "estados_geograficos": estados_geograficos,
            "default_unidade_id": user_obj.unidade_id if not is_master else None,
            "product": None,
            "item": None,
            "stock": None,
            "product_items": [],
            "user": user,
            "hide_app_header": True,
        }
    )


def _unidade_scope_ok(db: Session, user_obj: User, unidade: Unidade) -> bool:
    """Master: qualquer unidade. Demais: apenas unidades do órgão do usuário."""
    if not user_obj or not unidade:
        return False
    if getattr(user_obj, "perfil", None) == "master":
        return True
    return unidade.orgao_id == user_obj.orgao_id


def _parse_int(val, default=None):
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _parse_float(val, default=None):
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ----------------- ADD PRODUCT -----------------
@router.post("/add")
async def add_product(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    form_data = await request.form()
    # Listas de tombos/séries: o form envia numero[], tipo_numero[], estado_id[] e status[] (por linha)
    numero = form_data.getlist("numero[]") or form_data.getlist("numero")
    tipo_numero = form_data.getlist("tipo_numero[]") or form_data.getlist("tipo_numero")
    estado_id_list = form_data.getlist("estado_id[]")
    status_list = form_data.getlist("status[]")

    category_id = _parse_int(form_data.get("category_id"))
    type_id = _parse_int(form_data.get("type_id")) or 0
    brand_id = _parse_int(form_data.get("brand_id")) or 0
    model = form_data.get("model") or ""
    description = form_data.get("description") or ""
    controla_por_serie = form_data.get("controla_por_serie") in ("true", "on", "1", "sim", "yes")
    unit_id = _parse_int(form_data.get("unit_id"))
    quantidade = _parse_int(form_data.get("quantidade"), 0) or 0
    quantidade_minima = _parse_int(form_data.get("quantidade_minima"), 0) or 0
    unit_id_serie = _parse_int(form_data.get("unit_id_serie"))
    estado_id = _parse_int(form_data.get("estado_id"))
    status = form_data.get("status") or "Disponível"
    data_aquisicao = form_data.get("data_aquisicao") or None
    valor_aquisicao = _parse_float(form_data.get("valor_aquisicao"))
    garantia_ate = form_data.get("garantia_ate") or None
    observacao = form_data.get("observacao") or None

    if not type_id or not brand_id:
        return HTMLResponse(
            content="<script>alert('Tipo e Marca são obrigatórios.'); history.back();</script>",
            status_code=400,
        )

    user_obj = _user_obj(db, user)
    if not user_obj:
        return RedirectResponse("/login")

    target_unit_id = unit_id_serie if controla_por_serie else unit_id
    if not target_unit_id:
        return HTMLResponse(
            content="<script>alert('Unidade é obrigatória.'); history.back();</script>",
            status_code=400,
        )

    unidade = (
        db.query(Unidade)
        .options(joinedload(Unidade.orgao).joinedload(Orgao.municipio))
        .filter(Unidade.id == int(target_unit_id))
        .first()
    )
    if not unidade or not unidade.orgao or not unidade.orgao.municipio:
        return HTMLResponse(
            content="<script>alert('Unidade inválida.'); history.back();</script>",
            status_code=400,
        )
    if not _unidade_scope_ok(db, user_obj, unidade):
        return HTMLResponse(
            content="<script>alert('Você não tem permissão para cadastrar nesta unidade.'); history.back();</script>",
            status_code=403,
        )

    tipo = db.query(EquipmentType).filter(EquipmentType.id == type_id).first()
    marca = db.query(Brand).filter(Brand.id == brand_id).first()
    if not marca or not _brand_valid_for_type(db, brand_id, type_id):
        return HTMLResponse(
            content="<script>alert('Marca inválida para o tipo selecionado.'); history.back();</script>",
            status_code=400,
        )
    nome_partes = [tipo.nome if tipo else "", marca.nome if marca else "", model or ""]
    name = " ".join(filter(None, nome_partes)) or "Produto sem nome"

    municipio_id = unidade.orgao.municipio_id
    orgao_id = unidade.orgao_id

    product = Product(
        name=name,
        category_id=category_id,
        type_id=type_id,
        brand_id=brand_id,
        model=model,
        description=description,
        controla_por_serie=controla_por_serie,
        quantidade=0 if controla_por_serie else quantidade,
        quantidade_minima=0 if controla_por_serie else quantidade_minima,
        municipio_id=municipio_id,
        orgao_id=orgao_id,
        created_by=user_obj.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    if controla_por_serie:
        items_criados = 0
        data_aq = None
        if data_aquisicao:
            try:
                data_aq = datetime.strptime(str(data_aquisicao).strip(), "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
        garantia_dt = None
        if garantia_ate:
            try:
                garantia_dt = datetime.strptime(str(garantia_ate).strip(), "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
        for i, num in enumerate(numero):
            num_str = (num if isinstance(num, str) else str(num or "")).strip()
            if not num_str:
                continue
            tipo_val = (tipo_numero[i] if i < len(tipo_numero) else "tombo")
            is_tombo = (str(tipo_val).lower() == "tombo")
            estado_i = _parse_int(estado_id_list[i]) if i < len(estado_id_list) else estado_id
            status_i = (status_list[i] or "Disponível") if i < len(status_list) else status
            item = Item(
                product_id=product.id,
                municipio_id=municipio_id,
                orgao_id=orgao_id,
                unit_id=unidade.id,
                tombo=is_tombo,
                num_tombo_ou_serie=num_str,
                estado_id=estado_i,
                status=status_i,
                data_aquisicao=data_aq,
                valor_aquisicao=valor_aquisicao,
                garantia_ate=garantia_dt,
                observacao=observacao,
            )
            db.add(item)
            items_criados += 1
        db.commit()
        registrar_log(db, usuario=user, acao=f"Cadastrou produto em lote: {product.name} ({items_criados} itens)", ip=request.client.host)
    else:
        stock = Stock(
            product_id=product.id,
            municipio_id=municipio_id,
            orgao_id=orgao_id,
            unit_id=unidade.id,
            quantidade=quantidade,
            quantidade_minima=quantidade_minima,
            localizacao=None,
        )
        db.add(stock)
        db.commit()
        data_aq = None
        if data_aquisicao:
            try:
                data_aq = datetime.strptime(str(data_aquisicao).strip(), "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
        garantia_dt = None
        if garantia_ate:
            try:
                garantia_dt = datetime.strptime(str(garantia_ate).strip(), "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
        item = Item(
            product_id=product.id,
            municipio_id=municipio_id,
            orgao_id=orgao_id,
            unit_id=unidade.id,
            tombo=False,
            num_tombo_ou_serie=None,
            estado_id=estado_id,
            status=status,
            data_aquisicao=data_aq,
            valor_aquisicao=valor_aquisicao,
            garantia_ate=garantia_dt,
            observacao=observacao or f"Estoque inicial: {quantidade}",
        )
        db.add(item)
        product.quantidade = quantidade
        product.quantidade_minima = quantidade_minima
        db.commit()
        registrar_log(db, usuario=user, acao=f"Cadastrou produto: {product.name}", ip=request.client.host)

    return RedirectResponse("/products", status_code=HTTP_302_FOUND)


# ----------------- EDIT FORM -----------------
@router.get("/edit/{product_id}")
def edit_product_form(product_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    user_obj = _user_obj(db, user)
    if not user_obj:
        return RedirectResponse("/login")

    product = db.query(Product).options(
        joinedload(Product.orgao).joinedload(Orgao.municipio).joinedload(Municipio.estado),
        joinedload(Product.items),
        joinedload(Product.stocks),
    ).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse("/products")
    if product.controla_por_serie:
        product_items = list(product.items) if product.items else []
        stock = None
        item = product_items[0] if product_items else None
    else:
        product_items = []
        stock = db.query(Stock).filter(Stock.product_id == product_id).first()
        item = db.query(Item).filter(Item.product_id == product_id).first()

    is_master = getattr(user_obj, "perfil", None) == "master"
    lotacao = None
    if product.orgao and product.orgao.municipio and product.orgao.municipio.estado:
        lotacao = {
            "estado": product.orgao.municipio.estado.nome,
            "municipio": product.orgao.municipio.nome,
            "orgao": product.orgao.nome,
            "unidade": "-",
        }
    if item and item.unit:
        lotacao["unidade"] = item.unit.nome if lotacao else "-"
    elif stock and stock.unit_id and lotacao:
        un = db.query(Unidade).filter(Unidade.id == stock.unit_id).first()
        if un:
            lotacao["unidade"] = un.nome

    # Unidades do órgão do produto (sempre do órgão ao qual o produto pertence)
    units = (
        db.query(Unidade)
        .filter(Unidade.orgao_id == product.orgao_id, Unidade.ativo == True)
        .order_by(Unidade.nome)
        .all()
    )
    estados_geograficos = db.query(Estado).order_by(Estado.nome).all() if is_master else []
    if product.controla_por_serie and product_items:
        default_unidade_id = product_items[0].unit_id
    else:
        default_unidade_id = (stock.unit_id if stock else None) or (item.unit_id if item else None)

    categorias = db.query(Category).order_by(Category.nome).all()
    tipos = db.query(EquipmentType).all()
    estados = db.query(EquipmentState).all()

    return templates.TemplateResponse(
        "product_form.html",
        {
            "request": request,
            "action": "edit",
            "categories": categorias,
            "tipos": tipos,
            "estados": estados,
            "units": units,
            "lotacao": lotacao,
            "is_master": is_master,
            "estados_geograficos": estados_geograficos,
            "default_unidade_id": default_unidade_id,
            "product": product,
            "item": item,
            "product_items": product_items,
            "stock": stock,
            "user": user,
            "hide_app_header": True,
        }
    )


# ----------------- EDIT PRODUCT -----------------
@router.post("/edit/{product_id}")
async def edit_product(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    user_obj = _user_obj(db, user)
    if not user_obj:
        return RedirectResponse("/login")

    form_data = await request.form()

    # --- Produto ---
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse("/products")

    category_id = form_data.get("category_id")
    type_id = _parse_int(form_data.get("type_id")) or 0
    brand_id = _parse_int(form_data.get("brand_id")) or 0
    model = form_data.get("model") or ""
    description = form_data.get("description") or ""
    controla_por_serie = form_data.get("controla_por_serie") in ("true", "on", "1", "sim", "yes")
    unit_id = form_data.get("unit_id")
    unit_id_serie = form_data.get("unit_id_serie")
    estado_id = form_data.get("estado_id")
    status = form_data.get("status") or "Disponível"
    data_aquisicao = form_data.get("data_aquisicao")
    valor_aquisicao = form_data.get("valor_aquisicao")
    garantia_ate = form_data.get("garantia_ate")
    observacao = form_data.get("observacao")
    quantidade = _parse_int(form_data.get("quantidade"), 0) or 0
    quantidade_minima = _parse_int(form_data.get("quantidade_minima"), 0) or 0

    # Nome do produto
    tipo = db.query(EquipmentType).filter(EquipmentType.id == type_id).first()
    marca = db.query(Brand).filter(Brand.id == brand_id).first()
    if not marca or not _brand_valid_for_type(db, brand_id, type_id):
        return HTMLResponse(
            content="<script>alert('Marca inválida para o tipo selecionado.'); history.back();</script>",
            status_code=400,
        )
    nome_partes = []
    if tipo:
        nome_partes.append(tipo.nome)
    if marca:
        nome_partes.append(marca.nome)
    if model:
        nome_partes.append(model)
    product.name = " ".join(nome_partes) if nome_partes else "Produto sem nome"
    product.category_id = int(category_id) if category_id else None
    product.type_id = type_id
    product.brand_id = brand_id
    product.model = model
    product.description = description
    product.controla_por_serie = controla_por_serie
    if not controla_por_serie:
        product.quantidade = quantidade
        product.quantidade_minima = quantidade_minima

    unit_id_int = _parse_int(unit_id) or _parse_int(unit_id_serie)
    data_aq = None
    if data_aquisicao:
        try:
            data_aq = datetime.strptime(data_aquisicao, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass
    valor_float = None
    if valor_aquisicao:
        valor_clean = str(valor_aquisicao).replace("R$", "").replace(".", "").replace(",", ".").strip()
        valor_float = _parse_float(valor_clean)
    garantia_dt = None
    if garantia_ate:
        try:
            garantia_dt = datetime.strptime(garantia_ate, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass
    estado_int = _parse_int(estado_id)
    status_val = status or "Disponível"

    if controla_por_serie:
        numeros = form_data.getlist("numero[]") or form_data.getlist("numero")
        tipo_numeros = form_data.getlist("tipo_numero[]") or form_data.getlist("tipo_numero")
        estado_id_list = form_data.getlist("estado_id[]")
        status_list = form_data.getlist("status[]")

        if not unit_id_int:
            return HTMLResponse(
                content="<script>alert('Selecione a Unidade antes de salvar.'); history.back();</script>",
                status_code=400,
            )

        existing_items = db.query(Item).filter(Item.product_id == product.id).order_by(Item.id).all()
        pares = []
        for i, num in enumerate(numeros):
            num_str = (num if isinstance(num, str) else str(num or "")).strip()
            if not num_str:
                continue
            tipo_val = tipo_numeros[i] if i < len(tipo_numeros) else "tombo"
            is_tombo = str(tipo_val).lower() == "tombo"
            pares.append((is_tombo, num_str))

        # Primeiro libera num_tombo_ou_serie nos itens existentes (evita UniqueViolation ao trocar ordem)
        for idx in range(min(len(pares), len(existing_items))):
            existing_items[idx].num_tombo_ou_serie = None
        db.flush()

        for idx, (is_tombo, num_str) in enumerate(pares):
            estado_idx = _parse_int(estado_id_list[idx]) if idx < len(estado_id_list) else estado_int
            status_idx = (status_list[idx] or "Disponível") if idx < len(status_list) else status_val
            if idx < len(existing_items):
                it = existing_items[idx]
                it.tombo = is_tombo
                it.num_tombo_ou_serie = num_str
                it.unit_id = unit_id_int
                it.municipio_id = product.municipio_id
                it.orgao_id = product.orgao_id
                it.estado_id = estado_idx
                it.status = status_idx
                it.data_aquisicao = data_aq
                it.valor_aquisicao = valor_float
                it.garantia_ate = garantia_dt
                it.observacao = observacao or None
                db.add(it)
            else:
                novo = Item(
                    product_id=product.id,
                    municipio_id=product.municipio_id,
                    orgao_id=product.orgao_id,
                    unit_id=unit_id_int,
                    tombo=is_tombo,
                    num_tombo_ou_serie=num_str,
                    estado_id=estado_idx,
                    status=status_idx,
                    data_aquisicao=data_aq,
                    valor_aquisicao=valor_float,
                    garantia_ate=garantia_dt,
                    observacao=observacao or None,
                )
                db.add(novo)

        if len(pares) < len(existing_items):
            for it in existing_items[len(pares):]:
                db.delete(it)

        db.commit()
    else:
        item = db.query(Item).filter(Item.product_id == product.id).first()
        if not item:
            if not unit_id_int:
                return HTMLResponse(
                    content="<script>alert('Selecione a Unidade antes de salvar o produto.'); history.back();</script>",
                    status_code=400,
                )
            item = Item(
                product_id=product.id,
                municipio_id=product.municipio_id,
                orgao_id=product.orgao_id,
                unit_id=unit_id_int,
            )
        else:
            if not item.municipio_id:
                item.municipio_id = product.municipio_id
            if not item.orgao_id:
                item.orgao_id = product.orgao_id
            if unit_id_int is not None:
                item.unit_id = unit_id_int
            if not item.unit_id:
                return HTMLResponse(
                    content="<script>alert('Item associado ao produto está sem Unidade. Defina uma Unidade e tente novamente.'); history.back();</script>",
                    status_code=400,
                )

        item.tombo = False
        item.num_tombo_ou_serie = None
        item.estado_id = estado_int
        item.status = status_val
        item.data_aquisicao = data_aq
        item.valor_aquisicao = valor_float
        item.garantia_ate = garantia_dt
        item.observacao = observacao or None
        db.add(item)

        stock_row = db.query(Stock).filter(Stock.product_id == product.id).first()
        if not stock_row:
            if not unit_id_int:
                return HTMLResponse(
                    content="<script>alert('Selecione a Unidade antes de salvar o produto.'); history.back();</script>",
                    status_code=400,
                )
            stock_row = Stock(
                product_id=product.id,
                municipio_id=product.municipio_id,
                orgao_id=product.orgao_id,
                unit_id=unit_id_int,
                quantidade=quantidade,
                quantidade_minima=quantidade_minima,
            )
            db.add(stock_row)
        else:
            if unit_id_int is not None:
                stock_row.unit_id = unit_id_int
            stock_row.quantidade = quantidade
            stock_row.quantidade_minima = quantidade_minima
            db.add(stock_row)

        db.commit()

    registrar_log(db, usuario=user, acao=f"Editou produto: {product.name}", ip=request.client.host)
    return RedirectResponse("/products", status_code=HTTP_302_FOUND)

@router.get("/tipos-por-categoria/{category_id}")
def get_tipos_por_categoria(category_id: int, db: Session = Depends(get_db)):
    """Retorna tipos de equipamento de uma categoria específica"""
    tipos = (
        db.query(EquipmentType)
        .filter(EquipmentType.category_id == category_id)
        .order_by(EquipmentType.nome)
        .all()
    )

    return [{"id": t.id, "nome": t.nome} for t in tipos]


@router.get("/marcas-por-tipo/{type_id}")
def get_marcas_por_tipo(
    type_id: int,
    include_brand_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Retorna marcas vinculadas ao tipo de equipamento."""
    marcas = (
        db.query(Brand)
        .filter(Brand.equipment_types.any(EquipmentType.id == type_id))
        .order_by(Brand.nome)
        .all()
    )
    ids = {m.id for m in marcas}
    if include_brand_id and include_brand_id not in ids:
        extra = db.query(Brand).filter(Brand.id == include_brand_id).first()
        if extra:
            marcas = sorted(list(marcas) + [extra], key=lambda m: m.nome.lower())
    return [{"id": m.id, "nome": m.nome} for m in marcas]


# ----------------- DELETE -----------------
@router.post("/delete/{product_id}")
def delete_product(product_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return JSONResponse({"success": False, "message": "Usuário não autenticado."})

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return JSONResponse({"success": False, "message": "Produto não encontrado."})

    item_ids = [
        row[0]
        for row in db.query(Item.id).filter(Item.product_id == product.id).all()
    ]
    filtros_mov = [Movement.product_id == product.id]
    if item_ids:
        filtros_mov.append(Movement.item_id.in_(item_ids))
    tem_movimentacao = db.query(Movement).filter(or_(*filtros_mov)).first()
    if tem_movimentacao:
        return JSONResponse({
            "success": False,
            "message": "Produto possui movimentações registradas e não pode ser excluído.",
        })

    estoque_qtd = (
        db.query(Stock)
        .filter(Stock.product_id == product.id, Stock.quantidade > 0)
        .count()
    )
    if estoque_qtd > 0:
        return JSONResponse({
            "success": False,
            "message": (
                f"Produto possui estoque ativo ({estoque_qtd} registro(s) com quantidade maior que zero). "
                "Zere ou transfira o estoque antes de excluir."
            ),
        })

    nome_produto = product.name

    try:
        db.query(Stock).filter(Stock.product_id == product.id).delete(
            synchronize_session=False
        )
        db.query(Item).filter(Item.product_id == product.id).delete(
            synchronize_session=False
        )
        db.delete(product)
        db.commit()
    except IntegrityError:
        db.rollback()
        return JSONResponse({
            "success": False,
            "message": "Não foi possível excluir: o produto ainda possui vínculos no sistema.",
        })

    registrar_log(
        db,
        usuario=user,
        acao=f"Excluiu produto: {nome_produto}",
        ip=request.client.host,
    )
    return JSONResponse({"success": True, "message": "Produto excluído com sucesso."})
