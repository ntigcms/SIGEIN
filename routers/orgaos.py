from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session, joinedload

from database import get_db
from dependencies import get_current_user, registrar_log
from fastapi.templating import Jinja2Templates
from models import User, Orgao, Municipio, Estado

router = APIRouter(prefix="/orgaos", tags=["Órgãos"])
templates = Jinja2Templates(directory="templates")


# LISTAR ÓRGÃOS
@router.get("/")
def list_orgaos(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    orgaos = (
        db.query(Orgao)
        .join(Municipio, Orgao.municipio_id == Municipio.id)
        .join(Estado, Municipio.estado_id == Estado.id)
        .options(
            joinedload(Orgao.municipio).joinedload(Municipio.estado)
        )
        .order_by(Estado.nome, Municipio.nome, Orgao.nome)
        .all()
    )

    orgaos_data = []
    for o in orgaos:
        orgaos_data.append({
            "id": o.id,
            "nome": o.nome,
            "sigla": o.sigla or "-",
            "responsavel": o.responsavel or "-",
            "email": o.email or "-",
            "telefone": o.telefone or "-",
            "ativo": "Sim" if o.ativo else "Não",
            "municipio": o.municipio.nome if o.municipio else "-",
            "estado": o.municipio.estado.nome if o.municipio and o.municipio.estado else "-",
        })

    return templates.TemplateResponse(
        "orgaos.html",
        {
            "request": request,
            "orgaos": orgaos_data,
            "user": user,
        },
    )


# FORMULÁRIO DE ADIÇÃO
@router.get("/add")
def add_orgao_form(
    request: Request,
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        "orgao_add.html",
        {"request": request, "user": user, "action": "add"},
    )


# ADICIONAR ÓRGÃO
@router.post("/add")
def add_orgao(
    request: Request,
    nome: str = Form(...),
    sigla: str = Form(""),
    responsavel: str = Form(""),
    email: str = Form(""),
    telefone: str = Form(""),
    municipio_id: int = Form(...),
    ativo: str = Form("false"),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    novo_orgao = Orgao(
        nome=nome,
        sigla=sigla or None,
        responsavel=responsavel or None,
        email=email or None,
        telefone=telefone or None,
        municipio_id=municipio_id,
        ativo=ativo and ativo.lower() in ("true", "1", "on", "sim"),
    )
    db.add(novo_orgao)
    db.commit()
    db.refresh(novo_orgao)

    registrar_log(
        db,
        usuario=user,
        acao=f"Cadastrou órgão: {nome} (município ID {municipio_id})",
        ip=ip,
    )
    return RedirectResponse("/orgaos", status_code=HTTP_302_FOUND)


# FORMULÁRIO DE EDIÇÃO
@router.get("/edit/{orgao_id}")
def edit_orgao_form(
    orgao_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    orgao = (
        db.query(Orgao)
        .options(joinedload(Orgao.municipio).joinedload(Municipio.estado))
        .filter(Orgao.id == orgao_id)
        .first()
    )
    if not orgao:
        return RedirectResponse("/orgaos")

    return templates.TemplateResponse(
        "orgao_add.html",
        {
            "request": request,
            "user": user,
            "orgao": orgao,
            "action": "edit",
        },
    )


# EDITAR ÓRGÃO
@router.post("/edit/{orgao_id}")
def edit_orgao(
    request: Request,
    orgao_id: int,
    nome: str = Form(...),
    sigla: str = Form(""),
    responsavel: str = Form(""),
    email: str = Form(""),
    telefone: str = Form(""),
    municipio_id: int = Form(...),
    ativo: str = Form("false"),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    ip = request.client.host
    orgao = db.query(Orgao).filter(Orgao.id == orgao_id).first()
    if orgao:
        orgao.nome = nome
        orgao.sigla = sigla or None
        orgao.responsavel = responsavel or None
        orgao.email = email or None
        orgao.telefone = telefone or None
        orgao.municipio_id = municipio_id
        orgao.ativo = ativo and ativo.lower() in ("true", "1", "on", "sim")
        db.commit()
        registrar_log(
            db,
            usuario=user,
            acao=f"Editou órgão ID {orgao_id}",
            ip=ip,
        )

    return RedirectResponse("/orgaos", status_code=HTTP_302_FOUND)


# EXCLUIR ÓRGÃO
@router.post("/delete/{orgao_id}")
def delete_orgao(
    request: Request,
    orgao_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse("/login")

    user_obj = db.query(User).filter(User.email == current_user).first()
    if not user_obj:
        return JSONResponse({"success": False, "message": "Não autenticado"})

    if user_obj.perfil not in ["master", "admin_municipal"]:
        return JSONResponse({
            "success": False,
            "message": "Você não tem permissão para excluir órgãos",
        })

    orgao = db.query(Orgao).filter(Orgao.id == orgao_id).first()
    if not orgao:
        return JSONResponse({
            "success": False,
            "message": "Órgão não encontrado",
        })

    if user_obj.perfil == "admin_municipal":
        if orgao.municipio_id != user_obj.municipio_id:
            return JSONResponse({
                "success": False,
                "message": "Você só pode excluir órgãos do seu município",
            })

    from models import Unidade
    unidades_count = db.query(Unidade).filter(Unidade.orgao_id == orgao_id).count()
    if unidades_count > 0:
        return JSONResponse({
            "success": False,
            "message": f"Não é possível excluir. Existem {unidades_count} unidade(s) vinculada(s) a este órgão.",
        })

    nome_orgao = orgao.nome
    db.delete(orgao)
    db.commit()

    registrar_log(
        db,
        usuario=current_user,
        acao=f"Excluiu órgão {nome_orgao} (ID: {orgao_id})",
        ip=request.client.host,
    )

    return JSONResponse({
        "success": True,
        "message": "Órgão excluído com sucesso",
    })
