from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session, joinedload
from database import get_db
from dependencies import get_current_user, registrar_log
from models import (
    Product, EquipmentType, Brand, Category, EquipmentState,
    Item, Movement, Stock, User, Unidade, Orgao, Municipio, Estado,
)
from fastapi.templating import Jinja2Templates
from datetime import datetime

router = APIRouter(prefix="/products", tags=["Products"])
templates = Jinja2Templates(directory="templates")


def _user_obj(db: Session, user: str):
    if not user:
        return None
    return db.query(User).filter(User.email == user).first()

# ----------------- LIST -----------------
@router.get("/")
def list_products(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    
    products = db.query(Product).all()

    # FILTROS: coletamos valores únicos
    tipos = sorted({p.type.nome for p in products if p.type})
    marcas = sorted({p.brand.nome for p in products if p.brand})

    estados_set = set()
    status_set = set()
    for p in products:
        for item in getattr(p, "items", []):
            if item.estado:
                estados_set.add(item.estado.nome)
            if item.status:
                status_set.add(item.status)
    estados = sorted(estados_set)
    status_list = sorted(status_set)

    return templates.TemplateResponse(
        "products_list.html",
        {
            "request": request,
            "products": products,
            "user": user,
            "tipos": tipos,
            "marcas": marcas,
            "estados": estados,
            "status_list": status_list
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
    marcas = db.query(Brand).all()
    estados = db.query(EquipmentState).all()  # estado físico do item (equipment_states)

    return templates.TemplateResponse(
        "product_form.html",
        {
            "request": request,
            "action": "add",
            "categories": categorias,
            "tipos": tipos,
            "marcas": marcas,
            "estados": estados,
            "units": units,
            "lotacao": lotacao,
            "is_master": is_master,
            "estados_geograficos": estados_geograficos,
            "default_unidade_id": user_obj.unidade_id if not is_master else None,
            "product": None,
            "item": None,
            "user": user,
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
    # Listas de tombos/séries: o form envia nome "numero[]" e "tipo_numero[]" (vários valores)
    numero = form_data.getlist("numero[]") or form_data.getlist("numero")
    tipo_numero = form_data.getlist("tipo_numero[]") or form_data.getlist("tipo_numero")

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
            item = Item(
                product_id=product.id,
                municipio_id=municipio_id,
                orgao_id=orgao_id,
                unit_id=unidade.id,
                tombo=is_tombo,
                num_tombo_ou_serie=num_str,
                estado_id=estado_id,
                status=status,
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
            estado_id=None,
            status="Disponível",
            data_aquisicao=data_aq,
            valor_aquisicao=valor_aquisicao,
            garantia_ate=garantia_dt,
            observacao=observacao or f"Estoque inicial: {quantidade}",
        )
        db.add(item)
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
    ).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse("/products")
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

    # Unidades do órgão do produto (sempre do órgão ao qual o produto pertence)
    units = (
        db.query(Unidade)
        .filter(Unidade.orgao_id == product.orgao_id, Unidade.ativo == True)
        .order_by(Unidade.nome)
        .all()
    )
    estados_geograficos = db.query(Estado).order_by(Estado.nome).all() if is_master else []
    default_unidade_id = item.unit_id if item else None

    categorias = db.query(Category).order_by(Category.nome).all()
    tipos = db.query(EquipmentType).all()
    marcas = db.query(Brand).all()
    estados = db.query(EquipmentState).all()

    return templates.TemplateResponse(
        "product_form.html",
        {
            "request": request,
            "action": "edit",
            "categories": categorias,
            "tipos": tipos,
            "marcas": marcas,
            "estados": estados,
            "units": units,
            "lotacao": lotacao,
            "is_master": is_master,
            "estados_geograficos": estados_geograficos,
            "default_unidade_id": default_unidade_id,
            "product": product,
            "item": item,
            "user": user,
        }
    )


# ----------------- EDIT PRODUCT -----------------
@router.post("/edit/{product_id}")
def edit_product(
    product_id: int,
    request: Request,
    category_id: int = Form(None),
    type_id: int = Form(...),
    brand_id: int = Form(...),
    model: str = Form(...),
    estado_id: str = Form(None),
    status: str = Form(None),
    unit_id: str = Form(None),
    data_aquisicao: str = Form(None),
    valor_aquisicao: str = Form(None),
    description: str = Form(...),
    controla_por_serie: bool = Form(False),
    tombo: str = Form(None),
    num_tombo: str = Form(None),
    num_serie: str = Form(None),
    garantia_ate: str = Form(None),
    observacao: str = Form(None),
    quantidade: str = Form("0"),
    quantidade_minima: str = Form("0"),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    user_obj = _user_obj(db, user)
    if not user_obj:
        return RedirectResponse("/login")

    # --- Produto ---
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse("/products")

    # ✅ Gera nome automaticamente
    tipo = db.query(EquipmentType).filter(EquipmentType.id == type_id).first()
    marca = db.query(Brand).filter(Brand.id == brand_id).first()
    
    nome_partes = []
    if tipo:
        nome_partes.append(tipo.nome)
    if marca:
        nome_partes.append(marca.nome)
    if model:
        nome_partes.append(model)
    
    product.name = " ".join(nome_partes) if nome_partes else "Produto sem nome"
    product.category_id = int(category_id) if category_id else None
    product.type_id = int(type_id)
    product.brand_id = int(brand_id)
    product.model = model
    product.description = description
    product.controla_por_serie = controla_por_serie

    if not controla_por_serie:
        product.quantidade = int(quantidade or 0)
        product.quantidade_minima = int(quantidade_minima or 0)

    # --- Item físico ---
    item = db.query(Item).filter(Item.product_id == product.id).first()
    unit_id_int = int(unit_id) if unit_id else None

    if not item:
        # Se não existe item ainda, precisamos de unidade para criar um novo
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
        # Garante que campos NOT NULL sejam sempre preenchidos
        if not item.municipio_id:
            item.municipio_id = product.municipio_id
        if not item.orgao_id:
            item.orgao_id = product.orgao_id
        if unit_id_int:
            item.unit_id = unit_id_int
        if not item.unit_id:
            return HTMLResponse(
                content="<script>alert('Item associado ao produto está sem Unidade. Defina uma Unidade e tente novamente.'); history.back();</script>",
                status_code=400,
            )

    is_tombo = (tombo == "Sim")

    item.tombo = is_tombo if controla_por_serie else False
    item.num_tombo_ou_serie = (num_tombo if is_tombo else num_serie) if controla_por_serie else None
    item.estado_id = int(estado_id) if estado_id else None
    item.unit_id = int(unit_id) if unit_id else None
    item.status = status or "Disponível"

    if data_aquisicao:
        try:
            item.data_aquisicao = datetime.strptime(data_aquisicao, "%Y-%m-%d").date()
        except:
            item.data_aquisicao = None
    else:
        item.data_aquisicao = None

    if valor_aquisicao:
        valor_clean = valor_aquisicao.replace("R$", "").replace(".", "").replace(",", ".").strip()
        try:
            item.valor_aquisicao = float(valor_clean)
        except:
            item.valor_aquisicao = None
    else:
        item.valor_aquisicao = None

    item.garantia_ate = garantia_ate or None
    item.observacao = observacao or None

    db.add(item)
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
    
    return [
        {
            "id": t.id,
            "nome": t.nome
        }
        for t in tipos
    ]


# ----------------- DELETE -----------------
@router.post("/delete/{product_id}")
def delete_product(product_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return JSONResponse({"success": False, "message": "Usuário não autenticado."})

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return JSONResponse({"success": False, "message": "Produto não encontrado."})

    movimentacoes = db.query(Movement).filter(Movement.product_id == product.id).first()
    if movimentacoes:
        return JSONResponse({"success": False, "message": "Produto possui movimentações e não pode ser excluído."})

    estoque = db.query(Stock).filter(Stock.product_id == product.id).first()
    if estoque:
        return JSONResponse({"success": False, "message": "Produto possui estoque registrado e não pode ser excluído."})

    item = db.query(Item).filter(Item.product_id == product.id).first()
    if item:
        db.delete(item)

    db.delete(product)
    db.commit()

    registrar_log(db, usuario=user, acao=f"Excluiu produto: {product.name}", ip=request.client.host)
    return JSONResponse({"success": True})
