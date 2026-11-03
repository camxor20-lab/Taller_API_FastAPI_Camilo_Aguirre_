from fastapi import APIRouter, Query, status
from ..controllers import usuario_controller
from ..core.dependencies import PaginacionDep, SessionDep, SoloAdmin
from ..models.usuario import RolUsuario
from ..schemas.usuario import (
    CambiarActivo,
    CambiarRol,
    UsuarioCrear,
    UsuarioRespuesta,
)

router = APIRouter(
    prefix="/usuarios",
    tags=["Gestión de Usuarios"]
)


@router.get(
    "",
    response_model=list[UsuarioRespuesta],
    status_code=status.HTTP_200_OK,
    summary="Lista paginada de usuarios (Solo Admin)"
)
def listar_usuarios(
    db: SessionDep,
    paginacion: PaginacionDep,
    _admin: SoloAdmin,
    rol: RolUsuario | None = Query(default=None, description="Filtrar por rol"),
    activo: bool | None = Query(default=None, description="Filtrar por estado activo")
):
    """Retorna la lista de usuarios del sistema."""
    return usuario_controller.listar_usuarios(
        db=db,
        skip=paginacion.skip,
        limit=paginacion.limit,
        rol=rol,
        activo=activo
    )


@router.post(
    "",
    response_model=UsuarioRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Crear bibliotecario o administrador (Solo Admin)"
)
def crear_usuario(
    datos: UsuarioCrear,
    db: SessionDep,
    _admin: SoloAdmin
):
    """Crea una nueva cuenta con rol bibliotecario o administrador."""
    return usuario_controller.crear_usuario(db=db, datos=datos)


@router.patch(
    "/{id}/rol",
    response_model=UsuarioRespuesta,
    status_code=status.HTTP_200_OK,
    summary="Cambiar rol de usuario (Solo Admin)"
)
def cambiar_rol(
    id: int,
    datos: CambiarRol,
    db: SessionDep,
    admin: SoloAdmin
):
    """Actualiza el rol de un usuario y revoca sus refresh tokens."""
    return usuario_controller.cambiar_rol(
        db=db,
        usuario_id=id,
        datos=datos,
        admin_actual=admin
    )


@router.patch(
    "/{id}/activo",
    response_model=UsuarioRespuesta,
    status_code=status.HTTP_200_OK,
    summary="Activar o desactivar usuario (Solo Admin)"
)
def cambiar_activo(
    id: int,
    datos: CambiarActivo,
    db: SessionDep,
    admin: SoloAdmin
):
    """Activa o desactiva un usuario en el sistema."""
    return usuario_controller.cambiar_activo(
        db=db,
        usuario_id=id,
        datos=datos,
        admin_actual=admin
    )

