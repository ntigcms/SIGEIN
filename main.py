from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware  # ✅ Import no topo
from middleware import MultiTenantMiddleware
from database import Base, engine
import os

# ========================================
# 1. CRIAR APP
# ========================================
app = FastAPI()

# ========================================
# 2. ADICIONAR MIDDLEWARES (ANTES DE TUDO)
# ========================================
SECRET_KEY = os.getenv("SECRET_KEY", "sua-chave-secreta-aqui-mude-em-producao")

# ✅ SessionMiddleware PRIMEIRO
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session",
    max_age=3600 * 24,
    same_site="lax",
    https_only=False
)

# ✅ MultiTenantMiddleware DEPOIS
#app.add_middleware(MultiTenantMiddleware)

# ========================================
# 3. STATIC FILES
# ========================================
app.mount("/static", StaticFiles(directory="static"), name="static")

# ========================================
# 4. TEMPLATES
# ========================================
templates = Jinja2Templates(directory="templates")

def get_logged_user(request: Request):
    return request.session.get("user")

templates.env.globals["get_logged_user"] = get_logged_user
app.state.templates = templates

# ========================================
# 5. DATABASE
# ========================================
Base.metadata.create_all(bind=engine)

# ========================================
# 6. ROUTERS (POR ÚLTIMO)
# ========================================
from routers import (
    auth, dashboard, users, units, movements, logs, root,
    equipment_types, brands, states, products, stock,
    categories, eprotocolo
)

app.include_router(root.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(units.router)
app.include_router(movements.router)
app.include_router(categories.router)
app.include_router(equipment_types.router)
app.include_router(products.router)
app.include_router(brands.router)
app.include_router(states.router)
app.include_router(stock.router)
app.include_router(eprotocolo.router)
app.include_router(logs.router)