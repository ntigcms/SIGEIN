from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, registrar_log
from models import Product, EquipmentType, Brand, Category, EquipmentState, Unit, Item, Movement, Stock
from fastapi.templating import Jinja2Templates
from datetime import datetime

router = APIRouter(prefix="/products", tags=["Products"])
templates = Jinja2Templates(directory="templates")


# ----------------- LIST -----------------
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
    categorias = db.query(Category).order_by(Category.nome).all()
    tipos = db.query(EquipmentType).all()
    marcas = db.query(Brand).all()
    estados = db.query(EquipmentState).all()
    units = db.query(Unit).all()
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
            "product": None,
            "item": None,
            "user": user
        }
    )


# ----------------- ADD PRODUCT -----------------
@router.post("/add")
async def add_product(
    request: Request,
    name: str = Form(...),
    category_id: int = Form(None),
    type_id: int = Form(...),
    brand_id: int = Form(...),
    model: str = Form(...),
    description: str = Form(...),
    controla_por_serie: bool = Form(False),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    form = await request.form()

    # Campos do item físico
    tombo = form.get("tombo")
    num_tombo = form.get("num_tombo")
    num_serie = form.get("num_serie")
    estado_id = form.get("estado_id")
    status = form.get("status")
    unit_id = form.get("unit_id")
    data_aquisicao = form.get("data_aquisicao")
    valor_aquisicao = form.get("valor_aquisicao")
    garantia_ate = form.get("garantia_ate")
    observacao = form.get("observacao")

    # Campos para produtos sem série
    quantidade = int(form.get("quantidade", 0))
    quantidade_minima = int(form.get("quantidade_minima", 0))

    # --- PRODUTO ---
    product = Product(
        name=name,
        category_id=category_id,
        type_id=type_id,
        brand_id=brand_id,
        model=model,
        description=description,
        controla_por_serie=controla_por_serie,
        quantidade=quantidade if not controla_por_serie else 0,
        quantidade_minima=quantidade_minima if not controla_por_serie else 0
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    # --- ITEM FÍSICO ---
    is_tombo = (tombo == "Sim")
    item = Item(
        product_id=product.id,
        tombo=is_tombo if controla_por_serie else False,
        num_tombo_ou_serie=(num_tombo if is_tombo else num_serie) if controla_por_serie else None,
        estado_id=int(estado_id) if estado_id else None,
        status=status or "Disponível",
        unit_id=int(unit_id) if unit_id else None,
        data_aquisicao=datetime.strptime(data_aquisicao, "%Y-%m-%d").date() if data_aquisicao else None,
        valor_aquisicao=float(valor_aquisicao) if valor_aquisicao else None,
        garantia_ate=garantia_ate or None,
        observacao=observacao
    )
    db.add(item)
    db.commit()

    registrar_log(db, usuario=user, acao=f"Cadastrou produto: {name}", ip=request.client.host)
    return RedirectResponse("/products", status_code=HTTP_302_FOUND)


# ----------------- EDIT FORM -----------------
@router.get("/edit/{product_id}")
def edit_product_form(product_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse("/products")
    item = db.query(Item).filter(Item.product_id == product_id).first()

    categorias = db.query(Category).order_by(Category.nome).all()
    tipos = db.query(EquipmentType).all()
    marcas = db.query(Brand).all()
    estados = db.query(EquipmentState).all()
    units = db.query(Unit).all()

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
            "product": product,
            "item": item,
            "user": user
        }
    )


# ----------------- EDIT PRODUCT -----------------
@router.post("/edit/{product_id}")
def edit_product(
    product_id: int,
    request: Request,
    name: str = Form(...),
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

    # --- Produto ---
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse("/products")

    product.name = name
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
    if not item:
        item = Item(product_id=product.id)

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

    registrar_log(db, usuario=user, acao=f"Editou produto: {name}", ip=request.client.host)
    return RedirectResponse("/products", status_code=HTTP_302_FOUND)


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
