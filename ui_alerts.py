"""Respostas HTML padronizadas com alertas SIGEN (SweetAlert2)."""

from fastapi.responses import HTMLResponse

from templating import templates

_VALID_ICONS = frozenset({"error", "warning", "info", "success"})


def alert_back(message: str, icon: str = "error", status_code: int = 400) -> HTMLResponse:
    """Exibe modal SIGEN e retorna à página anterior (history.back)."""
    icon_key = icon if icon in _VALID_ICONS else "error"
    return templates.TemplateResponse(
        "includes/alert_back.html",
        {
            "message": (message or "").strip(),
            "icon": icon_key,
        },
        status_code=status_code,
    )
