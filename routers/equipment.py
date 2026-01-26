from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, registrar_log
from models import Equipment, EquipmentType, Brand, EquipmentState, Unit, Product
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/equipment", tags=["Equipment"])
templates = Jinja2Templates(directory="templates")

# ============================
# Listar equipamentos
# ============================
@router.get("/")
def list_equipment(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    
    equipments = db.query(Equipment).all()
    return templates.TemplateResponse("equipment_list.html",
                                      {"request": request, "equipments": equipments, "user": user})

# ============================
# Formulário para adicionar
# ============================
@router.get("/add")
def add_equipment_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    
    tipos = db.query(EquipmentType).all()
    marcas = db.query(Brand).all()
    estados = db.query(EquipmentState).all()
    units = db.query(Unit).all()  # <-- listar unidades
    products = db.query(Product).filter(Product.ativo == True).all()

    return templates.TemplateResponse(
        "equipment_form.html",
        {
            "request": request,
            "action": "add",
            "tipos": tipos,
            "marcas": marcas,
            "estados": estados,
            "units": units,  # <-- passar para o template
            "equipment": None,
            "products": products,
            "user": user
        }
    )

# ============================
# Adicionar equipamento
# ============================
@router.post("/add")
def add_equipment(
    request: Request,
    tipo_id: int = Form(...),
    brand_id: int = Form(...),
    status: str = Form(...),
    state_id: int = Form(...),
    unit_id: int = Form(...),
    product_id: int = Form(...),
    tombo: str = Form(...),
    num_tombo: str = Form(None),
    num_serie: str = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    tombo_valor = 0 if tombo == "Sim" else 1
    numero = num_tombo if tombo == "Sim" else num_serie

    equipment = Equipment(
        tipo_id=tipo_id,
        brand_id=brand_id,
        status=status,
        state_id=state_id,
        unit_id=unit_id,
        product_id=product_id,
        tombo=tombo_valor,
        num_tombo_ou_serie=numero
    )

    db.add(equipment)
    db.commit()
    db.refresh(equipment)

    registrar_log(db, usuario=user, acao=f"Adicionou equipamento ID {equipment.id}", ip=ip)
    return RedirectResponse("/equipment", status_code=HTTP_302_FOUND)

# ============================
# Editar equipamento
# ============================
@router.post("/edit/{equipment_id}")
def edit_equipment(
    request: Request,
    equipment_id: int,
    tipo_id: int = Form(...),
    brand_id: int = Form(...),
    status: str = Form(...),
    state_id: int = Form(...),
    unit_id: int = Form(...),
    product_id: int = Form(...),
    tombo: str = Form(...),
    num_tombo: str = Form(None),
    num_serie: str = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if equipment:
        equipment.tipo_id = tipo_id
        equipment.brand_id = brand_id
        equipment.status = status
        equipment.state_id = state_id
        equipment.unit_id = unit_id
        equipment.product_id = product_id
        equipment.tombo = 0 if tombo == "Sim" else 1
        equipment.num_tombo_ou_serie = num_tombo if tombo == "Sim" else num_serie

        db.commit()
        registrar_log(db, usuario=user, acao=f"Editou equipamento ID {equipment.id}", ip=request.client.host)

    return RedirectResponse("/equipment", status_code=HTTP_302_FOUND)


# ============================
# Deletar equipamento
# ============================
@router.get("/delete/{equipment_id}")
def delete_equipment(request: Request, equipment_id: int, db: Session = Depends(get_db),
                     user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if equipment:
        db.delete(equipment)
        db.commit()
        registrar_log(db, usuario=user, acao=f"Excluiu equipamento ID {equipment_id}", ip=ip)

    return RedirectResponse("/equipment", status_code=HTTP_302_FOUND)

# ============================
# Formulário para editar
# ============================
@router.get("/edit/{equipment_id}")
def edit_equipment_form(equipment_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        return RedirectResponse("/equipment")
    
    tipos = db.query(EquipmentType).all()
    marcas = db.query(Brand).all()
    estados = db.query(EquipmentState).all()
    units = db.query(Unit).all()  # <-- listar unidades
    products = db.query(Product).filter(Product.ativo == True).all()

    return templates.TemplateResponse(
        "equipment_form.html",
        {
            "request": request,
            "action": "edit",
            "tipos": tipos,
            "marcas": marcas,
            "estados": estados,
            "units": units,  # <-- passar para o template
            "equipment": equipment,
            "products": products,
            "user": user
        }
    )


# ============================
# Confirmar exclusão de equipamento
# ============================
@router.get("/confirm_delete/{equipment_id}")
def confirm_delete_equipment(request: Request, equipment_id: int, db: Session = Depends(get_db),
                             user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        return RedirectResponse("/equipment")
    
    return templates.TemplateResponse(
        "equipment_confirm_delete.html",
        {"request": request, "equipment": equipment, "user": user}
    )