"""
Middleware de auditoria: registra requisições mutáveis não cobertas por registrar_log explícito.
"""

import contextvars
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from database import SessionLocal
from dependencies import registrar_log, audit_was_logged

_audit_skip_paths = (
    "/static",
    "/login",
    "/logout",
    "/logs",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
)

_audit_skip_prefixes = (
    "/logs/export",
)


def _should_audit(path: str, method: str) -> bool:
    if any(path.startswith(p) for p in _audit_skip_paths):
        return False
    if any(path.startswith(p) for p in _audit_skip_prefixes):
        return False
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return True
    if method == "GET" and "/delete/" in path:
        return True
    return False


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        token = audit_was_logged.set(False)
        response = await call_next(request)

        path = request.url.path
        method = request.method.upper()

        if _should_audit(path, method) and not audit_was_logged.get():
            user = request.session.get("user") if hasattr(request, "session") else None
            if user:
                status = response.status_code
                acao = f"[{method}] {path}"
                if status >= 400:
                    acao += f" (HTTP {status})"
                db = SessionLocal()
                try:
                    registrar_log(
                        db,
                        usuario=user,
                        acao=acao,
                        request=request,
                        tipo="sistema",
                    )
                except Exception:
                    db.rollback()
                finally:
                    db.close()

        audit_was_logged.reset(token)
        return response
