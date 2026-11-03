from fastapi import APIRouter, Query, status
from ..controllers import prestamo_controller
from ..core.dependencies import CurrentUser, PaginacionDep, SessionDep, Staff
from ..schemas.prestamo import (
    DevolucionCrear,
    EstadoPrestamoEnum,
    PrestamoCrear,
    PrestamoRespuesta
)

router = APIRouter(
    prefix="/prestamos",
    tags=["Préstamos"]
)


@router.get("", response_model=list[PrestamoRespuesta], status_code=status.HTTP_200_OK)
def listar_prestamos(
    db: SessionDep,
    paginacion: PaginacionDep,
    usuario: CurrentUser,
    estado: EstadoPrestamoEnum | None = Query(default=None, description="Filtrar por estado: activo, vencido, devuelto"),
    socio_id: int | None = Query(default=None, description="Filtrar por ID de socio"),
    libro_id: int | None = Query(default=None, description="Filtrar por ID de libro")
):
    """Lista préstamos con filtros opcionales. Los socios solo ven sus propios préstamos (Z3)."""
    return prestamo_controller.listar_prestamos(
        db=db,
        skip=paginacion.skip,
        limit=paginacion.limit,
        estado=estado,
        socio_id=socio_id,
        libro_id=libro_id,
        usuario=usuario
    )


@router.get("/{id}", response_model=PrestamoRespuesta, status_code=status.HTTP_200_OK)
def obtener_prestamo(id: int, db: SessionDep, usuario: CurrentUser):
    """Consulta un préstamo por ID. Si un socio consulta uno ajeno, recibe 404 (Z2)."""
    return prestamo_controller.obtener_prestamo(db=db, prestamo_id=id, usuario=usuario)


@router.post("", response_model=PrestamoRespuesta, status_code=status.HTTP_201_CREATED)
def crear_prestamo(datos: PrestamoCrear, db: SessionDep, staff: Staff):
    """Registra un nuevo préstamo validando reglas R1-R8, R11 y auditoría registrado_por_id (Z7)."""
    return prestamo_controller.crear_prestamo(db=db, datos=datos, registrado_por_id=staff.id)


@router.post("/{id}/devolucion", response_model=PrestamoRespuesta, status_code=status.HTTP_200_OK)
def registrar_devolucion(
    id: int,
    db: SessionDep,
    _staff: Staff,
    datos: DevolucionCrear | None = None
):
    """Registra la devolución de un préstamo calculando multas por retraso (Staff: Bibliotecario o Admin)."""
    return prestamo_controller.registrar_devolucion(db=db, prestamo_id=id, datos=datos)


@router.post("/{id}/pago-multa", response_model=PrestamoRespuesta, status_code=status.HTTP_200_OK)
def pagar_multa(id: int, db: SessionDep, _staff: Staff):
    """Registra el pago de la multa de un préstamo (Staff: Bibliotecario o Admin)."""
    return prestamo_controller.pagar_multa(db=db, prestamo_id=id)
