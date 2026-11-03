from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..core.exceptions import Conflicto, NoEncontrado, ReglaNegocio
from ..core.security import hashear_password
from ..models.refresh_token import RefreshToken
from ..models.usuario import RolUsuario, Usuario
from ..schemas.usuario import CambiarActivo, CambiarRol, UsuarioCrear


def listar_usuarios(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    rol: RolUsuario | None = None,
    activo: bool | None = None
) -> list[Usuario]:
    """Lista usuarios paginados con filtros opcionales por rol y estado activo."""
    consulta = select(Usuario)
    if rol is not None:
        consulta = consulta.where(Usuario.rol == rol)
    if activo is not None:
        consulta = consulta.where(Usuario.activo == activo)
    consulta = consulta.order_by(Usuario.id.asc()).offset(skip).limit(limit)
    return list(db.scalars(consulta).all())


def crear_usuario(db: Session, datos: UsuarioCrear) -> Usuario:
    """Crea un usuario con rol bibliotecario o admin (solo administradores)."""
    email_limpio = datos.email.lower()
    existente = db.scalar(
        select(Usuario).where(func.lower(Usuario.email) == email_limpio)
    )
    if existente:
        raise Conflicto("Ya existe un usuario con ese correo electrónico")

    nuevo_usuario = Usuario(
        email=email_limpio,
        nombre=datos.nombre,
        password_hash=hashear_password(datos.password),
        rol=datos.rol,
        activo=True,
        intentos_fallidos=0,
        bloqueado_hasta=None,
        socio_id=None
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario


def cambiar_rol(
    db: Session,
    usuario_id: int,
    datos: CambiarRol,
    admin_actual: Usuario
) -> Usuario:
    """
    Cambia el rol de un usuario aplicando Z5 y Z6:
    - Z5: Un admin no puede quitarse el rol de admin a sí mismo (422) y debe haber al menos un admin activo.
    - Z6: Revoca todos los refresh tokens del usuario.
    """
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise NoEncontrado("Usuario no encontrado")

    # Z5: El admin actual no puede quitarse el rol a sí mismo
    if usuario.id == admin_actual.id and datos.rol != RolUsuario.admin:
        raise ReglaNegocio("Un administrador no puede quitarse el rol de administrador a sí mismo")

    # Si es admin y cambia a otro rol, asegurar que quede al menos un admin activo
    if usuario.rol == RolUsuario.admin and datos.rol != RolUsuario.admin:
        otros_admins = db.scalar(
            select(func.count(Usuario.id)).where(
                Usuario.rol == RolUsuario.admin,
                Usuario.activo.is_(True),
                Usuario.id != usuario_id
            )
        ) or 0
        if otros_admins == 0:
            raise ReglaNegocio("Debe existir siempre al menos un administrador activo")

    usuario.rol = datos.rol

    # Z6: Revocar todos los refresh tokens
    tokens = list(
        db.scalars(select(RefreshToken).where(RefreshToken.usuario_id == usuario_id)).all()
    )
    for t in tokens:
        t.revocado = True

    db.commit()
    db.refresh(usuario)
    return usuario


def cambiar_activo(
    db: Session,
    usuario_id: int,
    datos: CambiarActivo,
    admin_actual: Usuario
) -> Usuario:
    """
    Activa o desactiva un usuario aplicando Z5 y Z6:
    - Z5: Un admin no puede desactivarse a sí mismo (422) y debe haber al menos un admin activo.
    - Z6: Si se desactiva, revoca todos sus refresh tokens.
    """
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise NoEncontrado("Usuario no encontrado")

    # Z5: El admin actual no puede desactivarse a sí mismo
    if usuario.id == admin_actual.id and not datos.activo:
        raise ReglaNegocio("Un administrador no puede desactivarse a sí mismo")

    # Si es admin y se desactiva, asegurar que quede otro admin activo
    if usuario.rol == RolUsuario.admin and not datos.activo:
        otros_admins = db.scalar(
            select(func.count(Usuario.id)).where(
                Usuario.rol == RolUsuario.admin,
                Usuario.activo.is_(True),
                Usuario.id != usuario_id
            )
        ) or 0
        if otros_admins == 0:
            raise ReglaNegocio("Debe existir siempre al menos un administrador activo")

    usuario.activo = datos.activo

    # Z6: Revocar todos los refresh tokens
    tokens = list(
        db.scalars(select(RefreshToken).where(RefreshToken.usuario_id == usuario_id)).all()
    )
    for t in tokens:
        t.revocado = True

    db.commit()
    db.refresh(usuario)
    return usuario

