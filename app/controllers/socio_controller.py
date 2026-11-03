from datetime import date
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from ..core.exceptions import Conflicto, NoEncontrado
from ..models.prestamo import Prestamo
from ..models.socio import Socio
from ..models.usuario import Usuario
from ..schemas.prestamo import EstadoPrestamoEnum
from ..schemas.socio import SocioActualizar, SocioCrear
from ..schemas.usuario import SocioActualizarPropio


def listar_socios(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    activo: bool | None = None
) -> dict:
    """Retorna una lista paginada de socios con filtro opcional por estado activo."""
    consulta = select(Socio)
    conteo = select(func.count(Socio.id))
    if activo is not None:
        consulta = consulta.where(Socio.activo == activo)
        conteo = conteo.where(Socio.activo == activo)

    total = db.scalar(conteo) or 0
    consulta = consulta.order_by(Socio.id.asc()).offset(skip).limit(limit)
    items = list(db.scalars(consulta).all())
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


def obtener_socio(db: Session, socio_id: int) -> Socio:
    """Consulta un socio por su ID o lanza NoEncontrado si no existe."""
    socio = db.get(Socio, socio_id)
    if not socio:
        raise NoEncontrado("Socio no encontrado")
    return socio


def crear_socio(db: Session, datos: SocioCrear) -> Socio:
    """Crea un nuevo socio validando unicidad de correo electrónico."""
    existente = db.scalar(
        select(Socio).where(func.lower(Socio.email) == datos.email.lower())
    )
    if existente:
        raise Conflicto("Ya existe un socio con ese correo electrónico")

    nuevo_socio = Socio(
        nombre=datos.nombre,
        email=datos.email,
        telefono=datos.telefono,
        activo=datos.activo
    )
    db.add(nuevo_socio)
    db.commit()
    db.refresh(nuevo_socio)
    return nuevo_socio


def actualizar_socio(
    db: Session,
    socio_id: int,
    datos: SocioActualizar
) -> Socio:
    """Actualiza solo los campos enviados validando duplicados de email."""
    socio = obtener_socio(db, socio_id)

    if datos.email is not None:
        existente = db.scalar(
            select(Socio).where(
                func.lower(Socio.email) == datos.email.lower(),
                Socio.id != socio_id
            )
        )
        if existente:
            raise Conflicto("Ya existe otro socio con ese correo electrónico")
        socio.email = datos.email

    if datos.nombre is not None:
        socio.nombre = datos.nombre

    if datos.telefono is not None:
        socio.telefono = datos.telefono

    if datos.activo is not None:
        socio.activo = datos.activo

    db.commit()
    db.refresh(socio)
    return socio


def actualizar_socio_propio(
    db: Session,
    socio_id: int,
    datos: SocioActualizarPropio,
    usuario: Usuario
) -> Socio:
    """Actualiza solo nombre y teléfono del propio socio autenticado."""
    socio = obtener_socio(db, socio_id)

    if datos.nombre is not None:
        socio.nombre = datos.nombre
        usuario.nombre = datos.nombre

    if datos.telefono is not None:
        socio.telefono = datos.telefono

    db.commit()
    db.refresh(socio)
    return socio


def eliminar_socio(db: Session, socio_id: int) -> None:
    """
    Elimina un socio:
    - 409 si tiene préstamos sin devolver.
    - Si solo tiene préstamos devueltos, se desactiva (borrado lógico).
    - Si no tiene préstamos, se elimina físicamente de la base de datos.
    """
    socio = obtener_socio(db, socio_id)

    # 1. Comprobar si tiene préstamos activos / sin devolver
    prestamos_sin_devolver = db.scalar(
        select(func.count(Prestamo.id)).where(
            Prestamo.socio_id == socio_id,
            Prestamo.fecha_devolucion.is_(None)
        )
    ) or 0
    if prestamos_sin_devolver > 0:
        raise Conflicto("No se puede eliminar el socio porque tiene préstamos sin devolver")

    # 2. Comprobar si tiene préstamos registrados en su historial (ya devueltos)
    total_prestamos = db.scalar(
        select(func.count(Prestamo.id)).where(Prestamo.socio_id == socio_id)
    ) or 0

    if total_prestamos > 0:
        # Borrado lógico: se marca inactivo
        socio.activo = False
        db.commit()
    else:
        # Borrado físico
        db.delete(socio)
        db.commit()


def listar_prestamos_socio(
    db: Session,
    socio_id: int,
    skip: int = 0,
    limit: int = 10,
    estado: EstadoPrestamoEnum | None = None
) -> dict:
    """Lista los préstamos de un socio con filtro opcional de estado."""
    obtener_socio(db, socio_id)

    hoy = date.today()
    consulta = select(Prestamo).options(
        selectinload(Prestamo.libro),
        selectinload(Prestamo.socio)
    ).where(Prestamo.socio_id == socio_id)

    conteo = select(func.count(Prestamo.id)).where(Prestamo.socio_id == socio_id)

    if estado == EstadoPrestamoEnum.devuelto:
        filtro = Prestamo.fecha_devolucion.is_not(None)
        consulta = consulta.where(filtro)
        conteo = conteo.where(filtro)
    elif estado == EstadoPrestamoEnum.vencido:
        filtro_vencido = (Prestamo.fecha_devolucion.is_(None), Prestamo.fecha_limite < hoy)
        consulta = consulta.where(*filtro_vencido)
        conteo = conteo.where(*filtro_vencido)
    elif estado == EstadoPrestamoEnum.activo:
        filtro_activo = (Prestamo.fecha_devolucion.is_(None), Prestamo.fecha_limite >= hoy)
        consulta = consulta.where(*filtro_activo)
        conteo = conteo.where(*filtro_activo)

    total = db.scalar(conteo) or 0
    consulta = consulta.order_by(Prestamo.id.desc()).offset(skip).limit(limit)
    prestamos = list(db.scalars(consulta).all())

    for p in prestamos:
        if p.fecha_devolucion is not None:
            p.estado = "devuelto"
        elif p.fecha_limite < hoy:
            p.estado = "vencido"
        else:
            p.estado = "activo"

    return {
        "items": prestamos,
        "total": total,
        "skip": skip,
        "limit": limit
    }


def obtener_multas_socio(db: Session, socio_id: int) -> dict:
    """Retorna los préstamos con multas no pagadas de un socio y el total adeudado."""
    obtener_socio(db, socio_id)
    hoy = date.today()

    consulta = select(Prestamo).options(
        selectinload(Prestamo.libro),
        selectinload(Prestamo.socio)
    ).where(
        Prestamo.socio_id == socio_id,
        Prestamo.multa > Decimal("0.00"),
        Prestamo.multa_pagada.is_(False)
    )

    prestamos = list(db.scalars(consulta).all())
    for p in prestamos:
        if p.fecha_devolucion is not None:
            p.estado = "devuelto"
        elif p.fecha_limite < hoy:
            p.estado = "vencido"
        else:
            p.estado = "activo"

    total_adeudado = sum((p.multa for p in prestamos), Decimal("0.00"))

    return {
        "prestamos": prestamos,
        "total_adeudado": total_adeudado
    }
