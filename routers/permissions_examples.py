# EXEMPLOS DE USO DO SISTEMA DE PERMISSÕES

"""
Este arquivo mostra como usar os decorators e dependencies de permissão
nas rotas do sistema.
"""

from fastapi import APIRouter, Request, Depends
from templating import templates
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user
from permissions import (
    Permissao,
    requer_permissao,
    requer_perfil,
    requer_mesmo_municipio,
    UsuarioComPermissao,
    UsuarioComPerfil,
    usuario_tem_permissao
)
from models import User, Product

router = APIRouter(prefix="/products", tags=["Products"])
# EXEMPLO 1: Usando Decorator @requer_permissao
# ========================================

@router.get("/add")
@requer_permissao(Permissao.CRIAR_PRODUTO)
async def add_product_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
    user_obj: User = None  # Será injetado pelo decorator
):
    """
    Apenas usuários com permissão CRIAR_PRODUTO podem acessar
    
    Perfis permitidos: master, admin_municipal, gestor_estoque, gestor_geral
    Perfis negados: gestor_protocolo, operador
    """
    # user_obj já vem validado do decorator
    return {"message": f"Olá {user_obj.nome}, você pode criar produtos!"}


# ========================================
# EXEMPLO 2: Usando Decorator @requer_perfil
# ========================================

@router.get("/relatorio-geral")
@requer_perfil("master", "admin_municipal")
async def relatorio_geral(
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
    user_obj: User = None  # Será injetado pelo decorator
):
    """
    Apenas MASTER e ADMIN_MUNICIPAL podem acessar
    """
    return {"message": "Relatório disponível apenas para gestores municipais"}


# ========================================
# EXEMPLO 3: Usando Dependency UsuarioComPermissao
# ========================================

@router.post("/")
def create_product(
    request: Request,
    db: Session = Depends(get_db),
    user_obj: User = Depends(UsuarioComPermissao(Permissao.CRIAR_PRODUTO))
):
    """
    Usa dependency injection - mais limpo e moderno
    
    user_obj já vem validado com a permissão
    Se não tiver permissão, HTTPException 403 é lançada automaticamente
    """
    # Código de criação do produto
    product = Product(
        name="Novo Produto",
        municipio_id=user_obj.municipio_id,  # Automaticamente do usuário
        orgao_id=user_obj.orgao_id,
        created_by=user_obj.id
    )
    db.add(product)
    db.commit()
    
    return {"message": "Produto criado com sucesso"}


# ========================================
# EXEMPLO 4: Usando Dependency UsuarioComPerfil
# ========================================

@router.get("/admin/settings")
def admin_settings(
    request: Request,
    user_obj: User = Depends(UsuarioComPerfil("master", "admin_municipal"))
):
    """
    Apenas perfis específicos podem acessar
    """
    return {"message": f"Configurações do município {user_obj.municipio.nome}"}


# ========================================
# EXEMPLO 5: Verificação Manual de Permissão
# ========================================

@router.get("/{product_id}")
def get_product(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Verifica permissão manualmente quando precisa de lógica condicional
    """
    user_obj = db.query(User).filter(User.email == current_user).first()
    
    product = db.query(Product).filter(Product.id == product_id).first()
    
    # Verifica se usuário pode visualizar o produto
    if not usuario_tem_permissao(user_obj, Permissao.VISUALIZAR_ESTOQUE):
        return {"error": "Sem permissão para visualizar estoque"}
    
    # Verifica se produto é do mesmo município (exceto MASTER)
    perfil = user_obj.perfil
    if perfil != "master" and product.municipio_id != user_obj.municipio_id:
        return {"error": "Produto de outro município"}
    
    return {"product": product}


# ========================================
# EXEMPLO 6: Combinando Múltiplas Verificações
# ========================================

@router.delete("/{product_id}")
@requer_permissao(Permissao.EXCLUIR_PRODUTO)
@requer_mesmo_municipio()
async def delete_product(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
    user_obj: User = None
):
    """
    Combina dois decorators:
    1. Verifica se tem permissão de excluir
    2. Verifica se o produto é do mesmo município
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    
    # Verifica município (se não for MASTER)
    perfil = user_obj.perfil
    if perfil != "master" and product.municipio_id != user_obj.municipio_id:
        return {"error": "Não pode excluir produto de outro município"}
    
    db.delete(product)
    db.commit()
    
    return {"message": "Produto excluído com sucesso"}


# ========================================
# EXEMPLO 7: Verificação Condicional por Perfil
# ========================================

@router.get("/")
def list_products(
    request: Request,
    db: Session = Depends(get_db),
    user_obj: User = Depends(UsuarioComPermissao(Permissao.VISUALIZAR_ESTOQUE))
):
    """
    Lista produtos com filtro automático por município
    """
    perfil = user_obj.perfil
    
    if perfil == "master":
        # MASTER vê todos os produtos de todos os municípios
        products = db.query(Product).all()
    
    elif perfil == "admin_municipal":
        # ADMIN vê todos os produtos do município
        products = db.query(Product).filter(
            Product.municipio_id == user_obj.municipio_id
        ).all()
    
    else:
        # Outros perfis veem apenas do seu órgão
        products = db.query(Product).filter(
            Product.municipio_id == user_obj.municipio_id,
            Product.orgao_id == user_obj.orgao_id
        ).all()
    
    return {"products": products}


# ========================================
# EXEMPLO 8: Permissões Dinâmicas em Templates
# ========================================

@router.get("/dashboard")
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Passa permissões para o template para mostrar/ocultar botões
    """
    user_obj = db.query(User).filter(User.email == current_user).first()
    
    # Cria dicionário de permissões para o template
    permissoes = {
        "pode_criar": usuario_tem_permissao(user_obj, Permissao.CRIAR_PRODUTO),
        "pode_editar": usuario_tem_permissao(user_obj, Permissao.EDITAR_PRODUTO),
        "pode_excluir": usuario_tem_permissao(user_obj, Permissao.EXCLUIR_PRODUTO),
        "pode_gerar_relatorio": usuario_tem_permissao(user_obj, Permissao.GERAR_RELATORIO_ESTOQUE),
    }
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user_obj,
            "permissoes": permissoes
        }
    )


# ========================================
# RESUMO DE BOAS PRÁTICAS
# ========================================

"""
? Use @requer_permissao() para verificações de permissões específicas
? Use @requer_perfil() para verificações de perfis
? Use UsuarioComPermissao() para dependency injection moderna
? Use UsuarioComPerfil() para dependency com perfis
? Use usuario_tem_permissao() para verificações manuais/condicionais
? Sempre filtre dados por município (exceto perfil MASTER)
? Passe permissões para templates para controle de UI
? Combine múltiplos decorators quando necessário

? Não confie apenas no frontend - SEMPRE valide no backend
? Não hardcode perfis em strings - use a classe Permissao
? Não esqueça de filtrar por município em consultas ao banco
"""