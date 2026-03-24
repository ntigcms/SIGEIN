import re
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload

from database import get_db
from dependencies import get_current_user, registrar_log
from models import User, SegemItem, SegemItemProduto, Unidade, ProdutoSegem
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


def _valor_fmt(val):
    """Formata valor para exibição no campo R$ (pt-BR)."""
    if val is None:
        return ""
    try:
        return "R$ {:,.2f}".format(float(val)).replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def _parse_valor(v):
    """Converte valor para float. Aceita: pt-BR (1.830,00) ou numérico (1830.00) enviado pelo form."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        s = str(v).replace("R$", "").replace(" ", "").strip()
        if not s:
            return None
        if "," in s:
            # Formato pt-BR: ponto = milhares, vírgula = decimal
            s = s.replace(".", "").replace(",", ".")
        return float(s) if s else None
    except (TypeError, ValueError):
        return None


def _build_produtos_list(item):
    """Monta lista de dicts {tombo, valor_formatado} para o bloco Produto (primeiro = item, demais = item.produtos)."""
    if not item:
        return [{"tombo": "", "valor_formatado": ""}]
    rows = [{"tombo": item.num_tombo_gcm or "", "valor_formatado": _valor_fmt(item.valor_rs)}]
    for p in getattr(item, "produtos", []) or []:
        rows.append({"tombo": p.num_tombo_gcm or "", "valor_formatado": _valor_fmt(p.valor_rs)})
    return rows if rows else [{"tombo": "", "valor_formatado": ""}]


def _all_tombos(item):
    """Concatena todos os Nº TOMBO (item principal + produtos relacionados)."""
    tombos = []
    if getattr(item, "num_tombo_gcm", None):
        tombos.append(item.num_tombo_gcm)
    for p in getattr(item, "produtos", []) or []:
        if getattr(p, "num_tombo_gcm", None):
            tombos.append(p.num_tombo_gcm)
    return ", ".join(tombos)


# Nº TOMBO: intervalo 000.001 a 999.999 (ex.: 003.502). Próximo = max(DB + atuais) + 1.
_TOMBO_PATTERN = re.compile(r"^\s*(\d{1,3})\.(\d{1,3})\s*$")


def _parse_tombo_to_int(s):
    """Converte '003.502' -> 3502 ou None se inválido."""
    if not s or not isinstance(s, str):
        return None
    m = _TOMBO_PATTERN.match(s.strip())
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if a > 999 or b > 999:
        return None
    return a * 1000 + b


def _format_tombo(n):
    """Converte 3502 -> '003.502'."""
    if n is None or n < 0:
        return None
    n = min(int(n), 999999)
    return "{:03d}.{:03d}".format(n // 1000, n % 1000)


def _proximo_tombo(db: Session, atuais=None):
    """Retorna o próximo Nº TOMBO (000.001–999.999). Considera SegemItem + SegemItemProduto e opcionalmente lista atuais."""
    valores = []
    for row in db.query(SegemItem.num_tombo_gcm).filter(SegemItem.num_tombo_gcm.isnot(None)):
        v = _parse_tombo_to_int(row[0])
        if v is not None:
            valores.append(v)
    for row in db.query(SegemItemProduto.num_tombo_gcm).filter(SegemItemProduto.num_tombo_gcm.isnot(None)):
        v = _parse_tombo_to_int(row[0])
        if v is not None:
            valores.append(v)
    if atuais:
        for s in atuais:
            v = _parse_tombo_to_int(s)
            if v is not None:
                valores.append(v)
    proximo_int = (max(valores) + 1) if valores else 3503  # 003.502 + 1 = 003.503
    return _format_tombo(min(proximo_int, 999999))


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


@router.get("/proximo-tombo")
def segem_proximo_tombo(
    atuais: str = "",
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Retorna o próximo Nº TOMBO (000.001–999.999). Opcional: atuais=003.503,003.504 para considerar tombos já no formulário."""
    if not user:
        return JSONResponse({"error": "Não autenticado"}, status_code=401)
    user_obj = _user_obj(db, user)
    if not user_obj or user_obj.perfil not in ["master", "gestor_segem"]:
        return JSONResponse({"error": "Sem permissão"}, status_code=403)
    lista_atuais = [x.strip() for x in (atuais or "").split(",") if x.strip()]
    proximo = _proximo_tombo(db, atuais=lista_atuais)
    return JSONResponse({"proximo_tombo": proximo or "003.503"})


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

    itens = (
        _query_segem(db, user_obj)
        .options(joinedload(SegemItem.produtos))
        .all()
    )
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
            "valor_fmt": _valor_fmt,
            "all_tombos": _all_tombos,
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
    primeiro_tombo = _proximo_tombo(db)
    produtos_list = [{"tombo": primeiro_tombo, "valor_formatado": ""}]
    return templates.TemplateResponse(
        "segem_form.html",
        {
            "request": request,
            "user": user,
            "action": "add",
            "item": None,
            "unidades": unidades,
            "produtos_segem": produtos_segem,
            "produtos_list": produtos_list,
        },
    )


@router.post("/add")
async def segem_add_submit(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")
    user_obj = _user_obj(db, user)
    if not user_obj or user_obj.perfil not in ["master", "gestor_segem"]:
        return RedirectResponse("/dashboard")
    form = await request.form()
    tombos = form.getlist("num_tombo_gcm")
    valores = form.getlist("valor_rs")

    primeiro_tombo = tombos[0].strip() or None if tombos else None
    primeiro_valor = _parse_valor(valores[0]) if valores else None

    # Valor da nota de empenho = soma dos valores de todos os produtos (não editável)
    soma_valores = sum(v for v in (_parse_valor(valores[i]) for i in range(len(valores))) if v is not None)
    item = SegemItem(
        municipio_id=user_obj.municipio_id,
        orgao_id=user_obj.orgao_id,
        created_by=user_obj.id,
        ano=int(form.get("ano")) if form.get("ano") else None,
        num_tombo_gcm=primeiro_tombo,
        local=(form.get("local") or "").strip() or None,
        codigo=(form.get("codigo") or "").strip() or None,
        descricao=(form.get("descricao") or "").strip() or None,
        situacao=(form.get("situacao") or "").strip() or None,
        valor_rs=primeiro_valor,
        entrada_no_siga=(form.get("entrada_no_siga") or "").strip() or None,
        nota_de_empenho=(form.get("nota_de_empenho") or "").strip() or None,
        valor_nota_empenho=soma_valores if soma_valores else None,
        num_nota_fiscal=(form.get("num_nota_fiscal") or "").strip() or None,
        nome_empresa=(form.get("nome_empresa") or "").strip() or None,
        classificacao_asi=(form.get("classificacao_asi") or "").strip() or None,
    )
    db.add(item)
    db.flush()
    for i in range(1, max(len(tombos), len(valores))):
        t = (tombos[i].strip() or None) if i < len(tombos) else None
        v = _parse_valor(valores[i]) if i < len(valores) else None
        if t is not None or v is not None:
            db.add(SegemItemProduto(segem_item_id=item.id, num_tombo_gcm=t, valor_rs=v))
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
    item = db.query(SegemItem).options(
        joinedload(SegemItem.produtos)
    ).filter(SegemItem.id == item_id).first()
    if not item:
        return RedirectResponse("/segem")
    if user_obj.perfil != "master" and item.municipio_id != user_obj.municipio_id:
        return RedirectResponse("/segem")
    unidades = db.query(Unidade).filter(Unidade.ativo == True).order_by(Unidade.nome).all()
    produtos_segem = db.query(ProdutoSegem).order_by(ProdutoSegem.codigo).all()
    produtos_list = _build_produtos_list(item)
    return templates.TemplateResponse(
        "segem_form.html",
        {
            "request": request,
            "user": user,
            "action": "edit",
            "item": item,
            "unidades": unidades,
            "produtos_segem": produtos_segem,
            "produtos_list": produtos_list,
        },
    )


@router.get("/view/{item_id}")
def segem_view_form(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Tela de visualização somente leitura de um registro SEGEM."""
    if not user:
        return RedirectResponse("/login")
    user_obj = _user_obj(db, user)
    if not user_obj or user_obj.perfil not in ["master", "gestor_segem"]:
        return RedirectResponse("/dashboard")
    item = db.query(SegemItem).options(
        joinedload(SegemItem.produtos)
    ).filter(SegemItem.id == item_id).first()
    if not item:
        return RedirectResponse("/segem")
    if user_obj.perfil != "master" and item.municipio_id != user_obj.municipio_id:
        return RedirectResponse("/segem")
    unidades = db.query(Unidade).filter(Unidade.ativo == True).order_by(Unidade.nome).all()
    produtos_segem = db.query(ProdutoSegem).order_by(ProdutoSegem.codigo).all()
    produtos_list = _build_produtos_list(item)
    return templates.TemplateResponse(
        "segem_form.html",
        {
            "request": request,
            "user": user,
            "action": "view",
            "item": item,
            "unidades": unidades,
            "produtos_segem": produtos_segem,
            "produtos_list": produtos_list,
        },
    )


@router.post("/edit/{item_id}")
async def segem_edit_submit(
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
    item = db.query(SegemItem).options(joinedload(SegemItem.produtos)).filter(SegemItem.id == item_id).first()
    if not item:
        return RedirectResponse("/segem")
    if user_obj.perfil != "master" and item.municipio_id != user_obj.municipio_id:
        return RedirectResponse("/segem")
    form = await request.form()
    tombos = form.getlist("num_tombo_gcm")
    valores = form.getlist("valor_rs")

    primeiro_tombo = tombos[0].strip() or None if tombos else None
    primeiro_valor = _parse_valor(valores[0]) if valores else None

    item.ano = int(form.get("ano")) if form.get("ano") else None
    item.num_tombo_gcm = primeiro_tombo
    item.local = (form.get("local") or "").strip() or None
    item.codigo = (form.get("codigo") or "").strip() or None
    item.descricao = (form.get("descricao") or "").strip() or None
    item.situacao = (form.get("situacao") or "").strip() or None
    item.valor_rs = primeiro_valor
    item.entrada_no_siga = (form.get("entrada_no_siga") or "").strip() or None
    item.nota_de_empenho = (form.get("nota_de_empenho") or "").strip() or None
    # Valor da nota de empenho = soma dos valores de todos os produtos (não editável)
    soma_valores = sum(v for v in (_parse_valor(valores[i]) for i in range(len(valores))) if v is not None)
    item.valor_nota_empenho = soma_valores if soma_valores else None
    item.num_nota_fiscal = (form.get("num_nota_fiscal") or "").strip() or None
    item.nome_empresa = (form.get("nome_empresa") or "").strip() or None
    item.classificacao_asi = (form.get("classificacao_asi") or "").strip() or None

    for p in list(item.produtos):
        db.delete(p)
    for i in range(1, max(len(tombos), len(valores))):
        t = (tombos[i].strip() or None) if i < len(tombos) else None
        v = _parse_valor(valores[i]) if i < len(valores) else None
        if t is not None or v is not None:
            db.add(SegemItemProduto(segem_item_id=item.id, num_tombo_gcm=t, valor_rs=v))
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
