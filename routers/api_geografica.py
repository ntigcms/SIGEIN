from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Estado, Municipio, Orgao, Unidade

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