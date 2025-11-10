from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from database import Base, engine
from dependencies import sessions

# Routers
from routers import auth, dashboard, equipment, users, units, movements, logs, root, equipment_types

# Criação das tabelas
Base.metadata.create_all(bind=engine)

# Inicializa o app FastAPI
app = FastAPI()

# Configuração de templates e arquivos estáticos
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Função global que pega o usuário logado do cookie + dicionário sessions
def get_logged_user(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        return sessions[session_id]  # retorna o username
    return None

def get_user_for_template(request: Request):
    return get_logged_user(request)

# Torna acessível a função em todos os templates Jinja2
templates.env.globals["get_logged_user"] = get_logged_user

# 🔹 Exporte o templates para outros módulos
app.state.templates = templates

# Incluindo routers
app.include_router(root.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(equipment.router)
app.include_router(users.router)
app.include_router(units.router)
app.include_router(movements.router)
app.include_router(equipment_types.router)
app.include_router(logs.router)
