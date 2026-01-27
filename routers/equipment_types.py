from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, registrar_log
from models import EquipmentType  # Modelo correspondente
from fastapi.templating import Jinja2Templates

# Cria o roteador para Tipos de Equipamentos
router = APIRouter(prefix="/equipment-types", tags=["Equipment Types"])
templates = Jinja2Templates(directory="templates")


# ============================================================
# LISTAR TIPOS DE EQUIPAMENTOS
# ------------------------------------------------------------
# Exibe uma tabela com todos os tipos de equipamentos cadastrados.
# Mostra ID, nome do tipo e ações (Editar / Excluir).
# ============================================================
@router.get("/")
def list_equipment_types(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    tipos = db.query(EquipmentType).all()
    return templates.TemplateResponse(
        "equipment_types.html",
        {"request": request, "equipment_types": tipos, "user": user}
    )


# ============================================================
# FORMULÁRIO PARA CADASTRAR NOVO TIPO
# ------------------------------------------------------------
# Exibe o formulário para criação de um novo tipo de equipamento.
# ============================================================
from models import Category

@router.get("/add")
def add_equipment_type_form(request: Request, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    categories = db.query(Category).order_by(Category.nome).all()

    return templates.TemplateResponse(
        "equipment_type_add.html",
        {
            "request": request,
            "user": user,
            "action": "add",
            "categories": categories,
            "tipo": None
        }
    )



# ============================================================
# CADASTRAR NOVO TIPO DE EQUIPAMENTO
# ------------------------------------------------------------
# Recebe os dados do formulário e insere o novo tipo no banco.
# Após salvar, redireciona para a listagem.
# ============================================================
@router.post("/add")
def add_equipment_type(
    request: Request,
    nome: str = Form(...),
    category_id: int = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    novo_tipo = EquipmentType(nome=nome, category_id=category_id)

    db.add(novo_tipo)
    db.commit()
    db.refresh(novo_tipo)

    registrar_log(db, usuario=user, acao=f"Cadastrou tipo de equipamento: {nome}", ip=ip)
    return RedirectResponse("/equipment-types", status_code=HTTP_302_FOUND)


# ============================================================
# FORMULÁRIO DE EDIÇÃO DE TIPO DE EQUIPAMENTO
# ------------------------------------------------------------
# Exibe o formulário com os dados de um tipo específico,
# permitindo a alteração do nome.
# ============================================================
@router.get("/edit/{type_id}")
def edit_equipment_type_form(
    type_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    tipo = db.query(EquipmentType).filter(EquipmentType.id == type_id).first()
    categories = db.query(Category).order_by(Category.nome).all()

    return templates.TemplateResponse(
        "equipment_type_add.html",
        {"request": request, "user": user, "tipo": tipo, "action": "edit", "categories": categories}
    )



# ============================================================
# EDITAR TIPO DE EQUIPAMENTO
# ------------------------------------------------------------
# Recebe os dados editados e atualiza o registro correspondente.
# ============================================================
@router.post("/edit/{type_id}")
def edit_equipment_type(
    request: Request,
    type_id: int,
    nome: str = Form(...),
    category_id: int = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    tipo = db.query(EquipmentType).filter(EquipmentType.id == type_id).first()
    if tipo:
        tipo.nome = nome
        tipo.category_id = category_id
        db.commit()
        registrar_log(db, usuario=user, acao=f"Editou tipo de equipamento ID {type_id}", ip=ip)

    return RedirectResponse("/equipment-types", status_code=HTTP_302_FOUND)


# ============================================================
# CONFIRMAR EXCLUSÃO DE TIPO
# ------------------------------------------------------------
# Exibe uma tela de confirmação antes de remover o tipo do banco.
# ============================================================
@router.get("/confirm_delete/{type_id}")
def confirm_delete_type(
    request: Request,
    type_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    tipo = db.query(EquipmentType).filter(EquipmentType.id == type_id).first()
    if not tipo:
        return RedirectResponse("/equipment-types")

    return templates.TemplateResponse(
        "equipment_type_confirm_delete.html",
        {"request": request, "user": user, "tipo": tipo}
    )


# ============================================================
# EXCLUIR TIPO DE EQUIPAMENTO
# ------------------------------------------------------------
# Remove o tipo selecionado do banco de dados.
# É recomendado verificar antes se o tipo não está associado
# a nenhum equipamento, para evitar falhas de integridade.
# ============================================================
@router.get("/delete/{type_id}")
def delete_equipment_type(
    request: Request,
    type_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    tipo = db.query(EquipmentType).filter(EquipmentType.id == type_id).first()
    if tipo:
        db.delete(tipo)
        db.commit()
        registrar_log(db, usuario=user, acao=f"Excluiu tipo de equipamento ID {type_id}", ip=ip)

    return RedirectResponse("/equipment-types", status_code=HTTP_302_FOUND)
