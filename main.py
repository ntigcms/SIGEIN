from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from database import Base, engine


# Routers
from routers import auth, dashboard, equipment, users, units, movements, logs, root

# Criação das tabelas
Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Incluindo routers
app.include_router(root.router) 
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(equipment.router)
app.include_router(users.router)
app.include_router(units.router)
app.include_router(movements.router)
app.include_router(logs.router)
