from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from dependencies import get_current_user

router = APIRouter(tags=["Dashboard"])
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard")
def dashboard(request: Request, current_user: str = Depends(get_current_user)):
    context = {"request": request, "user": current_user}
    return templates.TemplateResponse("dashboard.html", context)
