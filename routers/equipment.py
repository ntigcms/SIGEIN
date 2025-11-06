from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, registrar_log
from models import Equipment
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
def add_equipment_form(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("equipment_form.html",
                                      {"request": request, "user": user, "action": "add"})

# ============================
# Adicionar equipamento
# ============================
@router.post("/add")
def add_equipment(
    request: Request,
    nome: str = Form(...),
    tipo: str = Form(...),
    marca: str = Form(...),
    status: str = Form(...),
    estado: str = Form(...),
    localizacao: str = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host

    # Criando o equipamento com mapeamento correto dos nomes
    equipment = Equipment(
        nome=nome,
        tipo=tipo,
        brand=marca,        # 'marca' do form → 'brand' do modelo
        status=status,
        state=estado,       # 'estado' do form → 'state' do modelo
        location=localizacao # 'localizacao' do form → 'location' do modelo
    )

    db.add(equipment)
    db.commit()
    db.refresh(equipment)  # Atualiza o objeto com o ID gerado
    registrar_log(db, usuario=user, acao=f"Adicionou equipamento: {marca} - {tipo}", ip=ip)

    return RedirectResponse("/equipment", status_code=HTTP_302_FOUND)


# ============================
# Editar equipamento
# ============================
@router.post("/edit/{equipment_id}")
def edit_equipment(
    request: Request,
    equipment_id: int,
    nome: str = Form(...),
    tipo: str = Form(...),
    marca: str = Form(...),
    status: str = Form(...),
    estado: str = Form(...),
    localizacao: str = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()

    if equipment:
        # Atualizando os campos
        equipment.nome = nome
        equipment.tipo = tipo
        equipment.brand = marca
        equipment.status = status
        equipment.state = estado
        equipment.location = localizacao
        db.commit()
        registrar_log(db, usuario=user, acao=f"Editou equipamento ID {equipment_id}", ip=ip)

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
def edit_equipment_form(equipment_id: int, request: Request, db: Session = Depends(get_db),
                        user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    return templates.TemplateResponse("equipment_form.html",
                                      {"request": request, "equipment": equipment, "user": user, "action": "edit"})

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