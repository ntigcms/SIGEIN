from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from database import get_db
from dependencies import get_current_user, registrar_log
from models import (
    Product, EquipmentType, Brand, Category, EquipmentState,
    Item, Movement, Stock, User, Unidade, Orgao, Municipio,
)
from fastapi.templating import Jinja2Templates
from datetime import datetime

router = APIRouter(prefix="/products", tags=["Products"])
templates = Jinja2Templates(directory="templates")

PERFIL_MASTER = "master"
PERFIL_GESTOR_MUNICIPAL = "admin_municipal"


def _user_obj(db: Session, user: str):
    """Retorna o objeto User a partir do email da sessão."""
    if not user:
        return None
    return db.query(User).filter(User.email == user).first()

def _scope_products_query(db: Session, user_obj: User):
    """
    Define escopo de produtos por perfil:
    - master: todos
    - admin_municipal (Gestor Municipal): todos do município
    - demais: da unidade (com fallback para produtos antigos sem unidade_id)
    """
    q = db.query(Product).options(
        joinedload(Product.type),
        joinedload(Product.brand),
        joinedload(Product.unit),
        joinedload(Product.orgao).joinedload(Orgao.municipio).joinedload(Municipio.estado),
    )
    if not user_obj:
        return q.filter(Product.id == -1)

    perfil = getattr(user_obj, "perfil", None)
    if perfil == PERFIL_MASTER:
        return q
    if perfil == PERFIL_GESTOR_MUNICIPAL:
        return q.filter(Product.municipio_id == user_obj.municipio_id)

    return q.filter(
        or_(
            Product.unidade_id == user_obj.unidade_id,
            # fallback para registros antigos que ainda não tenham unidade_id preenchida
            (Product.unidade_id.is_(None)) & (Product.orgao_id == user_obj.orgao_id),
        )
    )

def _scope_unidades_query(db: Session, user_obj: User):
    """
    Define escopo de unidades por perfil:
    - master: todas
    - admin_municipal: todas do município do usuário
    - demais: somente a unidade do usuário
    """
    q = db.query(Unidade).order_by(Unidade.nome)
    if not user_obj:
        return q.filter(Unidade.id == -1)
    perfil = getattr(user_obj, "perfil", None)
    if perfil == PERFIL_MASTER:
        return q
    if perfil == PERFIL_GESTOR_MUNICIPAL:
        return q.join(Orgao, Unidade.orgao_id == Orgao.id).filter(Orgao.municipio_id == user_obj.municipio_id)
    return q.filter(Unidade.id == user_obj.unidade_id)

def _validate_unidade_scope(db: Session, user_obj: User, unidade: Unidade):
    if not user_obj or not unidade:
        return False
    perfil = getattr(user_obj, "perfil", None)
    if perfil == PERFIL_MASTER:
        return True
    if perfil == PERFIL_GESTOR_MUNICIPAL:
        orgao = db.query(Orgao).filter(Orgao.id == unidade.orgao_id).first()
        return bool(orgao and orgao.municipio_id == user_obj.municipio_id)
    return unidade.id == user_obj.unidade_id


# ----------------- LIST -----------------
@router.get("/")
def list_products(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    user_obj = _user_obj(db, user)
    if not user_obj:
        return RedirectResponse("/login")

    products = _scope_products_query(db, user_obj).all()

    tipos = sorted({p.type.nome for p in products if p.type})
    marcas = sorted({p.brand.nome for p in products if p.brand})
    estados_set = set()
    status_set = set()
    unidades_set = set()
    for p in products:
        if getattr(p, "unit", None) and p.unit and p.unit.nome:
            unidades_set.add(p.unit.nome)
        for item in getattr(p, "items", []):
            if item.estado:
                estados_set.add(item.estado.nome)
            if item.status:
                status_set.add(item.status)
            if getattr(item, "unit", None) and item.unit and item.unit.nome:
                unidades_set.add(item.unit.nome)
    estados = sorted(estados_set)
    status_list = sorted(status_set)
    unidades = sorted(unidades_set)

    return templates.TemplateResponse(
        "products_list.html",
        {
            "request": request,
            "products": products,
            "user": user,
            "tipos": tipos,
            "marcas": marcas,
            "estados": estados,
            "status_list": status_list,
            "unidades": unidades,
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

    # Lotação do usuário (default do cadastro)
    unidade = db.query(Unidade).filter(Unidade.id == user_obj.unidade_id).first()
    orgao = (
        db.query(Orgao)
        .options(joinedload(Orgao.municipio).joinedload(Municipio.estado))
        .filter(Orgao.id == user_obj.orgao_id)
        .first()
    )
    lotacao = None
    if unidade and orgao and orgao.municipio and orgao.municipio.estado:
        lotacao = {
            "estado": orgao.municipio.estado.nome,
            "municipio": orgao.municipio.nome,
            "orgao": orgao.nome,
            "unidade": unidade.nome,
        }

    categorias = db.query(Category).order_by(Category.nome).all()
    tipos = db.query(EquipmentType).all()
    marcas = db.query(Brand).all()
    estados = db.query(EquipmentState).all()
    # Lista de unidades conforme perfil (Master: todas; Gestor Municipal: município; demais: sua unidade)
    unidades = _scope_unidades_query(db, user_obj).all()

    return templates.TemplateResponse(
        "product_form.html",
        {
            "request": request,
            "action": "add",
            "categories": categorias,
            "tipos": tipos,
            "marcas": marcas,
            "estados": estados,
            "units": unidades,
            "lotacao": lotacao,
            "default_unidade_id": user_obj.unidade_id,
            "product": None,
            "item": None,
            "user": user,
        }
    )


# ----------------- ADD PRODUCT -----------------
@router.post("/add")
async def add_product(
    request: Request,
    category_id: int = Form(None),
    type_id: int = Form(...),
    brand_id: int = Form(...),
    model: str = Form(None),
    description: str = Form(None),
    controla_por_serie: bool = Form(False),
    unit_id: int = Form(None),
    quantidade: int = Form(0),
    quantidade_minima: int = Form(0),
    unit_id_serie: int = Form(None),
    estado_id: int = Form(None),
    status: str = Form(None),
    tipo_numero: list = Form([]),
    numero: list = Form([]),
    data_aquisicao: str = Form(None),
    valor_aquisicao: float = Form(None),
    garantia_ate: str = Form(None),
    observacao: str = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    user_obj = _user_obj(db, user)
    if not user_obj:
        return RedirectResponse("/login")

    if controla_por_serie:
        target_unidade_id = unit_id_serie
    else:
        target_unidade_id = unit_id
    if not target_unidade_id:
        return HTMLResponse(
            content="<script>alert('Unidade é obrigatória.'); history.back();</script>",
            status_code=400,
        )

    unidade = (
        db.query(Unidade)
        .options(joinedload(Unidade.orgao).joinedload(Orgao.municipio).joinedload(Municipio.estado))
        .filter(Unidade.id == int(target_unidade_id))
        .first()
    )
    if not unidade or not unidade.orgao or not unidade.orgao.municipio:
        return HTMLResponse(
            content="<script>alert('Unidade inválida.'); history.back();</script>",
            status_code=400,
        )

    if not _validate_unidade_scope(db, user_obj, unidade):
        return HTMLResponse(
            content="<script>alert('Você não tem permissão para cadastrar produto nesta unidade.'); history.back();</script>",
            status_code=403,
        )

    tipo = db.query(EquipmentType).filter(EquipmentType.id == type_id).first()
    marca = db.query(Brand).filter(Brand.id == brand_id).first()
    nome_partes = [tipo.nome if tipo else "", marca.nome if marca else "", model or ""]
    name = " ".join(filter(None, nome_partes)) or "Produto sem nome"

    # Produto vinculado à unidade selecionada (com escopo validado por perfil)
    product = Product(
        name=name,
        category_id=category_id,
        type_id=type_id,
        brand_id=brand_id,
        model=model,
        description=description,
        controla_por_serie=controla_por_serie,
        municipio_id=unidade.orgao.municipio_id,
        orgao_id=unidade.orgao_id,
        unidade_id=unidade.id,
        created_by=user_obj.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    if controla_por_serie:
        items_criados = 0
        for i, num in enumerate(numero):
            if not num or str(num).strip() == "":
                continue
            is_tombo = (tipo_numero[i] == "tombo" if i < len(tipo_numero) else True)
            item = Item(
                product_id=product.id,
                municipio_id=product.municipio_id,
                orgao_id=product.orgao_id,
                unit_id=unidade.id,
                tombo=is_tombo,
                num_tombo_ou_serie=str(num).strip(),
                estado_id=estado_id,
                status=status or "Disponível",
                data_aquisicao=datetime.strptime(data_aquisicao, "%Y-%m-%d").date() if data_aquisicao else None,
                valor_aquisicao=valor_aquisicao,
                garantia_ate=garantia_ate or None,
                observacao=observacao,
            )
            db.add(item)
            items_criados += 1
        db.commit()
        registrar_log(db, usuario=user, acao=f"Cadastrou produto em lote: {product.name} ({items_criados} itens)", ip=request.client.host)
    else:
        stock = Stock(
            product_id=product.id,
            municipio_id=product.municipio_id,
            orgao_id=product.orgao_id,
            unit_id=unidade.id,
            quantidade=quantidade,
            quantidade_minima=quantidade_minima,
            localizacao=None,
        )
        db.add(stock)
        db.commit()

        item = Item(
            product_id=product.id,
            municipio_id=product.municipio_id,
            orgao_id=product.orgao_id,
            unit_id=unidade.id,
            tombo=False,
            num_tombo_ou_serie=None,
            estado_id=None,
            status="Disponível",
            data_aquisicao=datetime.strptime(data_aquisicao, "%Y-%m-%d").date() if data_aquisicao else None,
            valor_aquisicao=valor_aquisicao,
            garantia_ate=garantia_ate or None,
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
        joinedload(Product.unit),
    ).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse("/products")

    perfil = getattr(user_obj, "perfil", None)
    if perfil == PERFIL_MASTER:
        pass
    elif perfil == PERFIL_GESTOR_MUNICIPAL:
        if product.municipio_id != user_obj.municipio_id:
            return RedirectResponse("/products")
    else:
        # restringe por unidade (fallback para produtos antigos sem unidade_id)
        if product.unidade_id and product.unidade_id != user_obj.unidade_id:
            return RedirectResponse("/products")
        if product.unidade_id is None and product.orgao_id != user_obj.orgao_id:
            return RedirectResponse("/products")
        return RedirectResponse("/products")

    item = db.query(Item).filter(Item.product_id == product_id).first()

    # Lotação do produto (para exibição)
    lotacao = None
    if product.orgao and product.orgao.municipio and product.orgao.municipio.estado:
        lotacao = {
            "estado": product.orgao.municipio.estado.nome,
            "municipio": product.orgao.municipio.nome,
            "orgao": product.orgao.nome,
            "unidade": (product.unit.nome if product.unit else "-"),
        }

    categorias = db.query(Category).order_by(Category.nome).all()
    tipos = db.query(EquipmentType).all()
    marcas = db.query(Brand).all()
    estados = db.query(EquipmentState).all()
    # Para edição: mantemos a mesma unidade (evita inconsistência com itens/estoque já existentes)
    unidades = [product.unit] if product.unit else _scope_unidades_query(db, user_obj).all()

    return templates.TemplateResponse(
        "product_form.html",
        {
            "request": request,
            "action": "edit",
            "categories": categorias,
            "tipos": tipos,
            "marcas": marcas,
            "estados": estados,
            "units": unidades,
            "lotacao": lotacao,
            "default_unidade_id": product.unidade_id or user_obj.unidade_id,
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
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    user_obj = _user_obj(db, user)
    if not user_obj:
        return RedirectResponse("/login")

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse("/products")

    perfil = getattr(user_obj, "perfil", None)
    if perfil == PERFIL_MASTER:
        pass
    elif perfil == PERFIL_GESTOR_MUNICIPAL:
        if product.municipio_id != user_obj.municipio_id:
            return RedirectResponse("/products")
    else:
        if product.unidade_id and product.unidade_id != user_obj.unidade_id:
            return RedirectResponse("/products")
        if product.unidade_id is None and product.orgao_id != user_obj.orgao_id:
            return RedirectResponse("/products")

    tipo = db.query(EquipmentType).filter(EquipmentType.id == type_id).first()
    marca = db.query(Brand).filter(Brand.id == brand_id).first()
    nome_partes = [tipo.nome if tipo else "", marca.nome if marca else "", model or ""]
    product.name = " ".join(filter(None, nome_partes)) or "Produto sem nome"
    product.category_id = int(category_id) if category_id else None
    product.type_id = int(type_id)
    product.brand_id = int(brand_id)
    product.model = model
    product.description = description
    product.controla_por_serie = controla_por_serie
    if not controla_por_serie:
        product.quantidade = int(quantidade or 0)
        product.quantidade_minima = int(quantidade_minima or 0)

    item = db.query(Item).filter(Item.product_id == product.id).first()
    if not item:
        item = Item(
            product_id=product.id,
            municipio_id=product.municipio_id,
            orgao_id=product.orgao_id,
        )
    item.tombo = (tombo == "Sim") if controla_por_serie else False
    item.num_tombo_ou_serie = (num_tombo if (tombo == "Sim") else num_serie) if controla_por_serie else None
    item.estado_id = int(estado_id) if estado_id else None
    item.status = status or "Disponível"
    # Evita alterar a unidade na edição (mantém consistência do vínculo do produto)
    item.unit_id = product.unidade_id or user_obj.unidade_id
    item.data_aquisicao = datetime.strptime(data_aquisicao, "%Y-%m-%d").date() if data_aquisicao else None
    if valor_aquisicao:
        try:
            valor_clean = valor_aquisicao.replace("R$", "").replace(".", "").replace(",", ".").strip()
            item.valor_aquisicao = float(valor_clean)
        except Exception:
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

    user_obj = _user_obj(db, user)
    if not user_obj:
        return JSONResponse({"success": False, "message": "Usuário não encontrado."})

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return JSONResponse({"success": False, "message": "Produto não encontrado."})

    perfil = getattr(user_obj, "perfil", None)
    if perfil == PERFIL_MASTER:
        pass
    elif perfil == PERFIL_GESTOR_MUNICIPAL:
        if product.municipio_id != user_obj.municipio_id:
            return JSONResponse({"success": False, "message": "Você não tem permissão para excluir este produto."})
    else:
        if product.unidade_id and product.unidade_id != user_obj.unidade_id:
            return JSONResponse({"success": False, "message": "Você não tem permissão para excluir este produto."})
        if product.unidade_id is None and product.orgao_id != user_obj.orgao_id:
            return JSONResponse({"success": False, "message": "Você não tem permissão para excluir este produto."})

    movimentacoes = db.query(Movement).filter(Movement.product_id == product.id).first()
    if movimentacoes:
        return JSONResponse({"success": False, "message": "Produto possui movimentações e não pode ser excluído."})

    for s in db.query(Stock).filter(Stock.product_id == product.id).all():
        db.delete(s)
    for it in db.query(Item).filter(Item.product_id == product.id).all():
        db.delete(it)
    db.delete(product)
    db.commit()

    registrar_log(db, usuario=user, acao=f"Excluiu produto: {product.name}", ip=request.client.host)
    return JSONResponse({"success": True})
