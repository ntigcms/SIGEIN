from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, registrar_log
from models import User, SegemItem, Unidade, ProdutoSegem
from shared_templates import templates

router = APIRouter(prefix="/segem", tags=["SEGEM"])


def _user_obj(db: Session, user: str):
    if not user:
        return None
    return db.query(User).filter(User.email == user).first()


def _query_segem(db: Session, user_obj: User):
    q = db.query(SegemItem)
    if user_obj.perfil != "master":
        q = q.filter(SegemItem.municipio_id == user_obj.municipio_id)
    return q.order_by(SegemItem.id.desc())


@router.get("/produtos")
def segem_produtos_list(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Lista todos os produtos SEGEM (código + descrição) para datalist/autocomplete."""
    if not user:
        return JSONResponse({"error": "Não autenticado"}, status_code=401)
    user_obj = _user_obj(db, user)
    if not user_obj or user_obj.perfil not in ["master", "gestor_segem"]:
        return JSONResponse({"error": "Sem permissão"}, status_code=403)
    produtos = db.query(ProdutoSegem).order_by(ProdutoSegem.codigo).all()
    return JSONResponse([{"codigo": p.codigo or "", "descricao": p.descricao or ""} for p in produtos])


@router.get("/produtos/busca")
def segem_produtos_busca(
    codigo: str = "",
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Retorna a descrição do produto SEGEM pelo código (para preenchimento automático)."""
    if not user:
        return JSONResponse({"error": "Não autenticado"}, status_code=401)
    user_obj = _user_obj(db, user)
    if not user_obj or user_obj.perfil not in ["master", "gestor_segem"]:
        return JSONResponse({"error": "Sem permissão"}, status_code=403)
    codigo = (codigo or "").strip()
    if not codigo:
        return JSONResponse({"codigo": "", "descricao": ""})
    p = db.query(ProdutoSegem).filter(ProdutoSegem.codigo == codigo).first()
    if not p:
        return JSONResponse({"codigo": codigo, "descricao": ""})
    return JSONResponse({"codigo": p.codigo, "descricao": p.descricao or ""})


@router.get("/")
def segem_home(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    user_obj = _user_obj(db, user)
    if not user_obj:
        return RedirectResponse("/login")

    if user_obj.perfil not in ["master", "gestor_segem"]:
        return RedirectResponse("/dashboard")

    itens = _query_segem(db, user_obj).all()
    unidades = db.query(Unidade).filter(Unidade.ativo == True).order_by(Unidade.nome).all()

    # Valores únicos para filtros
    anos = sorted({i.ano for i in itens if i.ano is not None})
    locais = sorted({i.local for i in itens if i.local})
    situacoes = sorted({i.situacao for i in itens if i.situacao})

    return templates.TemplateResponse(
        "segem_list.html",
        {
            "request": request,
            "user": user,
            "itens": itens,
            "unidades": unidades,
            "anos": anos,
            "locais": locais,
            "situacoes": situacoes,
        },
    )


@router.get("/add")
def segem_add_form(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")
    user_obj = _user_obj(db, user)
    if not user_obj or user_obj.perfil not in ["master", "gestor_segem"]:
        return RedirectResponse("/dashboard")
    unidades = db.query(Unidade).filter(Unidade.ativo == True).order_by(Unidade.nome).all()
    produtos_segem = db.query(ProdutoSegem).order_by(ProdutoSegem.codigo).all()
    return templates.TemplateResponse(
        "segem_form.html",
        {
            "request": request,
            "user": user,
            "action": "add",
            "item": None,
            "unidades": unidades,
            "produtos_segem": produtos_segem,
        },
    )


@router.post("/add")
def segem_add_submit(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    ano: int = Form(None),
    num_tombo_gcm: str = Form(""),
    local: str = Form(""),
    codigo: str = Form(""),
    descricao: str = Form(""),
    situacao: str = Form(""),
    valor_rs: float = Form(None),
    entrada_no_siga: str = Form(""),
    nota_de_empenho: str = Form(""),
    valor_nota_empenho: float = Form(None),
    num_nota_fiscal: str = Form(""),
    nome_empresa: str = Form(""),
    classificacao_asi: str = Form(""),
):
    if not user:
        return RedirectResponse("/login")
    user_obj = _user_obj(db, user)
    if not user_obj or user_obj.perfil not in ["master", "gestor_segem"]:
        return RedirectResponse("/dashboard")
    item = SegemItem(
        municipio_id=user_obj.municipio_id,
        orgao_id=user_obj.orgao_id,
        created_by=user_obj.id,
        ano=ano,
        num_tombo_gcm=num_tombo_gcm.strip() or None,
        local=local.strip() or None,
        codigo=codigo.strip() or None,
        descricao=descricao.strip() or None,
        situacao=situacao.strip() or None,
        valor_rs=valor_rs,
        entrada_no_siga=entrada_no_siga.strip() or None,
        nota_de_empenho=nota_de_empenho.strip() or None,
        valor_nota_empenho=valor_nota_empenho,
        num_nota_fiscal=num_nota_fiscal.strip() or None,
        nome_empresa=nome_empresa.strip() or None,
        classificacao_asi=classificacao_asi.strip() or None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    registrar_log(db, usuario=user, acao=f"SEGEM: Cadastrou registro {item.id}", ip=request.client.host)
    return RedirectResponse("/segem", status_code=302)


@router.get("/edit/{item_id}")
def segem_edit_form(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")
    user_obj = _user_obj(db, user)
    if not user_obj or user_obj.perfil not in ["master", "gestor_segem"]:
        return RedirectResponse("/dashboard")
    item = db.query(SegemItem).filter(SegemItem.id == item_id).first()
    if not item:
        return RedirectResponse("/segem")
    if user_obj.perfil != "master" and item.municipio_id != user_obj.municipio_id:
        return RedirectResponse("/segem")
    unidades = db.query(Unidade).filter(Unidade.ativo == True).order_by(Unidade.nome).all()
    produtos_segem = db.query(ProdutoSegem).order_by(ProdutoSegem.codigo).all()
    return templates.TemplateResponse(
        "segem_form.html",
        {
            "request": request,
            "user": user,
            "action": "edit",
            "item": item,
            "unidades": unidades,
            "produtos_segem": produtos_segem,
        },
    )


@router.post("/edit/{item_id}")
def segem_edit_submit(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    ano: int = Form(None),
    num_tombo_gcm: str = Form(""),
    local: str = Form(""),
    codigo: str = Form(""),
    descricao: str = Form(""),
    situacao: str = Form(""),
    valor_rs: float = Form(None),
    entrada_no_siga: str = Form(""),
    nota_de_empenho: str = Form(""),
    valor_nota_empenho: float = Form(None),
    num_nota_fiscal: str = Form(""),
    nome_empresa: str = Form(""),
    classificacao_asi: str = Form(""),
):
    if not user:
        return RedirectResponse("/login")
    user_obj = _user_obj(db, user)
    if not user_obj or user_obj.perfil not in ["master", "gestor_segem"]:
        return RedirectResponse("/dashboard")
    item = db.query(SegemItem).filter(SegemItem.id == item_id).first()
    if not item:
        return RedirectResponse("/segem")
    if user_obj.perfil != "master" and item.municipio_id != user_obj.municipio_id:
        return RedirectResponse("/segem")
    item.ano = ano
    item.num_tombo_gcm = num_tombo_gcm.strip() or None
    item.local = local.strip() or None
    item.codigo = codigo.strip() or None
    item.descricao = descricao.strip() or None
    item.situacao = situacao.strip() or None
    item.valor_rs = valor_rs
    item.entrada_no_siga = entrada_no_siga.strip() or None
    item.nota_de_empenho = nota_de_empenho.strip() or None
    item.valor_nota_empenho = valor_nota_empenho
    item.num_nota_fiscal = num_nota_fiscal.strip() or None
    item.nome_empresa = nome_empresa.strip() or None
    item.classificacao_asi = classificacao_asi.strip() or None
    db.commit()
    db.refresh(item)
    registrar_log(db, usuario=user, acao=f"SEGEM: Atualizou registro {item.id}", ip=request.client.host)
    return RedirectResponse("/segem", status_code=302)


@router.get("/item/{item_id}")
def segem_get_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return JSONResponse({"error": "Não autenticado"}, status_code=401)
    user_obj = _user_obj(db, user)
    if not user_obj or user_obj.perfil not in ["master", "gestor_segem"]:
        return JSONResponse({"error": "Sem permissão"}, status_code=403)

    item = db.query(SegemItem).filter(SegemItem.id == item_id).first()
    if not item:
        return JSONResponse({"error": "Registro não encontrado"}, status_code=404)
    if user_obj.perfil != "master" and item.municipio_id != user_obj.municipio_id:
        return JSONResponse({"error": "Sem permissão"}, status_code=403)

    return JSONResponse({
        "id": item.id,
        "ano": item.ano,
        "num_tombo_gcm": item.num_tombo_gcm or "",
        "local": item.local or "",
        "codigo": item.codigo or "",
        "descricao": item.descricao or "",
        "situacao": item.situacao or "",
        "valor_rs": item.valor_rs,
        "entrada_no_siga": item.entrada_no_siga or "",
        "nota_de_empenho": item.nota_de_empenho or "",
        "valor_nota_empenho": item.valor_nota_empenho,
        "num_nota_fiscal": item.num_nota_fiscal or "",
        "nome_empresa": item.nome_empresa or "",
        "classificacao_asi": item.classificacao_asi or "",
    })


@router.post("/save")
def segem_save(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    id: int = Form(None),
    ano: int = Form(None),
    num_tombo_gcm: str = Form(""),
    local: str = Form(""),
    codigo: str = Form(""),
    descricao: str = Form(""),
    situacao: str = Form(""),
    valor_rs: float = Form(None),
    entrada_no_siga: str = Form(""),
    nota_de_empenho: str = Form(""),
    valor_nota_empenho: float = Form(None),
    num_nota_fiscal: str = Form(""),
    nome_empresa: str = Form(""),
    classificacao_asi: str = Form(""),
):
    if not user:
        return JSONResponse({"error": "Não autenticado"}, status_code=401)
    user_obj = _user_obj(db, user)
    if not user_obj or user_obj.perfil not in ["master", "gestor_segem"]:
        return JSONResponse({"error": "Sem permissão"}, status_code=403)

    if id:
        item = db.query(SegemItem).filter(SegemItem.id == id).first()
        if not item:
            return JSONResponse({"error": "Registro não encontrado"}, status_code=404)
        if user_obj.perfil != "master" and item.municipio_id != user_obj.municipio_id:
            return JSONResponse({"error": "Sem permissão"}, status_code=403)
    else:
        item = SegemItem(
            municipio_id=user_obj.municipio_id,
            orgao_id=user_obj.orgao_id,
            created_by=user_obj.id,
        )
        db.add(item)

    item.ano = ano
    item.num_tombo_gcm = num_tombo_gcm.strip() or None
    item.local = local.strip() or None
    item.codigo = codigo.strip() or None
    item.descricao = descricao.strip() or None
    item.situacao = situacao.strip() or None
    item.valor_rs = valor_rs
    item.entrada_no_siga = entrada_no_siga.strip() or None
    item.nota_de_empenho = nota_de_empenho.strip() or None
    item.valor_nota_empenho = valor_nota_empenho
    item.num_nota_fiscal = num_nota_fiscal.strip() or None
    item.nome_empresa = nome_empresa.strip() or None
    item.classificacao_asi = classificacao_asi.strip() or None

    db.commit()
    db.refresh(item)
    registrar_log(db, usuario=user, acao=f"SEGEM: {'Atualizou' if id else 'Cadastrou'} registro {item.id}", ip=request.client.host)
    return JSONResponse({"success": True, "id": item.id})


@router.post("/delete/{item_id}")
def segem_delete(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return JSONResponse({"success": False, "message": "Não autenticado"}, status_code=401)
    user_obj = _user_obj(db, user)
    if not user_obj or user_obj.perfil not in ["master", "gestor_segem"]:
        return JSONResponse({"success": False, "message": "Sem permissão"}, status_code=403)

    item = db.query(SegemItem).filter(SegemItem.id == item_id).first()
    if not item:
        return JSONResponse({"success": False, "message": "Registro não encontrado"})
    if user_obj.perfil != "master" and item.municipio_id != user_obj.municipio_id:
        return JSONResponse({"success": False, "message": "Sem permissão"})

    db.delete(item)
    db.commit()
    registrar_log(db, usuario=user, acao=f"SEGEM: Excluiu registro {item_id}", ip=request.client.host)
    return JSONResponse({"success": True})
