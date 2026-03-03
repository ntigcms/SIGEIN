from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi import Form
from models import Requerente
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from database import get_db
from dependencies import get_current_user
from shared_templates import templates
from models import Estado, Municipio, User, Processo, ProcessoAssinante, Tramite, Orgao, Unidade, Grupo, Assunto, Subassunto
from datetime import datetime

router = APIRouter(prefix="/eprotocolo", tags=["E-Protocolo"])


# ========================================
# DASHBOARD PRINCIPAL
# ========================================
@router.get("/")
def eprotocolo_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    """Dashboard principal do E-Protocolo com cards de acesso rápido"""
    if not user:
        return RedirectResponse("/login")
    u = db.query(User).filter(User.email == user).first()
    pode_caixas_complementares = u and u.perfil in [
        "master", "admin_municipal", "gestor_protocolo", "gestor_geral"
    ]
    return templates.TemplateResponse(
        "eprotocolo/eprotocolo_dashboard.html",
        {
            "request": request,
            "user": user,
            "user_obj": u,
            "pode_caixas_complementares": pode_caixas_complementares,
        }
    )


# ========================================
# MÓDULO: PROCESSOS
# ========================================
@router.get("/processos/criar")
def processos_criar(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")
    u = db.query(User).filter(User.email == user).first()
    if not u:
        return RedirectResponse("/login")
    estados = db.query(Estado).order_by(Estado.nome).all()
    return templates.TemplateResponse(
        "eprotocolo/processos/criar.html",
        {"request": request, "user": user, "user_obj": u, "estados": estados}
    )


PERFIS_ASSINANTES = ("master", "admin_municipal", "gestor_protocolo", "gestor_geral")


@router.get("/api/assinantes-elegiveis")
def api_assinantes_elegiveis(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Retorna usuários do mesmo órgão/unidade do usuário logado com perfil Master, Admin Municipal, Gestor de Protocolo ou Gestor Geral (para seleção como assinantes)."""
    if not user:
        return JSONResponse({"error": "Não autorizado"}, status_code=401)
    u = db.query(User).filter(User.email == user).first()
    if not u:
        return JSONResponse({"error": "Não autorizado"}, status_code=401)
    usuarios = (
        db.query(User)
        .filter(
            User.orgao_id == u.orgao_id,
            User.unidade_id == u.unidade_id,
            User.perfil.in_(PERFIS_ASSINANTES),
            User.status == "ativo",
        )
        .order_by(User.nome)
        .all()
    )
    return JSONResponse(
        [{"id": x.id, "nome": x.nome, "perfil": x.perfil} for x in usuarios]
    )


@router.post("/processos/criar")
async def processos_criar_post(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")
    u = db.query(User).filter(User.email == user).first()
    if not u:
        return RedirectResponse("/login")
    form = await request.form()
    assunto = form.get("assunto") or ""
    requerente = form.get("requerente") or ""
    conteudo = form.get("conteudo") or ""
    numero_externo = form.get("numero_externo")
    orgao_destino_id = form.get("orgao_destino_id") or ""
    unidade_destino_id = form.get("unidade_destino_id") or ""
    municipio_destino_id = form.get("municipio_destino_id") or ""
    nivel_acesso = form.get("nivel_acesso") or "Público"
    assinante_ids = form.getlist("assinante_ids[]")
    try:
        oid = int(orgao_destino_id) if orgao_destino_id else None
        uid = int(unidade_destino_id) if unidade_destino_id else None
        mid = int(municipio_destino_id) if municipio_destino_id else None
    except (ValueError, TypeError):
        oid = uid = mid = None
    if not all([oid, uid, mid]):
        return RedirectResponse("/eprotocolo/processos/criar?erro=destinatario", status_code=303)
    ano = datetime.now().year
    count = db.query(Processo).filter(Processo.ano == ano).count()
    seq = count + 1
    numero = f"{seq:02d}/{ano}"
    p = Processo(
        numero=numero,
        ano=ano,
        assunto=assunto,
        requerente=requerente,
        conteudo=conteudo,
        municipio_origem_id=u.municipio_id,
        orgao_origem_id=u.orgao_id,
        unidade_origem_id=u.unidade_id,
        municipio_atual_id=mid,
        orgao_atual_id=oid,
        unidade_atual_id=uid,
        nivel_acesso=nivel_acesso,
        status="Em tramitação",
        created_by=u.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    for aid_str in assinante_ids:
        try:
            aid = int(aid_str)
        except (ValueError, TypeError):
            continue
        if db.query(User).filter(User.id == aid).first():
            pa = ProcessoAssinante(processo_id=p.id, user_id=aid)
            db.add(pa)
    db.commit()
    return RedirectResponse("/eprotocolo/processos/caixa", status_code=303)


@router.get("/processos/caixa")
def processos_caixa(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    aba: str = Query("todos", alias="aba"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(10, ge=5, le=100),
):
    if not user:
        return RedirectResponse("/login")
    u = db.query(User).filter(User.email == user).first()
    if not u:
        return RedirectResponse("/login")
    # Base: processos na unidade atual OU criados pela unidade do usuário
    base_filter = or_(
        Processo.unidade_atual_id == u.unidade_id,
        Processo.unidade_origem_id == u.unidade_id,
    )
    q_base = db.query(Processo).filter(base_filter)

    # Filtro por aba (status e demais critérios da caixa)
    q = q_base
    if aba == "urgentes":
        q = q.filter(Processo.urgente == True)
    elif aba == "assinados":
        q = q.filter(Processo.status == "Assinado")
    elif aba == "a_assinar":
        # Processos em que o usuário é assinante e ainda não estão assinados
        q = q.filter(
            Processo.assinantes.any(ProcessoAssinante.user_id == u.id),
            Processo.status != "Assinado",
        )
    elif aba == "recebidos":
        q = q.filter(Processo.status.in_(["Recebido", "Em tramitação"]))
    elif aba == "em_edicao":
        q = q.filter(Processo.status == "Em edição")
    elif aba == "nao_lidos":
        q = q.filter(Processo.lido_at == None)
    elif aba == "lidos":
        q = q.filter(Processo.lido_at != None)
    elif aba == "nao_atribuidos":
        q = q.filter(Processo.atribuido_to_id == None)

    total = q.count()
    offset = (pagina - 1) * por_pagina
    processos = (
        q.options(
            joinedload(Processo.orgao_origem),
            joinedload(Processo.unidade_origem),
            joinedload(Processo.creator),
            joinedload(Processo.assinantes).joinedload(ProcessoAssinante.user),
        )
        .order_by(Processo.created_at.desc())
        .offset(offset)
        .limit(por_pagina)
        .all()
    )

    # Contagens por aba (para badges)
    cnt_todos = q_base.count()
    cnt_urgentes = q_base.filter(Processo.urgente == True).count()
    cnt_assinados = q_base.filter(Processo.status == "Assinado").count()
    cnt_a_assinar = q_base.filter(
        Processo.assinantes.any(ProcessoAssinante.user_id == u.id),
        Processo.status != "Assinado",
    ).count()
    cnt_recebidos = q_base.filter(Processo.status.in_(["Recebido", "Em tramitação"])).count()
    cnt_em_edicao = q_base.filter(Processo.status == "Em edição").count()
    cnt_nao_lidos = q_base.filter(Processo.lido_at == None).count()
    cnt_lidos = q_base.filter(Processo.lido_at != None).count()
    cnt_nao_atribuidos = q_base.filter(Processo.atribuido_to_id == None).count()

    return templates.TemplateResponse(
        "eprotocolo/processos/caixa.html",
        {
            "request": request,
            "user": user,
            "processos": processos,
            "total": total,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "aba": aba,
            "cnt_todos": cnt_todos,
            "cnt_urgentes": cnt_urgentes,
            "cnt_assinados": cnt_assinados,
            "cnt_a_assinar": cnt_a_assinar,
            "cnt_recebidos": cnt_recebidos,
            "cnt_em_edicao": cnt_em_edicao,
            "cnt_nao_lidos": cnt_nao_lidos,
            "cnt_lidos": cnt_lidos,
            "cnt_nao_atribuidos": cnt_nao_atribuidos,
        },
    )


@router.get("/processos/{processo_id:int}/visualizar")
def processo_visualizar(
    request: Request,
    processo_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Exibe o processo em modo somente leitura, estilo documento/paginado, com histórico de trâmites."""
    if not user:
        return RedirectResponse("/login")
    u = db.query(User).filter(User.email == user).first()
    if not u:
        return RedirectResponse("/login")
    processo = (
        db.query(Processo)
        .options(
            joinedload(Processo.orgao_origem),
            joinedload(Processo.unidade_origem),
            joinedload(Processo.orgao_atual),
            joinedload(Processo.unidade_atual),
            joinedload(Processo.creator),
            joinedload(Processo.assinantes).joinedload(ProcessoAssinante.user),
            joinedload(Processo.tramites).joinedload(Tramite.usuario),
            joinedload(Processo.tramites).joinedload(Tramite.orgao_origem),
            joinedload(Processo.tramites).joinedload(Tramite.unidade_origem),
            joinedload(Processo.tramites).joinedload(Tramite.orgao_destino),
            joinedload(Processo.tramites).joinedload(Tramite.unidade_destino),
        )
        .filter(Processo.id == processo_id)
        .first()
    )
    if not processo:
        return RedirectResponse("/eprotocolo/processos/caixa", status_code=303)
    # Ordenar trâmites por data (mais antigo primeiro)
    tramites_ordenados = sorted(processo.tramites, key=lambda t: t.created_at or datetime.min)
    return templates.TemplateResponse(
        "eprotocolo/processos/visualizar.html",
        {
            "request": request,
            "user": user,
            "processo": processo,
            "tramites": tramites_ordenados,
        },
    )


@router.get("/processos/consulta")
def processos_consulta(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    numero: str = Query(None),
    ano: str = Query(None),
    codigo: str = Query(None),
    numero_externo: str = Query(None),
    status: str = Query(None),
    cpf_cnpj: str = Query(None),
    nome: str = Query(None),
    grupo: str = Query(None),
    assunto: str = Query(None),
    subassunto: str = Query(None),
    estado_id: str = Query(None),
    municipio_id: str = Query(None),
    orgao_id: str = Query(None),
    unidade_id: str = Query(None),
    data_de: str = Query(None),
    data_ate: str = Query(None),
):
    if not user:
        return RedirectResponse("/login")
    u = db.query(User).filter(User.email == user).first()
    if not u:
        return RedirectResponse("/login")

    # Cascata Estado -> Município -> Órgão -> Unidade (igual à tela de criação)
    estados = db.query(Estado).order_by(Estado.nome).all()
    municipios = []
    orgaos = []
    unidades = []

    eid = int(estado_id) if estado_id and estado_id.isdigit() else None
    mid = int(municipio_id) if municipio_id and municipio_id.isdigit() else None
    oid = int(orgao_id) if orgao_id and orgao_id.isdigit() else None

    # Se orgao_id veio na URL, carregar estado/município para preencher cascata
    if oid and not (eid and mid):
        orgao = db.query(Orgao).filter(Orgao.id == oid).first()
        if orgao and orgao.municipio:
            mid = orgao.municipio_id
            eid = orgao.municipio.estado_id

    if eid:
        municipios = db.query(Municipio).filter(Municipio.estado_id == eid, Municipio.ativo == True).order_by(Municipio.nome).all()
    if mid:
        orgaos = db.query(Orgao).filter(Orgao.municipio_id == mid, Orgao.ativo == True).order_by(Orgao.nome).all()
    if oid:
        unidades = db.query(Unidade).filter(Unidade.orgao_id == oid, Unidade.ativo == True).order_by(Unidade.nome).all()

    # Processos (busca em qualquer município quando filtro por órgão/unidade)
    tem_filtro = any([numero, ano, status, nome, assunto, orgao_id, unidade_id, data_de, data_ate])
    q = db.query(Processo)
    if numero:
        q = q.filter(Processo.numero.ilike(f"%{numero}%"))
    if ano:
        try:
            q = q.filter(Processo.ano == int(ano))
        except ValueError:
            pass
    if status:
        q = q.filter(Processo.status == status)
    if nome:
        q = q.filter(Processo.requerente.ilike(f"%{nome}%"))
    if assunto:
        q = q.filter(Processo.assunto.ilike(f"%{assunto}%"))
    if orgao_id:
        try:
            q = q.filter(Processo.orgao_origem_id == int(orgao_id))
        except ValueError:
            pass
    if unidade_id:
        try:
            q = q.filter(Processo.unidade_origem_id == int(unidade_id))
        except ValueError:
            pass
    if data_de:
        try:
            from datetime import datetime
            dt = datetime.strptime(data_de, "%d/%m/%Y")
            q = q.filter(Processo.created_at >= dt)
        except ValueError:
            pass
    if data_ate:
        try:
            from datetime import datetime
            dt = datetime.strptime(data_ate, "%d/%m/%Y")
            dt = dt.replace(hour=23, minute=59, second=59)
            q = q.filter(Processo.created_at <= dt)
        except ValueError:
            pass
    if not tem_filtro:
        processos = []
        total = 0
    else:
        total = q.count()
        processos = q.options(
            joinedload(Processo.orgao_origem),
            joinedload(Processo.unidade_origem),
            joinedload(Processo.creator),
        ).order_by(Processo.created_at.desc()).limit(100).all()
    return templates.TemplateResponse(
        "eprotocolo/processos/consulta.html",
        {
            "request": request,
            "user": user,
            "processos": processos,
            "total": total,
            "numero": numero,
            "ano": ano,
            "codigo": codigo,
            "numero_externo": numero_externo,
            "status": status,
            "cpf_cnpj": cpf_cnpj,
            "nome": nome,
            "grupo": grupo,
            "assunto": assunto,
            "subassunto": subassunto,
            "estado_id": eid,
            "municipio_id": mid,
            "orgao_id": oid,
            "unidade_id": int(unidade_id) if unidade_id and unidade_id.isdigit() else None,
            "data_de": data_de,
            "data_ate": data_ate,
            "estados": estados,
            "municipios": municipios,
            "orgaos": orgaos,
            "unidades": unidades,
            "mostra_resultados": tem_filtro,
        }
    )


@router.get("/processos/historico")
def processos_historico(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/processos/historico.html", {"request": request, "user": user})


@router.get("/processos/arquivados")
def processos_arquivados(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/processos/arquivados.html", {"request": request, "user": user})


@router.get("/processos/atribuir")
def processos_atribuir(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/processos/atribuir.html", {"request": request, "user": user})


# ========================================
# MÓDULO: CIRCULARES
# ========================================
@router.get("/circulares/criar")
def circulares_criar(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/circulares/criar.html", {"request": request, "user": user})


@router.get("/circulares/caixa")
def circulares_caixa(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/circulares/caixa.html", {"request": request, "user": user})


@router.get("/circulares/historico")
def circulares_historico(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/circulares/historico.html", {"request": request, "user": user})


@router.get("/circulares/arquivados")
def circulares_arquivados(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/circulares/arquivados.html", {"request": request, "user": user})


# ========================================
# MÓDULO: ADMINISTRAÇÃO
# ========================================
@router.get("/administracao/requerentes")
def administracao_requerentes(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    nome: str = Query(None),
    tipo_documento: str = Query(None),
    numero_documento: str = Query(None),
):
    if not user:
        return RedirectResponse("/login")
    q = db.query(Requerente)
    if nome:
        q = q.filter(Requerente.nome.ilike(f"%{nome}%"))
    if tipo_documento:
        q = q.filter(Requerente.tipo_documento == tipo_documento)
    if numero_documento:
        q = q.filter(Requerente.numero_documento.ilike(f"%{numero_documento}%"))
    requerentes = q.order_by(Requerente.nome).all()
    return templates.TemplateResponse(
        "eprotocolo/administracao/requerentes.html",
        {
            "request": request,
            "user": user,
            "requerentes": requerentes,
            "nome_filtro": nome or "",
            "tipo_filtro": tipo_documento or "",
            "numero_filtro": numero_documento or "",
        }
    )


@router.get("/administracao/requerentes/cadastrar")
def requerente_cadastrar_form(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse(
        "eprotocolo/administracao/requerente_cadastrar.html",
        {"request": request, "user": user, "requerente": None}
    )


@router.post("/administracao/requerentes/cadastrar")
async def requerente_cadastrar_post(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    nome: str = Form(...),
    tipo_documento: str = Form(...),
    numero_documento: str = Form(...),
    email: str = Form(None),
    cep: str = Form(...),
    endereco: str = Form(...),
    numero_endereco: str = Form(...),
    bairro: str = Form(...),
    complemento: str = Form(None),
    cidade: str = Form(...),
    uf: str = Form(...),
    telefone1: str = Form(None),
    telefone2: str = Form(None),
):
    if not user:
        return RedirectResponse("/login")
    r = Requerente(
        nome=nome,
        tipo_documento=tipo_documento,
        numero_documento=numero_documento,
        email=email or None,
        cep=cep,
        endereco=endereco,
        numero_endereco=numero_endereco,
        bairro=bairro,
        complemento=complemento or None,
        cidade=cidade,
        uf=uf.upper()[:2],
        telefone1=telefone1 or None,
        telefone2=telefone2 or None,
    )
    db.add(r)
    db.commit()
    return RedirectResponse("/eprotocolo/administracao/requerentes", status_code=303)


@router.get("/administracao/requerentes/{requerente_id}/editar")
def requerente_editar_form(
    requerente_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")
    r = db.query(Requerente).filter(Requerente.id == requerente_id).first()
    if not r:
        return RedirectResponse("/eprotocolo/administracao/requerentes", status_code=303)
    return templates.TemplateResponse(
        "eprotocolo/administracao/requerente_cadastrar.html",
        {"request": request, "user": user, "requerente": r}
    )


@router.post("/administracao/requerentes/{requerente_id}/editar")
async def requerente_editar_post(
    requerente_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    nome: str = Form(...),
    tipo_documento: str = Form(...),
    numero_documento: str = Form(...),
    email: str = Form(None),
    cep: str = Form(...),
    endereco: str = Form(...),
    numero_endereco: str = Form(...),
    bairro: str = Form(...),
    complemento: str = Form(None),
    cidade: str = Form(...),
    uf: str = Form(...),
    telefone1: str = Form(None),
    telefone2: str = Form(None),
):
    if not user:
        return RedirectResponse("/login")
    r = db.query(Requerente).filter(Requerente.id == requerente_id).first()
    if not r:
        return RedirectResponse("/eprotocolo/administracao/requerentes", status_code=303)
    r.nome = nome
    r.tipo_documento = tipo_documento
    r.numero_documento = numero_documento
    r.email = email or None
    r.cep = cep
    r.endereco = endereco
    r.numero_endereco = numero_endereco
    r.bairro = bairro
    r.complemento = complemento or None
    r.cidade = cidade
    r.uf = uf.upper()[:2]
    r.telefone1 = telefone1 or None
    r.telefone2 = telefone2 or None
    db.commit()
    return RedirectResponse("/eprotocolo/administracao/requerentes", status_code=303)


@router.get("/administracao/usuarios")
def administracao_usuarios(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse(
        "eprotocolo/administracao/usuarios.html",
        {"request": request, "user": user}
    )


@router.get("/administracao/unidade-designacao")
def administracao_unidade_designacao(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse(
        "eprotocolo/administracao/unidade_designacao.html",
        {"request": request, "user": user}
    )


@router.get("/administracao/caixas-complementares")
def administracao_caixas_complementares(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")
    u = db.query(User).filter(User.email == user).first()
    if not u or u.perfil not in ["master", "admin_municipal", "gestor_protocolo", "gestor_geral"]:
        return RedirectResponse("/eprotocolo", status_code=303)
    return templates.TemplateResponse(
        "eprotocolo/administracao/caixas_complementares.html",
        {"request": request, "user": user}
    )


# ========================================
# ADMINISTRAÇÃO: GRUPO, ASSUNTO, SUBASSUNTO
# ========================================

@router.get("/administracao/grupos")
def administracao_grupos(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    nome: str = Query(None),
):
    if not user:
        return RedirectResponse("/login")
    q = db.query(Grupo).filter(Grupo.ativo == True)
    if nome:
        q = q.filter(Grupo.nome.ilike(f"%{nome}%"))
    grupos = q.order_by(Grupo.nome).all()
    return templates.TemplateResponse(
        "eprotocolo/administracao/grupos.html",
        {"request": request, "user": user, "grupos": grupos, "nome_filtro": nome or ""}
    )


@router.get("/administracao/grupos/cadastrar")
def grupo_cadastrar_form(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse(
        "eprotocolo/administracao/grupo_form.html",
        {"request": request, "user": user, "grupo": None}
    )


@router.post("/administracao/grupos/cadastrar")
async def grupo_cadastrar_post(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    nome: str = Form(...),
):
    if not user:
        return RedirectResponse("/login")
    g = Grupo(nome=nome.strip(), ativo=True)
    db.add(g)
    db.commit()
    return RedirectResponse("/eprotocolo/administracao/grupos", status_code=303)


@router.get("/administracao/grupos/{grupo_id}/editar")
def grupo_editar_form(
    request: Request,
    grupo_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")
    grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not grupo:
        return RedirectResponse("/eprotocolo/administracao/grupos", status_code=303)
    return templates.TemplateResponse(
        "eprotocolo/administracao/grupo_form.html",
        {"request": request, "user": user, "grupo": grupo}
    )


@router.post("/administracao/grupos/{grupo_id}/editar")
async def grupo_editar_post(
    grupo_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    nome: str = Form(...),
):
    if not user:
        return RedirectResponse("/login")
    grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not grupo:
        return RedirectResponse("/eprotocolo/administracao/grupos", status_code=303)
    grupo.nome = nome.strip()
    db.commit()
    return RedirectResponse("/eprotocolo/administracao/grupos", status_code=303)


@router.get("/administracao/assuntos")
def administracao_assuntos(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    grupo_id: str = Query(None),
    nome: str = Query(None),
):
    if not user:
        return RedirectResponse("/login")
    grupos = db.query(Grupo).filter(Grupo.ativo == True).order_by(Grupo.nome).all()
    q = db.query(Assunto).join(Grupo).filter(Assunto.ativo == True)
    if grupo_id and grupo_id.isdigit():
        q = q.filter(Assunto.grupo_id == int(grupo_id))
    if nome:
        q = q.filter(Assunto.nome.ilike(f"%{nome}%"))
    assuntos = q.order_by(Grupo.nome, Assunto.nome).all()
    return templates.TemplateResponse(
        "eprotocolo/administracao/assuntos.html",
        {
            "request": request,
            "user": user,
            "assuntos": assuntos,
            "grupos": grupos,
            "grupo_id": int(grupo_id) if grupo_id and grupo_id.isdigit() else None,
            "nome_filtro": nome or "",
        }
    )


@router.get("/administracao/assuntos/cadastrar")
def assunto_cadastrar_form(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")
    grupos = db.query(Grupo).filter(Grupo.ativo == True).order_by(Grupo.nome).all()
    return templates.TemplateResponse(
        "eprotocolo/administracao/assunto_form.html",
        {"request": request, "user": user, "assunto": None, "grupos": grupos}
    )


@router.post("/administracao/assuntos/cadastrar")
async def assunto_cadastrar_post(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    grupo_id: int = Form(...),
    nome: str = Form(...),
):
    if not user:
        return RedirectResponse("/login")
    a = Assunto(grupo_id=grupo_id, nome=nome.strip(), ativo=True)
    db.add(a)
    db.commit()
    return RedirectResponse("/eprotocolo/administracao/assuntos", status_code=303)


@router.get("/administracao/assuntos/{assunto_id}/editar")
def assunto_editar_form(
    request: Request,
    assunto_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")
    assunto = db.query(Assunto).filter(Assunto.id == assunto_id).first()
    if not assunto:
        return RedirectResponse("/eprotocolo/administracao/assuntos", status_code=303)
    grupos = db.query(Grupo).filter(Grupo.ativo == True).order_by(Grupo.nome).all()
    return templates.TemplateResponse(
        "eprotocolo/administracao/assunto_form.html",
        {"request": request, "user": user, "assunto": assunto, "grupos": grupos}
    )


@router.post("/administracao/assuntos/{assunto_id}/editar")
async def assunto_editar_post(
    assunto_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    grupo_id: int = Form(...),
    nome: str = Form(...),
):
    if not user:
        return RedirectResponse("/login")
    assunto = db.query(Assunto).filter(Assunto.id == assunto_id).first()
    if not assunto:
        return RedirectResponse("/eprotocolo/administracao/assuntos", status_code=303)
    assunto.grupo_id = grupo_id
    assunto.nome = nome.strip()
    db.commit()
    return RedirectResponse("/eprotocolo/administracao/assuntos", status_code=303)


@router.get("/administracao/subassuntos")
def administracao_subassuntos(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    grupo_id: str = Query(None),
    assunto_id: str = Query(None),
    nome: str = Query(None),
):
    if not user:
        return RedirectResponse("/login")
    grupos = db.query(Grupo).filter(Grupo.ativo == True).order_by(Grupo.nome).all()
    assuntos = []
    if grupo_id and grupo_id.isdigit():
        assuntos = db.query(Assunto).filter(Assunto.grupo_id == int(grupo_id), Assunto.ativo == True).order_by(Assunto.nome).all()
    q = db.query(Subassunto).join(Assunto).join(Grupo).filter(Subassunto.ativo == True)
    if assunto_id and assunto_id.isdigit():
        q = q.filter(Subassunto.assunto_id == int(assunto_id))
    if grupo_id and grupo_id.isdigit():
        q = q.filter(Assunto.grupo_id == int(grupo_id))
    if nome:
        q = q.filter(Subassunto.nome.ilike(f"%{nome}%"))
    subassuntos = q.order_by(Grupo.nome, Assunto.nome, Subassunto.nome).all()
    return templates.TemplateResponse(
        "eprotocolo/administracao/subassuntos.html",
        {
            "request": request,
            "user": user,
            "subassuntos": subassuntos,
            "grupos": grupos,
            "assuntos": assuntos,
            "grupo_id": int(grupo_id) if grupo_id and grupo_id.isdigit() else None,
            "assunto_id": int(assunto_id) if assunto_id and assunto_id.isdigit() else None,
            "nome_filtro": nome or "",
        }
    )


@router.get("/administracao/subassuntos/cadastrar")
def subassunto_cadastrar_form(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    grupo_id: str = Query(None),
):
    if not user:
        return RedirectResponse("/login")
    grupos = db.query(Grupo).filter(Grupo.ativo == True).order_by(Grupo.nome).all()
    assuntos = []
    if grupo_id and grupo_id.isdigit():
        assuntos = db.query(Assunto).filter(Assunto.grupo_id == int(grupo_id), Assunto.ativo == True).order_by(Assunto.nome).all()
    return templates.TemplateResponse(
        "eprotocolo/administracao/subassunto_form.html",
        {"request": request, "user": user, "subassunto": None, "grupos": grupos, "assuntos": assuntos, "grupo_id": int(grupo_id) if grupo_id and grupo_id.isdigit() else None}
    )


@router.post("/administracao/subassuntos/cadastrar")
async def subassunto_cadastrar_post(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    assunto_id: int = Form(...),
    nome: str = Form(...),
):
    if not user:
        return RedirectResponse("/login")
    s = Subassunto(assunto_id=assunto_id, nome=nome.strip(), ativo=True)
    db.add(s)
    db.commit()
    return RedirectResponse("/eprotocolo/administracao/subassuntos", status_code=303)


@router.get("/administracao/subassuntos/{subassunto_id}/editar")
def subassunto_editar_form(
    request: Request,
    subassunto_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")
    subassunto = db.query(Subassunto).filter(Subassunto.id == subassunto_id).first()
    if not subassunto:
        return RedirectResponse("/eprotocolo/administracao/subassuntos", status_code=303)
    grupos = db.query(Grupo).filter(Grupo.ativo == True).order_by(Grupo.nome).all()
    assuntos = db.query(Assunto).filter(Assunto.grupo_id == subassunto.assunto.grupo_id, Assunto.ativo == True).order_by(Assunto.nome).all()
    return templates.TemplateResponse(
        "eprotocolo/administracao/subassunto_form.html",
        {"request": request, "user": user, "subassunto": subassunto, "grupos": grupos, "assuntos": assuntos}
    )


@router.post("/administracao/subassuntos/{subassunto_id}/editar")
async def subassunto_editar_post(
    subassunto_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    assunto_id: int = Form(...),
    nome: str = Form(...),
):
    if not user:
        return RedirectResponse("/login")
    subassunto = db.query(Subassunto).filter(Subassunto.id == subassunto_id).first()
    if not subassunto:
        return RedirectResponse("/eprotocolo/administracao/subassuntos", status_code=303)
    subassunto.assunto_id = assunto_id
    subassunto.nome = nome.strip()
    db.commit()
    return RedirectResponse("/eprotocolo/administracao/subassuntos", status_code=303)


# ========================================
# MÓDULO: AJUDA
# ========================================
@router.get("/ajuda/manual")
def ajuda_manual(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/ajuda/manual.html", {"request": request, "user": user})


@router.get("/ajuda/novidades")
def ajuda_novidades(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/ajuda/novidades.html", {"request": request, "user": user})


@router.get("/ajuda/faq")
def ajuda_faq(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/ajuda/faq.html", {"request": request, "user": user})


@router.get("/ajuda/termo-uso")
def ajuda_termo_uso(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/ajuda/termo_uso.html", {"request": request, "user": user})


@router.get("/ajuda/integracao")
def ajuda_integracao(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/ajuda/integracao.html", {"request": request, "user": user})