# EXEMPLOS DE USO DO MIDDLEWARE DE MULTI-TENANCY

"""
Este arquivo mostra como usar o middleware e os helpers
de filtragem automática por município nas rotas.
"""

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from database import get_db
from middleware import (
    obter_contexto_usuario,
    filtrar_por_municipio,
    filtrar_por_orgao,
    pode_acessar_recurso,
    get_contexto_usuario,
    get_user_from_context,
    QueryComFiltro,
    validar_acesso_municipio
)
from models import Product, Stock, Item, User

router = APIRouter(prefix="/products", tags=["Products"])


# ========================================
# EXEMPLO 1: Listagem com Filtro Automático por Município
# ========================================

@router.get("/")
def list_products(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Lista produtos automaticamente filtrados por município
    
    - MASTER: vê todos os produtos de todos os municípios
    - ADMIN_MUNICIPAL: vê todos do seu município
    - Outros: veem apenas do seu órgão
    """
    
    # Método 1: Filtro manual
    municipio_id = filtrar_por_municipio(request)
    orgao_id = filtrar_por_orgao(request)
    
    query = db.query(Product)
    
    if municipio_id:
        query = query.filter(Product.municipio_id == municipio_id)
    
    if orgao_id:
        query = query.filter(Product.orgao_id == orgao_id)
    
    products = query.all()
    
    return {"products": products, "total": len(products)}


# ========================================
# EXEMPLO 2: Usando QueryComFiltro (Mais Limpo)
# ========================================

@router.get("/v2")
def list_products_v2(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Mesmo resultado do exemplo 1, mas com helper
    """
    
    query = db.query(Product)
    query = QueryComFiltro.aplicar_filtros_completos(query, Product, request)
    products = query.all()
    
    return {"products": products, "total": len(products)}


# ========================================
# EXEMPLO 3: Usando Dependency de Contexto
# ========================================

@router.get("/v3")
def list_products_v3(
    ctx: dict = Depends(get_contexto_usuario),
    db: Session = Depends(get_db)
):
    """
    Acessa contexto completo do usuário via dependency
    """
    
    municipio_id = ctx['municipio_id']
    orgao_id = ctx['orgao_id']
    perfil = ctx['perfil']
    user = ctx['user']
    
    query = db.query(Product)
    
    # MASTER não tem filtro
    if perfil == "master":
        products = query.all()
    
    # ADMIN_MUNICIPAL vê todo o município
    elif perfil == "admin_municipal":
        products = query.filter(Product.municipio_id == municipio_id).all()
    
    # Outros veem apenas seu órgão
    else:
        products = query.filter(
            Product.municipio_id == municipio_id,
            Product.orgao_id == orgao_id
        ).all()
    
    return {
        "products": products,
        "user": user.nome,
        "municipio": user.municipio.nome
    }


# ========================================
# EXEMPLO 4: Usando User Direto
# ========================================

@router.get("/v4")
def list_products_v4(
    user: User = Depends(get_user_from_context),
    db: Session = Depends(get_db)
):
    """
    Injeta objeto User diretamente
    """
    
    perfil = user.perfil.value if hasattr(user.perfil, 'value') else user.perfil
    
    query = db.query(Product)
    
    if perfil != "master":
        query = query.filter(Product.municipio_id == user.municipio_id)
    
    if perfil not in ["master", "admin_municipal"]:
        query = query.filter(Product.orgao_id == user.orgao_id)
    
    products = query.all()
    
    return {
        "products": products,
        "usuario": user.nome,
        "perfil": perfil
    }


# ========================================
# EXEMPLO 5: Validação de Acesso a Recurso Específico
# ========================================

@router.get("/{product_id}")
def get_product(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Obtém produto validando se usuário pode acessá-lo
    """
    
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        return {"error": "Produto não encontrado"}
    
    # ✅ Valida se usuário pode acessar este produto
    if not pode_acessar_recurso(request, product.municipio_id):
        return {"error": "Você não tem permissão para acessar produtos de outro município"}
    
    return {"product": product}


# ========================================
# EXEMPLO 6: Criação com Campos Automáticos
# ========================================

@router.post("/")
def create_product(
    request: Request,
    name: str,
    type_id: int,
    brand_id: int,
    user: User = Depends(get_user_from_context),
    db: Session = Depends(get_db)
):
    """
    Cria produto preenchendo automaticamente município/órgão do usuário
    """
    
    # ✅ Campos preenchidos automaticamente do contexto
    product = Product(
        name=name,
        type_id=type_id,
        brand_id=brand_id,
        municipio_id=user.municipio_id,  # ✅ Automático
        orgao_id=user.orgao_id,          # ✅ Automático
        created_by=user.id                # ✅ Automático
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return {
        "message": "Produto criado com sucesso",
        "product_id": product.id,
        "municipio": user.municipio.nome
    }


# ========================================
# EXEMPLO 7: Estatísticas por Município
# ========================================

@router.get("/stats")
def product_stats(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Retorna estatísticas filtradas automaticamente
    """
    
    ctx = obter_contexto_usuario(request)
    perfil = ctx['perfil']
    municipio_id = ctx['municipio_id']
    orgao_id = ctx['orgao_id']
    
    # Base query
    query_products = db.query(Product)
    query_items = db.query(Item)
    query_stocks = db.query(Stock)
    
    # Aplica filtros
    if perfil != "master":
        query_products = query_products.filter(Product.municipio_id == municipio_id)
        query_items = query_items.filter(Item.municipio_id == municipio_id)
        query_stocks = query_stocks.filter(Stock.municipio_id == municipio_id)
    
    if perfil not in ["master", "admin_municipal"]:
        query_products = query_products.filter(Product.orgao_id == orgao_id)
        query_items = query_items.filter(Item.orgao_id == orgao_id)
        query_stocks = query_stocks.filter(Stock.orgao_id == orgao_id)
    
    stats = {
        "total_produtos": query_products.count(),
        "total_items": query_items.count(),
        "total_estoque": query_stocks.count(),
        "perfil": perfil,
        "municipio": ctx['user'].municipio.nome if perfil != "master" else "Todos"
    }
    
    return stats


# ========================================
# EXEMPLO 8: Relatório Multi-Município (Apenas MASTER)
# ========================================

@router.get("/relatorio-geral")
def relatorio_geral(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Relatório que só MASTER pode ver com dados de todos os municípios
    """
    
    perfil = request.state.perfil
    
    if perfil != "master":
        return {
            "error": "Apenas MASTER pode acessar relatório geral",
            "seu_perfil": perfil
        }
    
    # MASTER vê tudo sem filtros
    from sqlalchemy import func
    
    relatorio = db.query(
        Product.municipio_id,
        func.count(Product.id).label('total_produtos')
    ).group_by(Product.municipio_id).all()
    
    return {
        "relatorio": [
            {"municipio_id": r.municipio_id, "total": r.total_produtos}
            for r in relatorio
        ]
    }


# ========================================
# EXEMPLO 9: Edição com Validação de Município
# ========================================

@router.put("/{product_id}")
def update_product(
    product_id: int,
    request: Request,
    name: str,
    db: Session = Depends(get_db)
):
    """
    Edita produto validando acesso ao município
    """
    
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        return {"error": "Produto não encontrado"}
    
    # ✅ Valida acesso
    if not pode_acessar_recurso(request, product.municipio_id):
        return {
            "error": "Você não pode editar produtos de outro município",
            "seu_municipio": request.state.user.municipio.nome,
            "municipio_do_produto": product.municipio.nome
        }
    
    # Atualiza
    product.name = name
    db.commit()
    
    return {"message": "Produto atualizado com sucesso"}


# ========================================
# EXEMPLO 10: Dashboard com Contexto Completo
# ========================================

@router.get("/dashboard")
def dashboard(
    user: User = Depends(get_user_from_context),
    db: Session = Depends(get_db)
):
    """
    Dashboard personalizado por perfil e município
    """
    
    perfil = user.perfil.value if hasattr(user.perfil, 'value') else user.perfil
    
    # Dados básicos do usuário
    info = {
        "usuario": user.nome,
        "perfil": perfil,
        "municipio": user.municipio.nome,
        "orgao": user.orgao.nome if user.orgao else None,
        "unidade": user.unidade.nome if user.unidade else None,
    }
    
    # Estatísticas baseadas no perfil
    if perfil == "master":
        info["escopo"] = "Todos os municípios"
        info["total_produtos"] = db.query(Product).count()
    
    elif perfil == "admin_municipal":
        info["escopo"] = f"Município de {user.municipio.nome}"
        info["total_produtos"] = db.query(Product).filter(
            Product.municipio_id == user.municipio_id
        ).count()
    
    else:
        info["escopo"] = f"Órgão {user.orgao.nome}"
        info["total_produtos"] = db.query(Product).filter(
            Product.municipio_id == user.municipio_id,
            Product.orgao_id == user.orgao_id
        ).count()
    
    return info


# ========================================
# CONFIGURAÇÃO NO MAIN.PY
# ========================================

"""
Para ativar o middleware, adicione no main.py:

from middleware import MultiTenantMiddleware

app = FastAPI()

# ✅ Adicione o middleware
app.add_middleware(MultiTenantMiddleware)

# ... resto da configuração
"""


# ========================================
# RESUMO DE BOAS PRÁTICAS
# ========================================

"""
✅ SEMPRE use filtrar_por_municipio() em queries de listagem
✅ SEMPRE use pode_acessar_recurso() ao acessar recurso específico
✅ SEMPRE preencha municipio_id e orgao_id automaticamente do contexto
✅ Use QueryComFiltro para código mais limpo
✅ Use get_user_from_context() para injetar User diretamente
✅ Confie no middleware - ele já valida autenticação e status

❌ NÃO hardcode municipio_id nas queries
❌ NÃO confie no frontend - SEMPRE valide no backend
❌ NÃO permita edição cross-município (exceto MASTER)
❌ NÃO esqueça de filtrar em relatórios e estatísticas
"""