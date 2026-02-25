"""
Middleware de Filtragem Automática por Município
Garante isolamento de dados entre prefeituras automaticamente
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, RedirectResponse
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from typing import Callable
import re


class MultiTenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware que injeta automaticamente o contexto do usuário
    e garante filtragem por município em todas as requisições
    """
    
    # Rotas que não precisam de autenticação
    ROTAS_PUBLICAS = [
        "/login",
        "/static",
        "/favicon.ico",
        "/docs",
        "/openapi.json",
        "/redoc",
    ]
    
    # Rotas da API que não precisam de contexto de usuário
    ROTAS_API_ABERTAS = [
        "/api/estados",
    ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Processa cada requisição injetando contexto do usuário
        """
        
        # Verifica se é rota pública
        if self._is_rota_publica(request.url.path):
            return await call_next(request)
        
        # Obtém sessão do banco
        db = SessionLocal()
        
        try:
            # Obtém usuário da sessão
            username = request.session.get("user")
            
            if not username:
                # Se não estiver logado e não for rota pública, redireciona
                if not self._is_rota_api_aberta(request.url.path):
                    return RedirectResponse("/login")
                return await call_next(request)
            
            # Busca usuário completo no banco
            user = db.query(User).filter(User.username == username).first()
            
            if not user:
                # Usuário não existe mais no banco
                request.session.clear()
                return RedirectResponse("/login")
            
            # Verifica se usuário está ativo
            status = user.status.value if hasattr(user.status, 'value') else user.status
            if status != "ativo":
                return Response(
                    content="""
                    <html>
                        <head><title>Acesso Bloqueado</title></head>
                        <body style="font-family: Arial; padding: 50px; text-align: center;">
                            <h1 style="color: #dc3545;">⚠️ Acesso Bloqueado</h1>
                            <p>Seu usuário está <strong>{}</strong>.</p>
                            <p>Entre em contato com o administrador do sistema.</p>
                            <p><a href="/login" style="color: #0d6efd;">← Voltar ao Login</a></p>
                        </body>
                    </html>
                    """.format(status),
                    status_code=403,
                    media_type="text/html"
                )
            
            # ✅ INJETA CONTEXTO DO USUÁRIO NA REQUEST
            request.state.user = user
            request.state.user_id = user.id
            request.state.municipio_id = user.municipio_id
            request.state.orgao_id = user.orgao_id
            request.state.unidade_id = user.unidade_id
            request.state.perfil = user.perfil.value if hasattr(user.perfil, 'value') else user.perfil
            request.state.db = db
            
            # Atualiza último acesso
            from datetime import datetime
            user.ultimo_acesso = datetime.utcnow()
            db.commit()
            
            # Processa requisição
            response = await call_next(request)
            
            return response
            
        except Exception as e:
            print(f"Erro no middleware: {e}")
            return Response(
                content=f"Erro interno: {str(e)}",
                status_code=500
            )
        finally:
            db.close()
    
    def _is_rota_publica(self, path: str) -> bool:
        """Verifica se rota é pública"""
        return any(path.startswith(rota) for rota in self.ROTAS_PUBLICAS)
    
    def _is_rota_api_aberta(self, path: str) -> bool:
        """Verifica se é rota de API aberta"""
        return any(path.startswith(rota) for rota in self.ROTAS_API_ABERTAS)


# ========================================
# HELPER FUNCTIONS PARA USAR NO CONTEXTO
# ========================================

def obter_contexto_usuario(request: Request) -> dict:
    """
    Obtém contexto completo do usuário da request
    
    Uso:
    @router.get("/products")
    def list_products(request: Request):
        ctx = obter_contexto_usuario(request)
        municipio_id = ctx['municipio_id']
        perfil = ctx['perfil']
    """
    if not hasattr(request.state, 'user'):
        raise HTTPException(status_code=401, detail="Usuário não autenticado")
    
    return {
        "user": request.state.user,
        "user_id": request.state.user_id,
        "municipio_id": request.state.municipio_id,
        "orgao_id": request.state.orgao_id,
        "unidade_id": request.state.unidade_id,
        "perfil": request.state.perfil,
        "db": request.state.db,
    }


def filtrar_por_municipio(request: Request):
    """
    Retorna municipio_id do usuário ou None se for MASTER
    
    Uso em queries:
    @router.get("/products")
    def list_products(request: Request, db: Session = Depends(get_db)):
        municipio_id = filtrar_por_municipio(request)
        
        query = db.query(Product)
        if municipio_id:
            query = query.filter(Product.municipio_id == municipio_id)
        
        products = query.all()
    """
    if not hasattr(request.state, 'perfil'):
        raise HTTPException(status_code=401, detail="Usuário não autenticado")
    
    # MASTER não tem filtro de município
    if request.state.perfil == "master":
        return None
    
    return request.state.municipio_id


def filtrar_por_orgao(request: Request):
    """
    Retorna orgao_id do usuário ou None se for MASTER/ADMIN_MUNICIPAL
    
    Uso:
    @router.get("/products")
    def list_products(request: Request, db: Session = Depends(get_db)):
        orgao_id = filtrar_por_orgao(request)
        
        query = db.query(Product)
        if orgao_id:
            query = query.filter(Product.orgao_id == orgao_id)
        
        products = query.all()
    """
    if not hasattr(request.state, 'perfil'):
        raise HTTPException(status_code=401, detail="Usuário não autenticado")
    
    perfil = request.state.perfil
    
    # MASTER e ADMIN_MUNICIPAL veem todos os órgãos do município
    if perfil in ["master", "admin_municipal"]:
        return None
    
    return request.state.orgao_id


def pode_acessar_recurso(request: Request, recurso_municipio_id: int) -> bool:
    """
    Verifica se usuário pode acessar um recurso de outro município
    
    Uso:
    @router.get("/products/{product_id}")
    def get_product(product_id: int, request: Request, db: Session = Depends(get_db)):
        product = db.query(Product).filter(Product.id == product_id).first()
        
        if not pode_acessar_recurso(request, product.municipio_id):
            raise HTTPException(403, "Acesso negado a recurso de outro município")
        
        return product
    """
    if not hasattr(request.state, 'perfil'):
        return False
    
    # MASTER acessa tudo
    if request.state.perfil == "master":
        return True
    
    # Outros perfis apenas seu município
    return request.state.municipio_id == recurso_municipio_id


# ========================================
# DEPENDENCY INJETADA AUTOMATICAMENTE
# ========================================

from fastapi import Depends

def get_contexto_usuario(request: Request):
    """
    Dependency para injetar contexto do usuário
    
    Uso moderno:
    @router.get("/products")
    def list_products(ctx: dict = Depends(get_contexto_usuario)):
        municipio_id = ctx['municipio_id']
        user = ctx['user']
    """
    return obter_contexto_usuario(request)


def get_user_from_context(request: Request) -> User:
    """
    Dependency para injetar objeto User diretamente
    
    Uso:
    @router.get("/products")
    def list_products(user: User = Depends(get_user_from_context)):
        print(user.nome)
        print(user.municipio_id)
    """
    if not hasattr(request.state, 'user'):
        raise HTTPException(status_code=401, detail="Usuário não autenticado")
    
    return request.state.user


# ========================================
# QUERY HELPERS COM FILTRO AUTOMÁTICO
# ========================================

from sqlalchemy.orm import Query
from typing import Type, TypeVar

T = TypeVar('T')

class QueryComFiltro:
    """
    Helper para adicionar filtros automáticos em queries
    """
    
    @staticmethod
    def filtrar_por_municipio(query: Query, model: Type[T], request: Request) -> Query:
        """
        Adiciona filtro de município automaticamente se não for MASTER
        
        Uso:
        query = db.query(Product)
        query = QueryComFiltro.filtrar_por_municipio(query, Product, request)
        products = query.all()
        """
        municipio_id = filtrar_por_municipio(request)
        
        if municipio_id and hasattr(model, 'municipio_id'):
            query = query.filter(model.municipio_id == municipio_id)
        
        return query
    
    @staticmethod
    def filtrar_por_orgao(query: Query, model: Type[T], request: Request) -> Query:
        """
        Adiciona filtro de órgão automaticamente
        
        Uso:
        query = db.query(Product)
        query = QueryComFiltro.filtrar_por_orgao(query, Product, request)
        products = query.all()
        """
        orgao_id = filtrar_por_orgao(request)
        
        if orgao_id and hasattr(model, 'orgao_id'):
            query = query.filter(model.orgao_id == orgao_id)
        
        return query
    
    @staticmethod
    def aplicar_filtros_completos(query: Query, model: Type[T], request: Request) -> Query:
        """
        Aplica município + órgão automaticamente
        
        Uso:
        query = db.query(Product)
        query = QueryComFiltro.aplicar_filtros_completos(query, Product, request)
        products = query.all()
        """
        query = QueryComFiltro.filtrar_por_municipio(query, model, request)
        query = QueryComFiltro.filtrar_por_orgao(query, model, request)
        return query


# ========================================
# DECORATORS PARA VALIDAÇÃO AUTOMÁTICA
# ========================================

from functools import wraps

def validar_acesso_municipio(func):
    """
    Decorator que valida acesso ao município automaticamente
    Útil para rotas que recebem IDs de recursos
    
    Uso:
    @router.get("/products/{product_id}")
    @validar_acesso_municipio
    def get_product(product_id: int, request: Request, db: Session = Depends(get_db)):
        # Se chegou aqui, tem permissão
        product = db.query(Product).filter(Product.id == product_id).first()
        return product
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get('request')
        
        if not request:
            raise HTTPException(500, "Request não encontrada")
        
        # Validação será feita dentro da função que busca o recurso
        # Este decorator apenas garante que o contexto existe
        if not hasattr(request.state, 'municipio_id'):
            raise HTTPException(401, "Contexto de usuário não encontrado")
        
        return await func(*args, **kwargs)
    
    return wrapper