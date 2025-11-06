from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from dependencies import get_current_user

router = APIRouter(prefix="/units", tags=["Units"])

@router.get("/")
def list_units(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    return {"msg": "Lista de unidades"}
