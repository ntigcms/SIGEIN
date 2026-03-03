from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from models import Estado, Municipio, Orgao, Unidade, Grupo, Assunto, Subassunto

router = APIRouter(prefix="/api", tags=["API Geográfica"])


@router.get("/estados")
def listar_estados(db: Session = Depends(get_db)):
    """Lista todos os estados"""
    estados = db.query(Estado).order_by(Estado.nome).all()
    return [{"id": e.id, "nome": e.nome, "uf": e.uf} for e in estados]


@router.get("/municipios/{estado_id}")
def listar_municipios(estado_id: int, db: Session = Depends(get_db)):
    """Lista municípios de um estado"""
    municipios = (
        db.query(Municipio)
        .filter(Municipio.estado_id == estado_id, Municipio.ativo == True)
        .order_by(Municipio.nome)
        .all()
    )
    return [{"id": m.id, "nome": m.nome} for m in municipios]


@router.get("/orgaos/{municipio_id}")
def listar_orgaos(municipio_id: int, db: Session = Depends(get_db)):
    """Lista órgãos de um município"""
    orgaos = (
        db.query(Orgao)
        .filter(Orgao.municipio_id == municipio_id, Orgao.ativo == True)
        .order_by(Orgao.nome)
        .all()
    )
    return [
        {
            "id": o.id,
            "nome": o.nome,
            "sigla": o.sigla
        }
        for o in orgaos
    ]


@router.get("/unidades/{orgao_id}")
def listar_unidades(orgao_id: int, db: Session = Depends(get_db)):
    """Lista unidades de um órgão"""
    unidades = (
        db.query(Unidade)
        .filter(Unidade.orgao_id == orgao_id, Unidade.ativo == True)
        .order_by(Unidade.nome)
        .all()
    )
    return [
        {
            "id": u.id,
            "nome": u.nome,
            "sigla": u.sigla
        }
        for u in unidades
    ]


@router.get("/estado-do-municipio/{municipio_id}")
def get_estado_do_municipio(municipio_id: int, db: Session = Depends(get_db)):
    """Retorna o estado de um município (para modo edição)"""
    municipio = db.query(Municipio).filter(Municipio.id == municipio_id).first()
    
    if not municipio:
        return {"error": "Município não encontrado"}
    
    return {
        "estado_id": municipio.estado_id,
        "municipio_id": municipio.id
    }


# ========================================
# CATEGORIA (GRUPO > ASSUNTO > SUBASSUNTO)
# ========================================

@router.get("/grupos")
def listar_grupos(db: Session = Depends(get_db)):
    """Lista todos os grupos"""
    grupos = db.query(Grupo).filter(Grupo.ativo == True).order_by(Grupo.nome).all()
    return [{"id": g.id, "nome": g.nome} for g in grupos]


@router.get("/assuntos/{grupo_id}")
def listar_assuntos(grupo_id: int, db: Session = Depends(get_db)):
    """Lista assuntos de um grupo"""
    assuntos = (
        db.query(Assunto)
        .filter(Assunto.grupo_id == grupo_id, Assunto.ativo == True)
        .order_by(Assunto.nome)
        .all()
    )
    return [{"id": a.id, "nome": a.nome} for a in assuntos]


@router.get("/subassuntos/{assunto_id}")
def listar_subassuntos(assunto_id: int, db: Session = Depends(get_db)):
    """Lista subassuntos de um assunto"""
    subassuntos = (
        db.query(Subassunto)
        .filter(Subassunto.assunto_id == assunto_id, Subassunto.ativo == True)
        .order_by(Subassunto.nome)
        .all()
    )
    return [{"id": s.id, "nome": s.nome} for s in subassuntos]


@router.get("/categoria/search")
def buscar_categoria(
    q: str = Query("", min_length=1),
    db: Session = Depends(get_db),
):
    """Busca tipo LIKE em grupo, assunto e subassunto. Refina conforme digita."""
    termo = f"%{q.strip()}%"
    resultados = []

    # Grupos que batem
    grupos = (
        db.query(Grupo)
        .filter(Grupo.ativo == True, Grupo.nome.ilike(termo))
        .order_by(Grupo.nome)
        .all()
    )
    for g in grupos:
        resultados.append({
            "label": g.nome,
            "grupo_id": g.id,
            "assunto_id": None,
            "subassunto_id": None,
        })

    # Assuntos que batem (com grupo)
    assuntos = (
        db.query(Assunto)
        .join(Grupo)
        .filter(Assunto.ativo == True, Grupo.ativo == True, Assunto.nome.ilike(termo))
        .order_by(Grupo.nome, Assunto.nome)
        .all()
    )
    for a in assuntos:
        resultados.append({
            "label": f"{a.grupo.nome} > {a.nome}",
            "grupo_id": a.grupo_id,
            "assunto_id": a.id,
            "subassunto_id": None,
        })

    # Subassuntos que batem (com assunto e grupo)
    subassuntos = (
        db.query(Subassunto)
        .join(Assunto)
        .join(Grupo)
        .filter(
            Subassunto.ativo == True,
            Assunto.ativo == True,
            Grupo.ativo == True,
            Subassunto.nome.ilike(termo),
        )
        .order_by(Grupo.nome, Assunto.nome, Subassunto.nome)
        .all()
    )
    for s in subassuntos:
        resultados.append({
            "label": f"{s.assunto.grupo.nome} > {s.assunto.nome} > {s.nome}",
            "grupo_id": s.assunto.grupo_id,
            "assunto_id": s.assunto_id,
            "subassunto_id": s.id,
        })

    return resultados