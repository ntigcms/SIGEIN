from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, registrar_log
from models import Product, EquipmentType, Brand, Category, EquipmentState, Unit, Item
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/products", tags=["Products"])
templates = Jinja2Templates(directory="templates")


@router.get("/")
def list_products(request: Request, db: Session = Depends(get_db),
                  user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    products = db.query(Product).all()
    return templates.TemplateResponse(
        "products_list.html",
        {"request": request, "products": products, "user": user}
    )


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
            "user": user
        }
    )


@router.post("/add")
def add_product(
    request: Request,
    name: str = Form(...),
    category_id: int = Form(None),
    type_id: int = Form(...),
    brand_id: int = Form(...),
    model: str = Form(...),
    description: str = Form(...),
    controla_por_serie: bool = Form(False),

    tombo: str = Form(None),
    num_tombo: str = Form(None),
    num_serie: str = Form(None),
    state_id: int = Form(None),
    status: str = Form(None),
    unit_id: int = Form(None),
    data_aquisicao: str = Form(None),
    valor_aquisicao: float = Form(None),
    garantia_ate: str = Form(None),
    observacao: str = Form(None),

    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    # ✅ PRODUTO
    product = Product(
        name=name,
        category_id=category_id,
        type_id=type_id,
        brand_id=brand_id,
        model=model,
        description=description,
        controla_por_serie=controla_por_serie
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    # ✅ ITEM FÍSICO
    if controla_por_serie:
        is_tombo = (tombo == "Sim")

        item = Item(
            product_id=product.id,
            tombo=is_tombo,
            num_tombo_ou_serie=num_tombo if is_tombo else num_serie,
            estado_id=state_id,
            status=status,
            unit_id=unit_id,
            data_aquisicao=data_aquisicao,
            valor_aquisicao=valor_aquisicao,
            garantia_ate=garantia_ate,
            observacao=observacao
        )

        db.add(item)
        db.commit()

    registrar_log(db, usuario=user, acao=f"Cadastrou produto: {name}", ip=request.client.host)
    return RedirectResponse("/products", status_code=HTTP_302_FOUND)


@router.get("/edit/{product_id}")
def edit_product_form(product_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse("/products")
    
    # Buscando o Item físico vinculado ao produto
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
            "item": item,  # <-- enviar item físico
            "user": user
        }
    )

@router.post("/edit/{product_id}")
def edit_product(
    product_id: int,
    request: Request,

    name: str = Form(...),
    category_id: int = Form(None),
    type_id: int = Form(...),
    brand_id: int = Form(...),
    model: str = Form(...),
    description: str = Form(...),
    controla_por_serie: bool = Form(False),

    tombo: str = Form(None),
    num_tombo: str = Form(None),
    num_serie: str = Form(None),
    state_id: int = Form(None),
    status: str = Form(None),
    unit_id: int = Form(None),
    data_aquisicao: str = Form(None),
    valor_aquisicao: float = Form(None),
    garantia_ate: str = Form(None),
    observacao: str = Form(None),

    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse("/products")

    # 🔹 PRODUTO
    product.name = name
    product.category_id = category_id
    product.type_id = type_id
    product.brand_id = brand_id
    product.model = model
    product.description = description
    product.controla_por_serie = controla_por_serie

    # 🔹 ITEM
    item = db.query(Item).filter(Item.product_id == product.id).first()

    if controla_por_serie:
        if not item:
            item = Item(product_id=product.id)

        is_tombo = (tombo == "Sim")
        item.tombo = is_tombo
        item.num_tombo_ou_serie = num_tombo if is_tombo else num_serie
        item.estado_id = state_id
        item.status = status
        item.unit_id = unit_id
        item.data_aquisicao = data_aquisicao
        item.valor_aquisicao = valor_aquisicao
        item.garantia_ate = garantia_ate
        item.observacao = observacao

        db.add(item)
    else:
        # se desmarcar "controla por série", remove item físico
        if item:
            db.delete(item)

    db.commit()

    registrar_log(db, usuario=user, acao=f"Editou produto: {name}", ip=request.client.host)
    return RedirectResponse("/products", status_code=HTTP_302_FOUND)

