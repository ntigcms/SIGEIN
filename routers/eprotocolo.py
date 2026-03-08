from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse, Response
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
    """Retorna todos os usuários cadastrados na mesma unidade do usuário logado."""
    if not user:
        return JSONResponse({"error": "Não autorizado"}, status_code=401)
    u = db.query(User).filter(User.email == user).first()
    if not u:
        return JSONResponse({"error": "Não autorizado"}, status_code=401)

    usuarios = (
        db.query(User)
        .filter(
            User.unidade_id == u.unidade_id,
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
    if aba == "arquivados":
        q = q.filter(Processo.arquivado == True)
    else:
        # Nas demais abas, só processos não arquivados
        q = q.filter(Processo.arquivado == False)
        if aba == "urgentes":
            q = q.filter(Processo.urgente == True)
        elif aba == "assinados":
            q = q.filter(Processo.status == "Assinado")
        elif aba == "a_assinar":
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

    # Contagens por aba (para badges) — abas de tramitação só consideram não arquivados
    q_nao_arq = q_base.filter(Processo.arquivado == False)
    cnt_todos = q_nao_arq.count()
    cnt_urgentes = q_nao_arq.filter(Processo.urgente == True).count()
    cnt_assinados = q_nao_arq.filter(Processo.status == "Assinado").count()
    cnt_a_assinar = q_nao_arq.filter(
        Processo.assinantes.any(ProcessoAssinante.user_id == u.id),
        Processo.status != "Assinado",
    ).count()
    cnt_recebidos = q_nao_arq.filter(Processo.status.in_(["Recebido", "Em tramitação"])).count()
    cnt_em_edicao = q_nao_arq.filter(Processo.status == "Em edição").count()
    cnt_nao_lidos = q_nao_arq.filter(Processo.lido_at == None).count()
    cnt_lidos = q_nao_arq.filter(Processo.lido_at != None).count()
    cnt_arquivados = q_base.filter(Processo.arquivado == True).count()

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
            "cnt_arquivados": cnt_arquivados,
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
            joinedload(Processo.processo_principal),
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
    # Marcar como lido ao visualizar
    processo.lido_at = datetime.utcnow()
    db.commit()
    # Ordenar trâmites por data (mais antigo primeiro)
    tramites_ordenados = sorted(processo.tramites, key=lambda t: t.created_at or datetime.min)
    # Histórico unificado: criação + tramitações (futuro: arquivamento, apreensamento, etc.)
    historico = []
    # 1. Criação do processo (sempre primeiro)
    origem = processo.orgao_origem and processo.unidade_origem
    dest_str = "-"
    if origem:
        dest_str = f"{(processo.orgao_origem.sigla or processo.orgao_origem.nome)} / {(processo.unidade_origem.sigla or processo.unidade_origem.nome)}"
    historico.append({
        "tipo": "Criação",
        "data": processo.created_at,
        "procedencia": "-",
        "destino": dest_str,
        "por": processo.creator.nome if processo.creator else "-",
        "tramite_id": None,
    })
    # 2. Tramitações
    for t in tramites_ordenados:
        proc = f"{(t.orgao_origem.sigla or t.orgao_origem.nome) if t.orgao_origem else '-'} / {(t.unidade_origem.sigla or t.unidade_origem.nome) if t.unidade_origem else '-'}"
        dest = f"{(t.orgao_destino.sigla or t.orgao_destino.nome) if t.orgao_destino else '-'} / {(t.unidade_destino.sigla or t.unidade_destino.nome) if t.unidade_destino else '-'}"
        historico.append({
            "tipo": "Tramitação",
            "data": t.created_at,
            "procedencia": proc,
            "destino": dest,
            "por": t.usuario.nome if t.usuario else "-",
            "tramite_id": t.id,
        })
    # Dias na unidade atual
    data_ref = processo.created_at
    if tramites_ordenados and tramites_ordenados[-1].created_at:
        data_ref = tramites_ordenados[-1].created_at
    try:
        delta = datetime.now() - (data_ref or datetime.min)
        dias_na_unidade = max(0, delta.days)
    except Exception:
        dias_na_unidade = 0
    return templates.TemplateResponse(
        "eprotocolo/processos/visualizar.html",
        {
            "request": request,
            "user": user,
            "processo": processo,
            "historico": historico,
            "dias_na_unidade": dias_na_unidade,
        },
    )


@router.get("/api/processos-apensaveis")
def api_processos_apensaveis(
    q: str = Query("", description="Busca por número, assunto ou requerente"),
    excluir_id: int = Query(None, description="ID do processo a excluir (atual)"),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Retorna processos que podem ser alvo de apensamento: públicos da unidade do usuário ou onde o usuário é requerente."""
    if not user:
        return JSONResponse({"error": "Não autorizado"}, status_code=401)
    u = db.query(User).filter(User.email == user).first()
    if not u:
        return JSONResponse({"error": "Não autorizado"}, status_code=401)

    # Filtro base: processos públicos da unidade OU processos onde o usuário é requerente
    filtro_publico = (Processo.unidade_atual_id == u.unidade_id) & (Processo.nivel_acesso == "Público")
    if u.nome and u.nome.strip():
        filtro_acesso = or_(filtro_publico, Processo.requerente.ilike(f"%{u.nome.strip()}%"))
    else:
        filtro_acesso = filtro_publico

    q_base = db.query(Processo).filter(filtro_acesso)

    if excluir_id:
        q_base = q_base.filter(Processo.id != excluir_id)

    if q and q.strip():
        termo = f"%{q.strip()}%"
        q_base = q_base.filter(
            or_(
                Processo.numero.ilike(termo),
                Processo.assunto.ilike(termo),
                Processo.requerente.ilike(termo),
            )
        )

    processos = (
        q_base.options(
            joinedload(Processo.orgao_atual),
            joinedload(Processo.unidade_atual),
        )
        .order_by(Processo.created_at.desc())
        .limit(50)
        .all()
    )
    return JSONResponse([
        {
            "id": p.id,
            "numero": p.numero,
            "ano": p.ano,
            "assunto": p.assunto or "-",
            "requerente": p.requerente or "-",
            "status": p.status or "-",
            "orgao": (p.orgao_atual.sigla or p.orgao_atual.nome) if p.orgao_atual else "-",
            "unidade": (p.unidade_atual.sigla or p.unidade_atual.nome) if p.unidade_atual else "-",
        }
        for p in processos
    ])


@router.post("/processos/{processo_id:int}/apensar")
async def processo_apensar_post(
    processo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Apensa o processo atual ao processo principal informado."""
    if not user:
        return JSONResponse({"error": "Não autorizado"}, status_code=401)
    u = db.query(User).filter(User.email == user).first()
    if not u:
        return JSONResponse({"error": "Não autorizado"}, status_code=401)

    form = await request.form()
    processo_principal_id = form.get("processo_principal_id")
    try:
        ppid = int(processo_principal_id) if processo_principal_id else None
    except (ValueError, TypeError):
        return JSONResponse({"error": "Processo principal inválido"}, status_code=400)

    if not ppid:
        return JSONResponse({"error": "Selecione o processo ao qual apensar"}, status_code=400)

    if ppid == processo_id:
        return JSONResponse({"error": "Não é possível apensar um processo a si mesmo"}, status_code=400)

    processo = db.query(Processo).filter(Processo.id == processo_id).first()
    if not processo:
        return JSONResponse({"error": "Processo não encontrado"}, status_code=404)

    if processo.processo_principal_id:
        return JSONResponse({"error": "Este processo já está apensado a outro"}, status_code=400)

    principal = db.query(Processo).filter(Processo.id == ppid).first()
    if not principal:
        return JSONResponse({"error": "Processo principal não encontrado"}, status_code=404)

    # Verificar permissão: principal deve ser público da unidade OU usuário é requerente
    partes_req = [p.strip().upper() for p in (principal.requerente or "").split(";") if p.strip()]
    user_nome_upper = (u.nome or "").strip().upper()
    pode = (
        (principal.unidade_atual_id == u.unidade_id and principal.nivel_acesso == "Público")
        or (user_nome_upper and user_nome_upper in partes_req)
    )
    if not pode:
        return JSONResponse({"error": "Sem permissão para apensar a este processo"}, status_code=403)

    processo.processo_principal_id = ppid
    db.commit()
    return JSONResponse({"ok": True, "message": "Processo apensado com sucesso", "processo_id": processo_id})


@router.post("/processos/{processo_id:int}/urgente")
def processo_toggle_urgente(
    processo_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Alterna a flag urgente do processo (criticidade alta)."""
    if not user:
        return JSONResponse({"error": "Não autorizado"}, status_code=401)
    processo = db.query(Processo).filter(Processo.id == processo_id).first()
    if not processo:
        return JSONResponse({"error": "Processo não encontrado"}, status_code=404)
    processo.urgente = not processo.urgente
    db.commit()
    return JSONResponse({"ok": True, "urgente": processo.urgente})


@router.post("/processos/{processo_id:int}/tramitar")
async def processo_tramitar_post(
    processo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Tramita o processo para a caixa de outra unidade. Registra quem tramitou, data/hora e despacho."""
    if not user:
        return JSONResponse({"error": "Não autorizado"}, status_code=401)
    u = db.query(User).filter(User.email == user).first()
    if not u:
        return JSONResponse({"error": "Não autorizado"}, status_code=401)

    form = await request.form()
    municipio_destino_id = form.get("municipio_destino_id")
    orgao_destino_id = form.get("orgao_destino_id")
    unidade_destino_id = form.get("unidade_destino_id")
    despacho = form.get("despacho") or ""

    try:
        mid = int(municipio_destino_id) if municipio_destino_id else None
        oid = int(orgao_destino_id) if orgao_destino_id else None
        uid = int(unidade_destino_id) if unidade_destino_id else None
    except (ValueError, TypeError):
        return JSONResponse({"error": "Dados do destinatário inválidos"}, status_code=400)

    if not all([mid, oid, uid]):
        return JSONResponse({"error": "Selecione Estado, Município, Órgão e Unidade destinatários"}, status_code=400)

    processo = db.query(Processo).filter(Processo.id == processo_id).first()
    if not processo:
        return JSONResponse({"error": "Processo não encontrado"}, status_code=404)

    # Validar que a unidade pertence ao órgão e ao município
    unidade = db.query(Unidade).filter(Unidade.id == uid).first()
    if not unidade or unidade.orgao_id != oid:
        return JSONResponse({"error": "Unidade não pertence ao órgão informado"}, status_code=400)
    orgao = db.query(Orgao).filter(Orgao.id == oid).first()
    if not orgao or orgao.municipio_id != mid:
        return JSONResponse({"error": "Órgão não pertence ao município informado"}, status_code=400)

    # Não tramitar para a mesma unidade
    if processo.unidade_atual_id == uid:
        return JSONResponse({"error": "O processo já está nesta unidade"}, status_code=400)

    # Criar registro de Tramite (origem = localização atual do processo)
    tramite = Tramite(
        processo_id=processo_id,
        municipio_origem_id=processo.municipio_atual_id,
        orgao_origem_id=processo.orgao_atual_id,
        unidade_origem_id=processo.unidade_atual_id,
        municipio_destino_id=mid,
        orgao_destino_id=oid,
        unidade_destino_id=uid,
        despacho=despacho.strip() or None,
        anexo_path=None,  # TODO: suporte a upload de arquivos
        created_by=u.id,
    )
    db.add(tramite)

    # Atualizar localização atual do processo
    processo.municipio_atual_id = mid
    processo.orgao_atual_id = oid
    processo.unidade_atual_id = uid
    processo.status = "Em tramitação"
    processo.lido_at = None  # Unidade destino ainda não leu
    processo.atribuido_to_id = None  # Desatribuir ao tramitar

    db.commit()
    return JSONResponse({"ok": True, "message": "Processo tramitado com sucesso", "processo_id": processo_id})


def _html_para_texto(raw: str) -> str:
    """Converte HTML para texto seguro para Paragraph do ReportLab."""
    import re
    texto = raw or ""
    texto = re.sub(r"<[^>]+>", " ", texto).replace("&nbsp;", " ").strip()
    texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return texto.replace("\n", "<br/>") if texto else "-"


def _quadro_cabecalho(linhas, styles) -> "Table":
    """Retorna uma Table com borda contendo campos rotulo:valor em linhas."""
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    data = [[Paragraph(f"<b>{r}</b>", styles["Normal"]), Paragraph(v or "-", styles["Normal"])] for r, v in linhas]
    t = Table(data, colWidths=[4*cm, None])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#495057")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dee2e6")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e9ecef")),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    return t


def _quadro_conteudo(texto: str, styles) -> "Table":
    """Retorna uma Table com borda para bloco de conteúdo/despacho."""
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib import colors
    p = Paragraph(texto, styles["Normal"])
    t = Table([[p]], colWidths=[None])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#495057")),
        ("PADDING", (0, 0), (-1, -1), 12),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
    ]))
    return t


def _bloco_assinatura(nome: str, cargo_unidade: str, data_hora: str, styles) -> list:
    """Retorna elementos do bloco de assinatura eletrônica no estilo de referência."""
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    nome_upper = (nome or "-").upper()
    cargo_upper = (cargo_unidade or "-").upper()
    # Formato: Assinatura eletrônica: DD/MM/YYYY HH:MM:SS
    assinatura_str = f"Assinatura eletrônica: {data_hora}" if data_hora else "Assinatura eletrônica: -"
    return [
        Spacer(1, 16),
        Paragraph(f"<b>{nome_upper}</b>", ParagraphStyle(
            name="AssinaturaNome", parent=styles["Normal"], fontSize=11, spaceAfter=4
        )),
        Paragraph(f"<b>{cargo_upper}</b>", ParagraphStyle(
            name="AssinaturaCargo", parent=styles["Normal"], fontSize=11, spaceAfter=4
        )),
        Paragraph(assinatura_str, ParagraphStyle(
            name="AssinaturaData", parent=styles["Normal"], fontSize=9, textColor="gray"
        )),
    ]


def _gerar_pdf_processo(processo, tramites):
    """Gera PDF do processo: cada movimentação em sua própria página, com cabeçalho e campos em quadros."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BoxTitle", parent=styles["Heading2"], fontSize=11, spaceAfter=6))
    normal = styles["Normal"]

    story = []

    # ---------- PÁGINA 1: CRIAÇÃO ----------
    titulo = Paragraph(f"<b>PROCESSO {processo.numero}</b> — Criação", ParagraphStyle(
        name="TituloPag", parent=normal, fontSize=14, spaceAfter=12, alignment=1
    ))
    story.append(titulo)
    story.append(Spacer(1, 8))

    origem_str = f"{(processo.orgao_origem.sigla or processo.orgao_origem.nome) if processo.orgao_origem else '-'} / {(processo.unidade_origem.sigla or processo.unidade_origem.nome) if processo.unidade_origem else '-'}"
    dest_str = origem_str  # na criação, destino = origem
    data_str = processo.created_at.strftime("%d/%m/%Y %H:%M") if processo.created_at else "-"
    por_str = processo.creator.nome if processo.creator else "-"

    cab_criacao = [
        ("Assunto", processo.assunto or "Sem assunto"),
        ("Requerente", processo.requerente or "-"),
        ("Origem", origem_str),
        ("Destino", dest_str),
        ("Data/Hora", data_str),
        ("Por", por_str),
    ]
    story.append(_quadro_cabecalho(cab_criacao, styles))
    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>Conteúdo</b>", normal))
    story.append(Spacer(1, 4))
    conteudo_texto = _html_para_texto(processo.conteudo or "Sem conteúdo.")
    story.append(_quadro_conteudo(conteudo_texto, styles))

    # Assinatura da criação (criador)
    creator = processo.creator
    nome_criador = creator.nome if creator else "-"
    cargo_criador = "-"
    if creator:
        if creator.unidade:
            cargo_criador = creator.unidade.nome or (creator.orgao.nome if creator.orgao else "-")
        elif creator.orgao:
            cargo_criador = creator.orgao.nome
    data_criacao = processo.created_at.strftime("%d/%m/%Y %H:%M:%S") if processo.created_at else ""
    story.extend(_bloco_assinatura(nome_criador, cargo_criador, data_criacao, styles))

    # ---------- PÁGINAS 2+: TRAMITAÇÕES ----------
    for tram in tramites:
        story.append(PageBreak())

        proc_orig = f"{(tram.orgao_origem.sigla or tram.orgao_origem.nome) if tram.orgao_origem else '-'} / {(tram.unidade_origem.sigla or tram.unidade_origem.nome) if tram.unidade_origem else '-'}"
        proc_dest = f"{(tram.orgao_destino.sigla or tram.orgao_destino.nome) if tram.orgao_destino else '-'} / {(tram.unidade_destino.sigla or tram.unidade_destino.nome) if tram.unidade_destino else '-'}"
        data_tram = tram.created_at.strftime("%d/%m/%Y %H:%M") if tram.created_at else "-"
        por_tram = tram.usuario.nome if tram.usuario else "-"

        titulo_tram = Paragraph(
            f"<b>PROCESSO {processo.numero}</b> — Tramitação",
            ParagraphStyle(name="TituloTram", parent=normal, fontSize=14, spaceAfter=12, alignment=1)
        )
        story.append(titulo_tram)
        story.append(Spacer(1, 8))

        cab_tram = [
            ("Origem", proc_orig),
            ("Destino", proc_dest),
            ("Data/Hora", data_tram),
            ("Por", por_tram),
        ]
        story.append(_quadro_cabecalho(cab_tram, styles))
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Despacho</b>", normal))
        story.append(Spacer(1, 4))
        despacho_texto = _html_para_texto(tram.despacho or "-")
        story.append(_quadro_conteudo(despacho_texto, styles))

        # Assinatura da tramitação (quem tramitou)
        usuario_tram = tram.usuario
        nome_tram = usuario_tram.nome if usuario_tram else "-"
        cargo_tram = "-"
        if usuario_tram:
            if usuario_tram.unidade:
                cargo_tram = usuario_tram.unidade.nome or (usuario_tram.orgao.nome if usuario_tram.orgao else "-")
            elif usuario_tram.orgao:
                cargo_tram = usuario_tram.orgao.nome
        data_tram_sig = tram.created_at.strftime("%d/%m/%Y %H:%M:%S") if tram.created_at else ""
        story.extend(_bloco_assinatura(nome_tram, cargo_tram, data_tram_sig, styles))

    doc.build(story)
    return buffer.getvalue()


@router.get("/processos/{processo_id:int}/pdf")
def processo_pdf(
    processo_id: int,
    download: int = Query(0, description="1 para download"),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Retorna o processo em PDF (visualizar no navegador ou download)."""
    if not user:
        return RedirectResponse("/login")
    processo = (
        db.query(Processo)
        .options(
            joinedload(Processo.creator).options(
                joinedload(User.orgao),
                joinedload(User.unidade),
            ),
            joinedload(Processo.orgao_origem), joinedload(Processo.unidade_origem),
            joinedload(Processo.orgao_atual), joinedload(Processo.unidade_atual),
            joinedload(Processo.tramites).options(
                joinedload(Tramite.usuario).options(
                    joinedload(User.orgao),
                    joinedload(User.unidade),
                ),
                joinedload(Tramite.orgao_origem),
                joinedload(Tramite.unidade_origem),
                joinedload(Tramite.orgao_destino),
                joinedload(Tramite.unidade_destino),
            ),
        )
        .filter(Processo.id == processo_id)
        .first()
    )
    if not processo:
        return RedirectResponse("/eprotocolo/processos/caixa", status_code=303)
    # Marcar como lido ao imprimir ou baixar PDF
    processo.lido_at = datetime.utcnow()
    db.commit()
    tramites = sorted(processo.tramites, key=lambda t: t.created_at or datetime.min)
    pdf_bytes = _gerar_pdf_processo(processo, tramites)
    filename = f"processo_{processo.numero.replace('/', '_')}.pdf"
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


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
def processos_historico(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    pesquisa: str = Query("", alias="pesquisa"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(10, ge=5, le=100),
):
    """Histórico da Unidade: lista processos da unidade do usuário com paginação e busca."""
    if not user:
        return RedirectResponse("/login")
    u = db.query(User).filter(User.email == user).first()
    if not u:
        return RedirectResponse("/login")
    base_filter = or_(
        Processo.unidade_atual_id == u.unidade_id,
        Processo.unidade_origem_id == u.unidade_id,
    )
    q = db.query(Processo).filter(base_filter)
    if pesquisa and pesquisa.strip():
        termo = f"%{pesquisa.strip()}%"
        q = q.filter(
            or_(
                Processo.numero.ilike(termo),
                Processo.assunto.ilike(termo),
                Processo.requerente.ilike(termo),
            )
        )
    total = q.count()
    offset = (pagina - 1) * por_pagina
    processos = (
        q.options(
            joinedload(Processo.orgao_origem),
            joinedload(Processo.unidade_origem),
            joinedload(Processo.tramites),
        )
        .order_by(Processo.created_at.desc())
        .offset(offset)
        .limit(por_pagina)
        .all()
    )
    # Data de atualização: última tramitação ou criação
    def ultima_atualizacao(p):
        if p.tramites:
            ult = max(p.tramites, key=lambda t: t.created_at or datetime.min)
            return ult.created_at
        return p.created_at

    processos_com_data = [(p, ultima_atualizacao(p)) for p in processos]
    return templates.TemplateResponse(
        "eprotocolo/processos/historico.html",
        {
            "request": request,
            "user": user,
            "processos": processos,
            "processos_com_data": processos_com_data,
            "total": total,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "pesquisa": pesquisa or "",
            "ultima_pagina": ((total + por_pagina - 1) // por_pagina) if total else 1,
        },
    )


@router.post("/processos/{processo_id:int}/arquivar")
async def processo_arquivar(
    request: Request,
    processo_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Marca o processo como arquivado (arquivado=True, arquivado_at=now, arquivado_por_id=usuário)."""
    if not user:
        return RedirectResponse("/login")
    u = db.query(User).filter(User.email == user).first()
    if not u:
        return RedirectResponse("/login")
    processo = db.query(Processo).filter(Processo.id == processo_id).first()
    if not processo:
        return RedirectResponse("/eprotocolo/processos/caixa", status_code=303)
    form = await request.form()
    redirect_to = form.get("redirect") or request.query_params.get("redirect") or "/eprotocolo/processos/caixa?aba=arquivados"
    processo.arquivado = True
    processo.arquivado_at = datetime.utcnow()
    processo.arquivado_por_id = u.id
    db.commit()
    return RedirectResponse(str(redirect_to), status_code=303)


@router.post("/processos/{processo_id:int}/desarquivar")
async def processo_desarquivar(
    request: Request,
    processo_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Remove o processo do arquivo (arquivado=False)."""
    if not user:
        return RedirectResponse("/login")
    processo = db.query(Processo).filter(Processo.id == processo_id).first()
    if not processo:
        return RedirectResponse("/eprotocolo/processos/caixa", status_code=303)
    form = await request.form()
    redirect_to = form.get("redirect") or request.query_params.get("redirect") or "/eprotocolo/processos/caixa"
    processo.arquivado = False
    processo.arquivado_at = None
    processo.arquivado_por_id = None
    db.commit()
    return RedirectResponse(str(redirect_to), status_code=303)


@router.get("/processos/arquivados")
def processos_arquivados(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    pesquisa: str = Query("", alias="pesquisa"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(10, ge=5, le=100),
):
    """Processos Arquivados: lista processos arquivados da unidade do usuário com paginação e busca."""
    if not user:
        return RedirectResponse("/login")
    u = db.query(User).filter(User.email == user).first()
    if not u:
        return RedirectResponse("/login")
    base_filter = or_(
        Processo.unidade_atual_id == u.unidade_id,
        Processo.unidade_origem_id == u.unidade_id,
    )
    q = db.query(Processo).filter(base_filter, Processo.arquivado == True)
    if pesquisa and pesquisa.strip():
        termo = f"%{pesquisa.strip()}%"
        q = q.filter(
            or_(
                Processo.numero.ilike(termo),
                Processo.assunto.ilike(termo),
                Processo.requerente.ilike(termo),
            )
        )
    total = q.count()
    offset = (pagina - 1) * por_pagina
    processos = (
        q.options(
            joinedload(Processo.orgao_origem),
            joinedload(Processo.unidade_origem),
            joinedload(Processo.tramites),
            joinedload(Processo.arquivado_por),
        )
        .order_by(Processo.arquivado_at.desc(), Processo.created_at.desc())
        .offset(offset)
        .limit(por_pagina)
        .all()
    )
    # Data de atualização: arquivado_at ou última tramitação ou criação
    def data_atualizacao(p):
        if p.arquivado_at:
            return p.arquivado_at
        if p.tramites:
            ult = max(p.tramites, key=lambda t: t.created_at or datetime.min)
            return ult.created_at
        return p.created_at

    processos_com_data = [(p, data_atualizacao(p)) for p in processos]
    return templates.TemplateResponse(
        "eprotocolo/processos/arquivados.html",
        {
            "request": request,
            "user": user,
            "user_obj": u,
            "processos": processos,
            "processos_com_data": processos_com_data,
            "total": total,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "pesquisa": pesquisa or "",
            "ultima_pagina": ((total + por_pagina - 1) // por_pagina) if total else 1,
        },
    )


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