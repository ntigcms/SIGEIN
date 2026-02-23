from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/eprotocolo", tags=["E-Protocolo"])
templates = Jinja2Templates(directory="templates")


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
    
    return templates.TemplateResponse(
        "eprotocolo/eprotocolo_dashboard.html",
        {
            "request": request,
            "user": user
        }
    )


# ========================================
# MÓDULO: PROCESSOS
# ========================================
@router.get("/processos/criar")
def processos_criar(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/processos/criar.html", {"request": request, "user": user})


@router.get("/processos/caixa")
def processos_caixa(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/processos/caixa.html", {"request": request, "user": user})


@router.get("/processos/consulta")
def processos_consulta(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("eprotocolo/processos/consulta.html", {"request": request, "user": user})


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