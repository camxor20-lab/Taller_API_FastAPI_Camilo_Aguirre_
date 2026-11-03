from fastapi import APIRouter, Query, status
from ..controllers import socio_controller
from ..core.dependencies import CurrentUser, PaginacionDep, SessionDep, SoloAdmin, Staff
from ..core.exceptions import Prohibido
from ..models.usuario import RolUsuario
from ..schemas.pagina import Pagina
from ..schemas.prestamo import EstadoPrestamoEnum, PrestamoRespuesta
from ..schemas.socio import (
    SocioActualizar,
    SocioCrear,
    SocioMultasRespuesta,
    SocioRespuesta,
)
from ..schemas.usuario import SocioActualizarPropio

router = APIRouter(
    prefix="/socios",
    tags=["Socios"]
)


# --- Endpoints Propios del Socio Autenticado ---

@router.get(
    "/me",
    response_model=SocioRespuesta,
    status_code=status.HTTP_200_OK,
    summary="Consultar perfil del socio autenticado"
)
def obtener_mi_perfil(usuario: CurrentUser, db: SessionDep):
    """Retorna la ficha del socio asociado a la cuenta autenticada."""
    if usuario.rol != RolUsuario.socio or usuario.socio_id is None:
        raise Prohibido("Solo los usuarios con rol socio tienen perfil de socio")
    return socio_controller.obtener_socio(db=db, socio_id=usuario.socio_id)


@router.patch(
    "/me",
    response_model=SocioRespuesta,
    status_code=status.HTTP_200_OK,
    summary="Actualizar perfil del socio autenticado"
)
def actualizar_mi_perfil(
    datos: SocioActualizarPropio,
    usuario: CurrentUser,
    db: SessionDep
):
    """Actualiza únicamente nombre y teléfono del socio autenticado (Z4: no permite modificar email, rol ni estado)."""
    if usuario.rol != RolUsuario.socio or usuario.socio_id is None:
        raise Prohibido("Solo los usuarios con rol socio tienen perfil de socio")
    return socio_controller.actualizar_socio_propio(
        db=db,
        socio_id=usuario.socio_id,
        datos=datos,
        usuario=usuario
    )


@router.get(
    "/me/prestamos",
    response_model=Pagina[PrestamoRespuesta],
    status_code=status.HTTP_200_OK,
    summary="Listar préstamos propios del socio"
)
def listar_mis_prestamos(
    usuario: CurrentUser,
    db: SessionDep,
    paginacion: PaginacionDep,
    estado: EstadoPrestamoEnum | None = Query(default=None, description="Filtrar por estado")
):
    """Lista los préstamos solicitados por el socio autenticado."""
    if usuario.rol != RolUsuario.socio or usuario.socio_id is None:
        raise Prohibido("Solo los usuarios con rol socio tienen préstamos")
    return socio_controller.listar_prestamos_socio(
        db=db,
        socio_id=usuario.socio_id,
        skip=paginacion.skip,
        limit=paginacion.limit,
        estado=estado
    )


@router.get(
    "/me/multas",
    response_model=SocioMultasRespuesta,
    status_code=status.HTTP_200_OK,
    summary="Consultar multas pendientes propias del socio"
)
def obtener_mis_multas(usuario: CurrentUser, db: SessionDep):
    """Retorna los préstamos con multas sin pagar del socio autenticado y el saldo acumulado."""
    if usuario.rol != RolUsuario.socio or usuario.socio_id is None:
        raise Prohibido("Solo los usuarios con rol socio tienen multas")
    return socio_controller.obtener_multas_socio(db=db, socio_id=usuario.socio_id)


# --- Endpoints Administrativos ---

@router.get(
    "",
    response_model=list[SocioRespuesta],
    status_code=status.HTTP_200_OK,
    summary="Listar socios (Staff: Bibliotecario o Admin)"
)
def listar_socios(
    db: SessionDep,
    paginacion: PaginacionDep,
    _staff: Staff,
    activo: bool | None = Query(default=None, description="Filtrar por estado activo/inactivo")
):
    """Lista paginada de socios registrados en la biblioteca."""
    return socio_controller.listar_socios(
        db=db,
        skip=paginacion.skip,
        limit=paginacion.limit,
        activo=activo
    )


@router.get(
    "/{id}",
    response_model=SocioRespuesta,
    status_code=status.HTTP_200_OK,
    summary="Consultar socio por ID (Staff: Bibliotecario o Admin)"
)
def obtener_socio(id: int, db: SessionDep, _staff: Staff):
    """Consulta la ficha de un socio por su identificador."""
    return socio_controller.obtener_socio(db=db, socio_id=id)


@router.post(
    "",
    response_model=SocioRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Crear socio (Staff: Bibliotecario o Admin)"
)
def crear_socio(datos: SocioCrear, db: SessionDep, _staff: Staff):
    """Registra manualmente un socio en la biblioteca."""
    return socio_controller.crear_socio(db=db, datos=datos)


@router.patch(
    "/{id}",
    response_model=SocioRespuesta,
    status_code=status.HTTP_200_OK,
    summary="Actualizar socio (Staff: Bibliotecario o Admin)"
)
def actualizar_socio(id: int, datos: SocioActualizar, db: SessionDep, _staff: Staff):
    """Actualiza los datos de un socio."""
    return socio_controller.actualizar_socio(db=db, socio_id=id, datos=datos)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar o desactivar socio (Solo Admin)"
)
def eliminar_socio(id: int, db: SessionDep, _admin: SoloAdmin):
    """Elimina físicamente o desactiva (borrado lógico) a un socio."""
    socio_controller.eliminar_socio(db=db, socio_id=id)
    return None


@router.get(
    "/{id}/prestamos",
    response_model=list[PrestamoRespuesta],
    status_code=status.HTTP_200_OK,
    summary="Listar préstamos de un socio específico (Staff: Bibliotecario o Admin)"
)
def listar_prestamos_socio(
    id: int,
    db: SessionDep,
    paginacion: PaginacionDep,
    _staff: Staff,
    estado: EstadoPrestamoEnum | None = Query(default=None, description="Filtrar por estado: activo, vencido, devuelto")
):
    """Lista los préstamos registrados a nombre de un socio."""
    return socio_controller.listar_prestamos_socio(
        db=db,
        socio_id=id,
        skip=paginacion.skip,
        limit=paginacion.limit,
        estado=estado
    )
