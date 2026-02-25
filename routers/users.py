from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_302_FOUND
from database import get_db
from dependencies import get_current_user, registrar_log
from models import User, Municipio, Orgao, Unidade
from typing import Optional
import re
import hashlib

router = APIRouter(prefix="/users", tags=["Users"])
templates = Jinja2Templates(directory="templates")


# ========================================
# HELPERS
# ========================================

def validar_cpf(cpf: str) -> bool:
    """Valida CPF brasileiro"""
    cpf = re.sub(r'\D', '', cpf)
    
    if len(cpf) != 11:
        return False
    
    if cpf == cpf[0] * 11:
        return False
    
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    
    if int(cpf[9]) != digito1:
        return False
    
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    
    if int(cpf[10]) != digito2:
        return False
    
    return True


def hash_senha(senha: str) -> str:
    """Cria hash SHA256 da senha (em produção use bcrypt)"""
    return hashlib.sha256(senha.encode()).hexdigest()


def limpar_cpf(cpf: str) -> str:
    """Remove formatação do CPF"""
    return re.sub(r'\D', '', cpf)


# ========================================
# LISTAR USUÁRIOS
# ========================================

@router.get("/")
def list_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse("/login")

    user_obj = db.query(User).filter(User.email == current_user).first()

    if not user_obj:
        return RedirectResponse("/login")

    perfil = user_obj.perfil

    if perfil == "master":
        users = db.query(User).order_by(User.nome).all()

    elif perfil == "admin_municipal":
        users = (
            db.query(User)
            .filter(User.municipio_id == user_obj.municipio_id)
            .order_by(User.nome)
            .all()
        )
    else:
        return HTMLResponse(
            "<h2>Acesso Negado</h2><p>Você não tem permissão para gerenciar usuários.</p>",
            status_code=403
        )

    return templates.TemplateResponse(
        "users_list.html",
        {
            "request": request,
            "users": users,
            "user": current_user,
            "user_perfil": perfil
        }
    )



# ========================================
# FORMULÁRIO DE CADASTRO
# ========================================

@router.get("/add")
def add_user_form(
    request: Request,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse("/login")

    user_obj = db.query(User).filter(User.email == current_user).first()

    if user_obj.perfil not in ["master", "admin_municipal"]:
        return HTMLResponse("Acesso Negado", status_code=403)

    return templates.TemplateResponse(
        "user_form.html",
        {
            "request": request,
            "user": None,
            "action": "add",
            "current_user": current_user
        }
    )


# ========================================
# INSERÇÃO NO BANCO
# ========================================

@router.post("/add")
def add_user(
    request: Request,
    nome: str = Form(...),
    cpf: str = Form(...),
    email: str = Form(...),
    municipio_id: int = Form(...),
    orgao_id: int = Form(...),
    unidade_id: int = Form(...),
    perfil: str = Form(...),
    status: str = Form(...),
    senha: str = Form(...),
    confirmar_senha: str = Form(...),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse("/login")

    user_obj = db.query(User).filter(User.email == current_user).first()

    if user_obj.perfil not in ["master", "admin_municipal"]:
        raise HTTPException(status_code=403, detail="Sem permissão")

    cpf_limpo = limpar_cpf(cpf)

    if not validar_cpf(cpf_limpo):
        return HTMLResponse("<script>alert('CPF inválido!'); window.history.back();</script>", status_code=400)

    if senha != confirmar_senha:
        return HTMLResponse("<script>alert('As senhas não coincidem!'); window.history.back();</script>", status_code=400)

    if len(senha) < 6:
        return HTMLResponse("<script>alert('A senha deve ter no mínimo 6 caracteres!'); window.history.back();</script>", status_code=400)

    if db.query(User).filter(User.cpf == cpf_limpo).first():
        return HTMLResponse("<script>alert('CPF já cadastrado!'); window.history.back();</script>", status_code=400)

    if db.query(User).filter(User.email == email).first():
        return HTMLResponse("<script>alert('E-mail já cadastrado!'); window.history.back();</script>", status_code=400)

    if user_obj.perfil == "admin_municipal" and municipio_id != user_obj.municipio_id:
        raise HTTPException(status_code=403, detail="Você só pode criar usuários do seu município")

    if perfil == "master" and user_obj.perfil != "master":
        raise HTTPException(status_code=403, detail="Apenas MASTER pode criar outros usuários MASTER")

    novo_usuario = User(
        nome=nome,
        cpf=cpf_limpo,
        email=email,
        password=hash_senha(senha),
        municipio_id=municipio_id,
        orgao_id=orgao_id,
        unidade_id=unidade_id,
        perfil=perfil,
        status=status,
        created_by=user_obj.id
)

    db.add(novo_usuario)
    db.commit()

    registrar_log(
        db,
        usuario=current_user,
        acao=f"Cadastrou usuário {nome} (CPF: {cpf_limpo}, Perfil: {perfil})",
        ip=request.client.host
    )

    return RedirectResponse("/users", status_code=HTTP_302_FOUND)


# ========================================
# FORMULÁRIO DE EDIÇÃO
# ========================================

@router.get("/edit/{user_id}")
def edit_user_form(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse("/login")
    
    user_obj = db.query(User).filter(User.email == current_user).first()
    
    # ✅ Verifica permissão
    if str(user_obj.perfil) not in ["master", "admin_municipal"]:
        return HTMLResponse("Acesso Negado", status_code=403)
    
    # ✅ Busca usuário a editar
    user_to_edit = db.query(User).filter(User.id == user_id).first()
    if not user_to_edit:
        return HTMLResponse("Usuário não encontrado", status_code=404)
    
    # ✅ ADMIN_MUNICIPAL só pode editar usuários do seu município
    if user_obj.perfil.value == "admin_municipal":
        if user_to_edit.municipio_id != user_obj.municipio_id:
            return HTMLResponse("Você só pode editar usuários do seu município", status_code=403)
    
    # ✅ Ninguém (exceto MASTER) pode editar outro MASTER
    if user_to_edit.perfil.value == "master" and user_obj.perfil.value != "master":
        return HTMLResponse("Apenas MASTER pode editar outros MASTER", status_code=403)
    
    return templates.TemplateResponse(
        "user_form.html",
        {
            "request": request,
            "user": user_to_edit,
            "action": "edit",
            "current_user": current_user
        }
    )


# ========================================
# ATUALIZAÇÃO DO USUÁRIO
# ========================================

@router.post("/edit/{user_id}")
def edit_user(
    request: Request,
    user_id: int,
    nome: str = Form(...),
    cpf: str = Form(...),
    email: str = Form(...),
    municipio_id: int = Form(...),
    orgao_id: int = Form(...),
    unidade_id: int = Form(...),
    perfil: str = Form(...),
    status: str = Form(...),
    senha: str = Form(""),
    confirmar_senha: str = Form(""),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse("/login")
    
    user_obj = db.query(User).filter(User.email == current_user).first()
    
    # ✅ Verifica permissão
    if str(user_obj.perfil) not in ["master", "admin_municipal"]:
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    # ✅ Busca usuário
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    # ✅ Validações
    cpf_limpo = limpar_cpf(cpf)
    
    if not validar_cpf(cpf_limpo):
        return HTMLResponse(
            "<script>alert('CPF inválido!'); window.history.back();</script>",
            status_code=400
        )
    
    # ✅ Verifica se CPF já existe (exceto o próprio usuário)
    cpf_existe = db.query(User).filter(
        User.cpf == cpf_limpo,
        User.id != user_id
    ).first()
    if cpf_existe:
        return HTMLResponse(
            "<script>alert('CPF já cadastrado por outro usuário!'); window.history.back();</script>",
            status_code=400
        )
    
    # ✅ Verifica se email já existe (exceto o próprio usuário)
    email_existe = db.query(User).filter(
        User.email == email,
        User.id != user_id
    ).first()
    if email_existe:
        return HTMLResponse(
            "<script>alert('E-mail já cadastrado por outro usuário!'); window.history.back();</script>",
            status_code=400
        )
    
    # ✅ Valida senha (se fornecida)
    if senha:
        if senha != confirmar_senha:
            return HTMLResponse(
                "<script>alert('As senhas não coincidem!'); window.history.back();</script>",
                status_code=400
            )
        if len(senha) < 6:
            return HTMLResponse(
                "<script>alert('A senha deve ter no mínimo 6 caracteres!'); window.history.back();</script>",
                status_code=400
            )
    
    # ✅ ATUALIZA CAMPOS
    user.nome = nome
    user.cpf = cpf_limpo
    user.email = email
    user.municipio_id = municipio_id
    user.orgao_id = orgao_id
    user.unidade_id = unidade_id
    user.perfil = perfil
    user.status = status
    user.email = email.split('@')[0]
    
    # ✅ Atualiza senha apenas se fornecida
    if senha:
        user.password = hash_senha(senha)
    
    db.commit()
    
    # ✅ LOG
    registrar_log(
        db,
        usuario=current_user,
        acao=f"Editou usuário {nome} (ID: {user_id})",
        ip=request.client.host
    )
    
    return RedirectResponse("/users", status_code=HTTP_302_FOUND)


# ========================================
# EXCLUIR USUÁRIO
# ========================================

@router.post("/delete/{user_id}")
def delete_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    if not current_user:
        return JSONResponse({"success": False, "message": "Não autenticado"})

    user_obj = db.query(User).filter(User.email == current_user).first()

    if user_obj.perfil not in ["master", "admin_municipal"]:
        return JSONResponse({"success": False, "message": "Sem permissão"})

    user_to_delete = db.query(User).filter(User.id == user_id).first()

    if not user_to_delete:
        return JSONResponse({"success": False, "message": "Usuário não encontrado"})

    if user_to_delete.id == user_obj.id:
        return JSONResponse({"success": False, "message": "Você não pode excluir a si mesmo"})

    if user_to_delete.perfil == "master" and user_obj.perfil != "master":
        return JSONResponse({"success": False, "message": "Apenas MASTER pode excluir outro MASTER"})

    if user_obj.perfil == "admin_municipal" and user_to_delete.municipio_id != user_obj.municipio_id:
        return JSONResponse({"success": False, "message": "Você só pode excluir usuários do seu município"})

    db.delete(user_to_delete)
    db.commit()

    registrar_log(
        db,
        usuario=current_user,
        acao=f"Excluiu usuário {user_to_delete.nome} (ID: {user_id})",
        ip=request.client.host
    )

    return JSONResponse({"success": True, "message": "Usuário excluído com sucesso"})