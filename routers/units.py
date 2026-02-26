from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session, joinedload

from database import get_db
from dependencies import get_current_user, registrar_log
from fastapi.templating import Jinja2Templates
from models import (
    User,           # ✅ Para verificar permissões
    Unit,           # ✅ Modelo legado (se ainda usar)
    Unidade,        # ✅ Modelo novo
    Orgao,          # ✅ Para relacionamentos
    Municipio,      # ✅ Para relacionamentos
    Estado          # ✅ Para relacionamentos
)

router = APIRouter(prefix="/units", tags=["Unidades Administrativas"])
templates = Jinja2Templates(directory="templates")


# LISTAR UNIDADES ADMINISTRATIVAS (tabela 'unidades')
@router.get("/")
def list_units(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    """Lista unidades com eager loading dos relacionamentos"""
    if not user:
        return RedirectResponse("/login")
    
    # ✅ Carrega unidades com todos os relacionamentos de uma vez (evita N+1 queries)
    unidades = (
        db.query(Unidade)
        .join(Orgao, Unidade.orgao_id == Orgao.id)
        .join(Municipio, Orgao.municipio_id == Municipio.id)
        .join(Estado, Municipio.estado_id == Estado.id)
        .options(
            joinedload(Unidade.orgao)
            .joinedload(Orgao.municipio)
            .joinedload(Municipio.estado)
        )
        .all()
    )
    
    # ✅ Prepara dados com campos diretos (evita problemas no template)
    units_data = []
    for u in unidades:
        units_data.append({
            'id': u.id,
            'nome': u.nome,
            'sigla': u.sigla or '-',
            'ramal': u.ramal or '-',
            'responsavel': u.responsavel or '-',
            'orgao': u.orgao.nome if u.orgao else '-',
            'municipio': u.orgao.municipio.nome if u.orgao and u.orgao.municipio else '-',
            'estado': u.orgao.municipio.estado.nome if u.orgao and u.orgao.municipio and u.orgao.municipio.estado else '-',
        })
    
    return templates.TemplateResponse(
        "units.html",
        {
            "request": request,
            "units": units_data,
            "user": user
        }
    )


# FORMULÁRIO DE ADIÇÃO DE UNIDADE
@router.get("/add")
def add_unit_form(
    request: Request,
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        "unit_add.html",
        {"request": request, "user": user, "action": "add"},
    )


# ADICIONAR UNIDADE (usa modelo Unidade)
@router.post("/add")
def add_unit(
    request: Request,
    nome: str = Form(...),
    sigla: str = Form(""),
    responsavel: str = Form(""),
    ramal: str = Form(""),
    orgao_id: int = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host

    nova_unidade = Unidade(
        nome=nome,
        sigla=sigla or None,
        responsavel=responsavel or None,
        ramal=ramal or None,
        orgao_id=orgao_id,
        ativo=True,
    )

    db.add(nova_unidade)
    db.commit()
    db.refresh(nova_unidade)

    registrar_log(
        db,
        usuario=user,
        acao=f"Cadastrou unidade administrativa: {nome} (órgão ID {orgao_id})",
        ip=ip,
    )
    return RedirectResponse("/units", status_code=HTTP_302_FOUND)


# FORMULÁRIO DE EDIÇÃO DE UNIDADE
@router.get("/edit/{unit_id}")
def edit_unit_form(
    unit_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    unidade = db.query(Unidade).filter(Unidade.id == unit_id).first()
    if not unidade:
        return RedirectResponse("/units")

    return templates.TemplateResponse(
        "unit_add.html",
        {
            "request": request,
            "user": user,
            "unidade": unidade,
            "action": "edit",
        },
    )


# EDITAR UNIDADE
@router.post("/edit/{unit_id}")
def edit_unit(
    request: Request,
    unit_id: int,
    nome: str = Form(...),
    sigla: str = Form(""),
    responsavel: str = Form(""),
    ramal: str = Form(""),
    orgao_id: int = Form(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    unidade = db.query(Unidade).filter(Unidade.id == unit_id).first()
    if unidade:
        unidade.nome = nome
        unidade.sigla = sigla or None
        unidade.responsavel = responsavel or None
        unidade.ramal = ramal or None
        unidade.orgao_id = orgao_id

        db.commit()

        registrar_log(
            db,
            usuario=user,
            acao=f"Editou unidade administrativa ID {unit_id}",
            ip=ip,
        )

    return RedirectResponse("/units", status_code=HTTP_302_FOUND)


# EXCLUIR UNIDADE
@router.post("/delete/{unit_id}")  # ✅ POST em vez de GET
def delete_unit(
    request: Request,
    unit_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Exclui uma unidade"""
    if not current_user:
        return RedirectResponse("/login")
    
    # Busca usuário para verificar permissão
    user_obj = db.query(User).filter(User.email == current_user).first()
    
    # ✅ Verifica permissão (apenas MASTER e ADMIN_MUNICIPAL)
    if user_obj.perfil not in ["master", "admin_municipal"]:
        return JSONResponse({
            "success": False,
            "message": "Você não tem permissão para excluir unidades"
        })
    
    # Busca unidade
    unidade = db.query(Unidade).filter(Unidade.id == unit_id).first()
    
    if not unidade:
        return JSONResponse({
            "success": False,
            "message": "Unidade não encontrada"
        })
    
    # ✅ ADMIN_MUNICIPAL só pode excluir do seu município
    if user_obj.perfil == "admin_municipal":
        if unidade.orgao.municipio_id != user_obj.municipio_id:
            return JSONResponse({
                "success": False,
                "message": "Você só pode excluir unidades do seu município"
            })
    
    # ✅ Verifica se há usuários vinculados
    usuarios_vinculados = db.query(User).filter(User.unidade_id == unit_id).count()
    if usuarios_vinculados > 0:
        return JSONResponse({
            "success": False,
            "message": f"Não é possível excluir. Existem {usuarios_vinculados} usuário(s) vinculado(s) a esta unidade."
        })
    
    # Exclui
    nome_unidade = unidade.nome
    db.delete(unidade)
    db.commit()
    
    # Log
    registrar_log(
        db,
        usuario=current_user,
        acao=f"Excluiu unidade {nome_unidade} (ID: {unit_id})",
        ip=request.client.host
    )
    
    return JSONResponse({
        "success": True,
        "message": "Unidade excluída com sucesso"
    })
