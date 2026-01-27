from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from database import Base, engine
from dependencies import sessions

# Criação do app (somente uma vez)
app = FastAPI()

# Montagem do diretório static
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuração de templates
templates = Jinja2Templates(directory="templates")

# Função global para templates
def get_logged_user(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        return sessions[session_id]
    return None

templates.env.globals["get_logged_user"] = get_logged_user
app.state.templates = templates

# Criação das tabelas
Base.metadata.create_all(bind=engine)

# Routers
from routers import auth, dashboard, equipment, users, units, movements, logs, root, equipment_types, brands, states, products, stock, categories

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
app.include_router(logs.router)
