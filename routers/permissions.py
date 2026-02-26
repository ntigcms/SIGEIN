"""
Sistema de Permissões e Decorators
Controla acesso granular por perfil de usuário
"""

from functools import wraps
from fastapi import HTTPException, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from database import get_db
from models import User
from typing import List, Optional, Callable
from dependencies import get_current_user


# ========================================
# ENUMS DE PERMISSÕES
# ========================================

class Permissao:
    """Constantes de permissões do sistema"""
    
    # Módulos
    ACESSAR_INVENTARIO = "acessar_inventario"
    ACESSAR_PROTOCOLO = "acessar_protocolo"
    GERENCIAR_USUARIOS = "gerenciar_usuarios"
    
    # Inventário
    CRIAR_PRODUTO = "criar_produto"
    EDITAR_PRODUTO = "editar_produto"
    EXCLUIR_PRODUTO = "excluir_produto"
    VISUALIZAR_ESTOQUE = "visualizar_estoque"
    MOVIMENTAR_ESTOQUE = "movimentar_estoque"
    GERAR_RELATORIO_ESTOQUE = "gerar_relatorio_estoque"
    
    # Protocolo
    CRIAR_PROCESSO = "criar_processo"
    TRAMITAR_PROCESSO = "tramitar_processo"
    ARQUIVAR_PROCESSO = "arquivar_processo"
    CRIAR_CIRCULAR = "criar_circular"
    VISUALIZAR_PROCESSO = "visualizar_processo"
    
    # Sistema
    ACESSAR_LOGS = "acessar_logs"
    ACESSAR_CONFIG = "acessar_config"
    ACESSAR_TODOS_MUNICIPIOS = "acessar_todos_municipios"


# ========================================
# MAPEAMENTO PERFIL → PERMISSÕES
# ========================================

PERMISSOES_POR_PERFIL = {
    "master": [
        # Acesso total
        Permissao.ACESSAR_INVENTARIO,
        Permissao.ACESSAR_PROTOCOLO,
        Permissao.GERENCIAR_USUARIOS,
        Permissao.CRIAR_PRODUTO,
        Permissao.EDITAR_PRODUTO,
        Permissao.EXCLUIR_PRODUTO,
        Permissao.VISUALIZAR_ESTOQUE,
        Permissao.MOVIMENTAR_ESTOQUE,
        Permissao.GERAR_RELATORIO_ESTOQUE,
        Permissao.CRIAR_PROCESSO,
        Permissao.TRAMITAR_PROCESSO,
        Permissao.ARQUIVAR_PROCESSO,
        Permissao.CRIAR_CIRCULAR,
        Permissao.VISUALIZAR_PROCESSO,
        Permissao.ACESSAR_LOGS,
        Permissao.ACESSAR_CONFIG,
        Permissao.ACESSAR_TODOS_MUNICIPIOS,
    ],
    
    "admin_municipal": [
        # Acesso total ao município
        Permissao.ACESSAR_INVENTARIO,
        Permissao.ACESSAR_PROTOCOLO,
        Permissao.GERENCIAR_USUARIOS,
        Permissao.CRIAR_PRODUTO,
        Permissao.EDITAR_PRODUTO,
        Permissao.EXCLUIR_PRODUTO,
        Permissao.VISUALIZAR_ESTOQUE,
        Permissao.MOVIMENTAR_ESTOQUE,
        Permissao.GERAR_RELATORIO_ESTOQUE,
        Permissao.CRIAR_PROCESSO,
        Permissao.TRAMITAR_PROCESSO,
        Permissao.ARQUIVAR_PROCESSO,
        Permissao.CRIAR_CIRCULAR,
        Permissao.VISUALIZAR_PROCESSO,
        Permissao.ACESSAR_LOGS,
    ],
    
    "gestor_estoque": [
        # Apenas inventário
        Permissao.ACESSAR_INVENTARIO,
        Permissao.CRIAR_PRODUTO,
        Permissao.EDITAR_PRODUTO,
        Permissao.EXCLUIR_PRODUTO,
        Permissao.VISUALIZAR_ESTOQUE,
        Permissao.MOVIMENTAR_ESTOQUE,
        Permissao.GERAR_RELATORIO_ESTOQUE,
    ],
    
    "gestor_protocolo": [
        # Apenas protocolo
        Permissao.ACESSAR_PROTOCOLO,
        Permissao.CRIAR_PROCESSO,
        Permissao.TRAMITAR_PROCESSO,
        Permissao.ARQUIVAR_PROCESSO,
        Permissao.CRIAR_CIRCULAR,
        Permissao.VISUALIZAR_PROCESSO,
    ],
    
    "gestor_geral": [
        # Inventário + Protocolo (sem gerenciar usuários)
        Permissao.ACESSAR_INVENTARIO,
        Permissao.ACESSAR_PROTOCOLO,
        Permissao.CRIAR_PRODUTO,
        Permissao.EDITAR_PRODUTO,
        Permissao.EXCLUIR_PRODUTO,
        Permissao.VISUALIZAR_ESTOQUE,
        Permissao.MOVIMENTAR_ESTOQUE,
        Permissao.GERAR_RELATORIO_ESTOQUE,
        Permissao.CRIAR_PROCESSO,
        Permissao.TRAMITAR_PROCESSO,
        Permissao.ARQUIVAR_PROCESSO,
        Permissao.CRIAR_CIRCULAR,
        Permissao.VISUALIZAR_PROCESSO,
    ],
    
    "operador": [
        # Acesso básico (apenas visualização e ações limitadas)
        Permissao.ACESSAR_INVENTARIO,
        Permissao.ACESSAR_PROTOCOLO,
        Permissao.VISUALIZAR_ESTOQUE,
        Permissao.VISUALIZAR_PROCESSO,
    ],
}


# ========================================
# HELPERS
# ========================================

def obter_usuario_atual(
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Obtém objeto User completo do usuário logado"""
    if not current_user:
        return None
    # current_user armazena o e-mail
    return db.query(User).filter(User.email == current_user).first()


def usuario_tem_permissao(user: User, permissao: str) -> bool:
    """Verifica se usuário tem uma permissão específica"""
    if not user:
        return False
    
    perfil = user.perfil
    permissoes = PERMISSOES_POR_PERFIL.get(perfil, [])
    return permissao in permissoes


def usuario_pode_acessar_municipio(user: User, municipio_id: int) -> bool:
    """Verifica se usuário pode acessar dados de um município"""
    if not user:
        return False
    
    perfil = user.perfil
    
    # MASTER acessa todos os municípios
    if perfil == "master":
        return True
    
    # Outros perfis apenas seu município
    return user.municipio_id == municipio_id


def usuario_pode_acessar_orgao(user: User, orgao_id: int) -> bool:
    """Verifica se usuário pode acessar dados de um órgão"""
    if not user:
        return False
    
    perfil = user.perfil
    
    # MASTER e ADMIN_MUNICIPAL acessam todos os órgãos do município
    if perfil in ["master", "admin_municipal"]:
        return True
    
    # Outros perfis apenas seu órgão
    return user.orgao_id == orgao_id


# ========================================
# DECORATORS
# ========================================

def requer_permissao(permissao: str):
    """
    Decorator para verificar se usuário tem permissão específica
    
    Uso:
    @router.get("/products/add")
    @requer_permissao(Permissao.CRIAR_PRODUTO)
    def criar_produto(...):
        ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Obtém request e db da função
            request = kwargs.get('request')
            db = kwargs.get('db')
            current_user = kwargs.get('current_user') or kwargs.get('user')
            
            if not current_user:
                return RedirectResponse("/login")
            
            # Obtém objeto User
            user_obj = db.query(User).filter(User.email == current_user).first()
            
            if not user_obj:
                return RedirectResponse("/login")
            
            # Verifica permissão
            if not usuario_tem_permissao(user_obj, permissao):
                return HTMLResponse(
                    f"""
                    <html>
                        <head><title>Acesso Negado</title></head>
                        <body style="font-family: Arial; padding: 50px; text-align: center;">
                            <h1 style="color: #dc3545;">🚫 Acesso Negado</h1>
                            <p>Você não tem permissão para acessar esta funcionalidade.</p>
                            <p><strong>Permissão necessária:</strong> {permissao}</p>
                            <p><a href="/" style="color: #0d6efd;">← Voltar ao Início</a></p>
                        </body>
                    </html>
                    """,
                    status_code=403
                )
            
            # Adiciona user_obj aos kwargs para a função poder usar
            kwargs['user_obj'] = user_obj
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def requer_perfil(*perfis_permitidos: str):
    """
    Decorator para verificar se usuário tem um dos perfis permitidos
    
    Uso:
    @router.get("/users")
    @requer_perfil("master", "admin_municipal")
    def listar_usuarios(...):
        ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get('request')
            db = kwargs.get('db')
            current_user = kwargs.get('current_user') or kwargs.get('user')
            
            if not current_user:
                return RedirectResponse("/login")
            
            user_obj = db.query(User).filter(User.email == current_user).first()
            
            if not user_obj:
                return RedirectResponse("/login")
            
            perfil_atual = user_obj.perfil
            
            if perfil_atual not in perfis_permitidos:
                return HTMLResponse(
                    f"""
                    <html>
                        <head><title>Acesso Negado</title></head>
                        <body style="font-family: Arial; padding: 50px; text-align: center;">
                            <h1 style="color: #dc3545;">🚫 Acesso Negado</h1>
                            <p>Seu perfil não tem permissão para acessar esta área.</p>
                            <p><strong>Perfil necessário:</strong> {', '.join(perfis_permitidos)}</p>
                            <p><strong>Seu perfil:</strong> {perfil_atual}</p>
                            <p><a href="/" style="color: #0d6efd;">← Voltar ao Início</a></p>
                        </body>
                    </html>
                    """,
                    status_code=403
                )
            
            kwargs['user_obj'] = user_obj
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def requer_mesmo_municipio():
    """
    Decorator para verificar se recurso pertence ao município do usuário
    
    Uso:
    @router.get("/products/edit/{product_id}")
    @requer_mesmo_municipio()
    def editar_produto(product_id: int, ...):
        ...
    
    NOTA: A função decorada deve aceitar um parâmetro chamado 'municipio_id'
    ou deve buscar o recurso e verificar o municipio_id manualmente.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db = kwargs.get('db')
            current_user = kwargs.get('current_user') or kwargs.get('user')
            
            if not current_user:
                return RedirectResponse("/login")
            
            user_obj = db.query(User).filter(User.email == current_user).first()
            
            if not user_obj:
                return RedirectResponse("/login")
            
            perfil = user_obj.perfil
            
            # MASTER pode acessar qualquer município
            if perfil == "master":
                kwargs['user_obj'] = user_obj
                return await func(*args, **kwargs)
            
            # Para outros perfis, verifica município
            municipio_id = kwargs.get('municipio_id')
            
            if municipio_id and municipio_id != user_obj.municipio_id:
                return HTMLResponse(
                    """
                    <html>
                        <head><title>Acesso Negado</title></head>
                        <body style="font-family: Arial; padding: 50px; text-align: center;">
                            <h1 style="color: #dc3545;">🚫 Acesso Negado</h1>
                            <p>Você não tem permissão para acessar recursos de outro município.</p>
                            <p><a href="/" style="color: #0d6efd;">← Voltar ao Início</a></p>
                        </body>
                    </html>
                    """,
                    status_code=403
                )
            
            kwargs['user_obj'] = user_obj
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# ========================================
# DEPENDENCY INJECTION
# ========================================

def UsuarioComPermissao(permissao: str):
    """
    Dependency para injetar usuário verificando permissão
    
    Uso:
    @router.get("/products/add")
    def criar_produto(
        user_obj: User = Depends(UsuarioComPermissao(Permissao.CRIAR_PRODUTO))
    ):
        # user_obj já está validado e tem a permissão
        ...
    """
    def dependency(
        current_user: str = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        if not current_user:
            raise HTTPException(status_code=401, detail="Não autenticado")
        
        user_obj = db.query(User).filter(User.email == current_user).first()
        
        if not user_obj:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        
        if not usuario_tem_permissao(user_obj, permissao):
            raise HTTPException(
                status_code=403,
                detail=f"Permissão necessária: {permissao}"
            )
        
        return user_obj
    
    return dependency


def UsuarioComPerfil(*perfis: str):
    """
    Dependency para injetar usuário verificando perfil
    
    Uso:
    @router.get("/users")
    def listar_usuarios(
        user_obj: User = Depends(UsuarioComPerfil("master", "admin_municipal"))
    ):
        ...
    """
    def dependency(
        current_user: str = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        if not current_user:
            raise HTTPException(status_code=401, detail="Não autenticado")
        
        user_obj = db.query(User).filter(User.email == current_user).first()
        
        if not user_obj:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        
        perfil_atual = user_obj.perfil
        
        if perfil_atual not in perfis:
            raise HTTPException(
                status_code=403,
                detail=f"Perfis permitidos: {', '.join(perfis)}"
            )
        
        return user_obj
    
    return dependency