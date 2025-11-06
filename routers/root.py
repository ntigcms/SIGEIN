# routers/root.py
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()

@router.get("/")
def root():
    # Redireciona para login
    return RedirectResponse(url="/login")
