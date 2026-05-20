"""Templates Jinja2 compartilhados (Starlette 1.0 + contexto do usuário)."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

from starlette.requests import Request
from starlette.templating import Jinja2Templates as _Jinja2Templates

from database import SessionLocal
from models import User

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

PERFIL_LABELS = {
    "master": "Master",
    "admin_municipal": "Admin Municipal",
    "gestor_estoque": "Gestor de Estoque",
    "gestor_protocolo": "Gestor de Protocolo",
    "gestor_geral": "Gestor Geral",
    "gestor_segem": "Gestor SEGEM",
    "operador": "Operador",
}


def enum_value(val) -> str:
    if val is None:
        return ""
    return val.value if hasattr(val, "value") else str(val)


def enum_label(val) -> str:
    return enum_value(val).replace("_", " ").capitalize()


def format_cpf(value) -> str:
    """Exibe CPF como 000.000.000-00 (aceita valor já mascarado ou só dígitos)."""
    if value is None:
        return ""
    digits = re.sub(r"\D", "", str(value))[:11]
    if len(digits) < 11:
        return digits
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def tempo_recebido(dt):
    """Formata datetime como 'Recebido há X dias/meses/anos'."""
    if not dt:
        return "-"
    agora = datetime.utcnow()
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    diff = agora - dt
    dias = diff.days
    if dias == 0:
        return "Recebido hoje"
    if dias == 1:
        return "Recebido há 1 dia"
    if dias < 30:
        return f"Recebido há {dias} dias"
    if dias < 365:
        meses = dias // 30
        return f"Recebido há {meses} {'mês' if meses == 1 else 'meses'}"
    anos = dias // 365
    return f"Recebido há {anos} {'ano' if anos == 1 else 'anos'}"


def get_user_display_name(request: Request) -> str:
    email = request.session.get("user")
    if not email:
        return ""
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        return u.nome if u else email
    finally:
        db.close()


def get_logged_user(request: Request):
    return request.session.get("user")


def get_meus_dados(request: Request):
    email = request.session.get("user")
    if not email:
        return None
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        if not u:
            return None
        municipio_nome = u.municipio.nome if u.municipio else ""
        orgao_nome = (u.orgao.sigla or u.orgao.nome) if u.orgao else ""
        unidade_nome = (u.unidade.sigla or u.unidade.nome) if u.unidade else ""
        perfil = u.perfil
        perfil_str = perfil.value if hasattr(perfil, "value") else str(perfil or "")
        status = u.status
        status_str = status.value if hasattr(status, "value") else str(status or "")
        return {
            "id": u.id,
            "nome": u.nome or "",
            "email": u.email or "",
            "perfil": perfil_str,
            "status": status_str,
            "municipio": municipio_nome,
            "orgao": orgao_nome,
            "unidade": unidade_nome,
        }
    finally:
        db.close()


def inject_user_context(request: Request) -> dict[str, Any]:
    email = request.session.get("user")
    nome = request.session.get("user_nome") or email or ""
    primeiro = nome.split()[0] if nome and nome.strip() else ""
    perfil = request.session.get("perfil") or ""

    hora = datetime.now().hour
    if hora < 12:
        saudacao = "Bom dia"
    elif hora < 18:
        saudacao = "Boa tarde"
    else:
        saudacao = "Boa noite"

    return {
        "current_user_email": email,
        "current_user_nome": nome,
        "current_user_primeiro_nome": primeiro,
        "current_user_id": request.session.get("user_id"),
        "current_user_perfil": perfil,
        "current_user_perfil_label": PERFIL_LABELS.get(perfil, perfil),
        "user_saudacao": saudacao,
        "is_logged_in": bool(email),
    }


class Jinja2Templates(_Jinja2Templates):
    def TemplateResponse(
        self,
        name_or_request: Request | str,
        context: dict[str, Any] | str | None = None,
        **kwargs: Any,
    ):
        if isinstance(name_or_request, str):
            template_name = name_or_request
            template_context = dict(context or {})
            request = template_context.pop("request", None)
            if request is None:
                raise ValueError(
                    "TemplateResponse legado exige 'request' no contexto."
                )
            return super().TemplateResponse(
                request,
                template_name,
                template_context or None,
                **kwargs,
            )
        return super().TemplateResponse(name_or_request, context, **kwargs)


templates = Jinja2Templates(directory=TEMPLATE_DIR)
templates.context_processors.append(inject_user_context)
templates.env.globals["get_logged_user"] = get_logged_user
templates.env.globals["get_user_display_name"] = get_user_display_name
templates.env.globals["get_meus_dados"] = get_meus_dados
templates.env.filters["tempo_recebido"] = tempo_recebido
templates.env.filters["enum_value"] = enum_value
templates.env.filters["enum_label"] = enum_label
templates.env.filters["format_cpf"] = format_cpf
