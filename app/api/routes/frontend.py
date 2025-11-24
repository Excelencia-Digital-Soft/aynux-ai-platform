"""
Rutas para servir la interfaz web de testing del chatbot
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter(tags=["frontend"])

# Base path for static files
STATIC_DIR = Path(__file__).parent.parent.parent / "static"


@router.get("/", response_class=HTMLResponse)
async def serve_chat_interface():
    """
    Sirve la interfaz web principal del chat

    Returns:
        HTML response con la interfaz de chat
    """
    index_path = STATIC_DIR / "index.html"

    if not index_path.exists():
        return HTMLResponse(
            content="<h1>Chat interface not found</h1><p>Static files are missing. Please check your deployment.</p>",
            status_code=404,
        )

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    return HTMLResponse(content=content)


@router.get("/chat")
async def serve_chat_interface_alt():
    """
    Ruta alternativa para acceder a la interfaz de chat

    Returns:
        HTML response con la interfaz de chat
    """
    return await serve_chat_interface()
