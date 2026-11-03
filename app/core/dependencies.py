from collections.abc import Generator
from typing import Annotated
from fastapi import Depends, Query
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session
from .config import get_settings
from .database import SessionLocal
from .exceptions import NoAutenticado, Prohibido
from ..models.usuario import RolUsuario, Usuario

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Generator[Session, None, None]:
    """Generador que provee una sesión de base de datos por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


SessionDep = Annotated[Session, Depends(get_db)]


class Paginacion:
    """Parámetros reutilizables de paginación."""
    def __init__(
        self,
        skip: int = Query(default=0, ge=0, description="Registros a omitir"),
        limit: int = Query(default=10, ge=1, le=100, description="Límite de registros por página (máx. 100)")
    ):
        self.skip = skip
        self.limit = limit


PaginacionDep = Annotated[Paginacion, Depends(Paginacion)]


def get_current_user(
    db: SessionDep,
    token: Annotated[str, Depends(oauth2_scheme)]
) -> Usuario:
    """
    Obtiene y valida el usuario autenticado a partir del token JWT:
    - Valida firma, expiración y claim type=='access'.
    - Consulta el usuario en la BD en cada petición (A7).
    - Valida que el usuario esté activo.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
    except jwt.InvalidTokenError:
        raise NoAutenticado("Token inválido o vencido")

    # A5: Validar que sea un access token
    if payload.get("type") != "access":
        raise NoAutenticado("Tipo de token inválido")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise NoAutenticado("Token no contiene identificador de usuario")

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise NoAutenticado("Identificador de usuario inválido")

    usuario = db.get(Usuario, user_id)
    if not usuario:
        raise NoAutenticado("Usuario no encontrado")

    # A7: Si el usuario fue desactivado, su token deja de servir
    if not usuario.activo:
        raise Prohibido("Usuario inactivo")

    return usuario


CurrentUser = Annotated[Usuario, Depends(get_current_user)]


def requiere_rol(*roles: RolUsuario):
    """Dependencia parametrizable que valida que el usuario pertenezca a uno de los roles dados."""
    def verificar(usuario: CurrentUser) -> Usuario:
        if usuario.rol not in roles:
            raise Prohibido("No tiene permisos para esta acción")
        return usuario
    return Depends(verificar)


Staff = Annotated[Usuario, requiere_rol(RolUsuario.admin, RolUsuario.bibliotecario)]
SoloAdmin = Annotated[Usuario, requiere_rol(RolUsuario.admin)]
