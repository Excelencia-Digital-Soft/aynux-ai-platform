from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, require_scopes

router = APIRouter()


@router.get("/protected")
async def protected_route(username: str = Depends(get_current_user)):
    """
    Ruta protegida que requiere autenticación
    """
    return {"message": f"Hola, {username}! Esta es una ruta protegida."}


@router.get("/admin", dependencies=[Depends(require_scopes(["admin"]))])
async def admin_route(username: str = Depends(get_current_user)):
    """
    Ruta de administrador que requiere el scope 'admin'
    """
    return {"message": f"Hola, administrador {username}!"}
