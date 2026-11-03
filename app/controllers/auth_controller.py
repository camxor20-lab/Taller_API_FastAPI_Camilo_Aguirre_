from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..core.config import get_settings
from ..core.exceptions import (
    Conflicto,
    CuentaBloqueada,
    NoAutenticado,
    Prohibido,
)
from ..core.security import (
    crear_token,
    decodificar_token,
    hashear_password,
    verificar_password,
)
from ..models.refresh_token import RefreshToken
from ..models.socio import Socio
from ..models.usuario import RolUsuario, Usuario
from ..schemas.auth import CambiarPasswordPeticion, TokenRespuesta
from ..schemas.usuario import UsuarioRegistro

settings = get_settings()


def registrar_socio(db: Session, datos: UsuarioRegistro) -> Usuario:
    """Registra un nuevo usuario con rol socio y crea su registro asociado en socios."""
    email_limpio = datos.email.lower()

    # Validar que el email no esté registrado en usuarios ni en socios
    usuario_existente = db.scalar(
        select(Usuario).where(func.lower(Usuario.email) == email_limpio)
    )
    if usuario_existente:
        raise Conflicto("Ya existe un usuario con ese correo electrónico")

    socio_existente = db.scalar(
        select(Socio).where(func.lower(Socio.email) == email_limpio)
    )
    if socio_existente:
        raise Conflicto("Ya existe un socio con ese correo electrónico")

    # Transacción atómica: se crea socio y luego usuario
    nuevo_socio = Socio(
        nombre=datos.nombre,
        email=email_limpio,
        telefono=datos.telefono,
        activo=True
    )
    db.add(nuevo_socio)
    db.flush()

    nuevo_usuario = Usuario(
        email=email_limpio,
        nombre=datos.nombre,
        password_hash=hashear_password(datos.password),
        rol=RolUsuario.socio,
        activo=True,
        intentos_fallidos=0,
        bloqueado_hasta=None,
        socio_id=nuevo_socio.id
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return nuevo_usuario


def login_usuario(db: Session, email: str, password: str) -> TokenRespuesta:
    """
    Inicia sesión con OAuth2 Password Flow aplicando las reglas A1, A2 y A3:
    - A1: Mensaje idéntico si el email no existe o contraseña es incorrecta.
    - A2: Usuario debe estar activo.
    - A3: Bloqueo de 15 min tras 5 intentos fallidos consecutivos.
    """
    ahora = datetime.now(timezone.utc)
    email_limpio = email.strip().lower()

    usuario = db.scalar(
        select(Usuario).where(func.lower(Usuario.email) == email_limpio)
    )

    if not usuario:
        # A1: Mismo mensaje si el usuario no existe para prevenir enumeración
        raise NoAutenticado("Credenciales inválidas")

    # A3: Verificar si la cuenta está bloqueada temporalmente
    if usuario.bloqueado_hasta is not None:
        if usuario.bloqueado_hasta > ahora:
            raise CuentaBloqueada("Cuenta bloqueada temporalmente")
        else:
            # El periodo de bloqueo expiró, restablecemos
            usuario.bloqueado_hasta = None
            usuario.intentos_fallidos = 0
            db.commit()

    # A2: Verificar si el usuario está activo
    if not usuario.activo:
        raise Prohibido("Usuario inactivo")

    # Verificar contraseña
    if not verificar_password(password, usuario.password_hash):
        usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos >= 5:
            usuario.bloqueado_hasta = ahora + timedelta(minutes=15)
        db.commit()

        if usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
            raise CuentaBloqueada("Cuenta bloqueada temporalmente")

        raise NoAutenticado("Credenciales inválidas")

    # Login correcto: reiniciar intentos fallidos y bloqueo
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None

    # Generar access token y refresh token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    refresh_token_expires = timedelta(days=settings.refresh_token_expire_days)

    access_token, _ = crear_token(
        sub=str(usuario.id),
        rol=usuario.rol.value,
        tipo="access",
        duracion=access_token_expires
    )
    refresh_token, refresh_jti = crear_token(
        sub=str(usuario.id),
        rol=usuario.rol.value,
        tipo="refresh",
        duracion=refresh_token_expires
    )

    # Registrar el JTI del refresh token en la base de datos
    db_refresh = RefreshToken(
        jti=refresh_jti,
        usuario_id=usuario.id,
        expira_en=ahora + refresh_token_expires,
        revocado=False
    )
    db.add(db_refresh)
    db.commit()

    return TokenRespuesta(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds())
    )


def rotar_refresh_token(db: Session, token_str: str) -> TokenRespuesta:
    """
    Renueva un par de tokens aplicando las reglas A4, A5 y A6:
    - Revoca el refresh token presentado y entrega uno nuevo.
    - Detección de reuso: si se envía un refresh token revocado, se revocan todos los tokens del usuario.
    """
    ahora = datetime.now(timezone.utc)

    try:
        payload = decodificar_token(token_str)
    except Exception:
        raise NoAutenticado("Token inválido o vencido")

    # A5: Validar que sea de tipo 'refresh'
    if payload.get("type") != "refresh":
        raise NoAutenticado("Tipo de token inválido")

    jti = payload.get("jti")
    user_id_str = payload.get("sub")
    if not jti or not user_id_str:
        raise NoAutenticado("Token malformado")

    user_id = int(user_id_str)
    usuario = db.get(Usuario, user_id)
    if not usuario or not usuario.activo:
        raise Prohibido("Usuario inactivo")

    # A6: Buscar el refresh token en la base de datos
    token_db = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
    if not token_db:
        raise NoAutenticado("Refresh token no encontrado")

    # Si ya fue revocado -> sospecha de robo de sesión, revocar TODOS los tokens de ese usuario
    if token_db.revocado:
        tokens_usuario = list(
            db.scalars(select(RefreshToken).where(RefreshToken.usuario_id == user_id)).all()
        )
        for t in tokens_usuario:
            t.revocado = True
        db.commit()
        raise NoAutenticado("Refresh token revocado previamente. Sesiones canceladas.")

    # Si ya venció en BD
    if token_db.expira_en < ahora:
        token_db.revocado = True
        db.commit()
        raise NoAutenticado("Refresh token expirado")

    # Revocar el token actual (rotación)
    token_db.revocado = True

    # Generar nuevo par
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    refresh_token_expires = timedelta(days=settings.refresh_token_expire_days)

    nuevo_access_token, _ = crear_token(
        sub=str(usuario.id),
        rol=usuario.rol.value,
        tipo="access",
        duracion=access_token_expires
    )
    nuevo_refresh_token, nuevo_jti = crear_token(
        sub=str(usuario.id),
        rol=usuario.rol.value,
        tipo="refresh",
        duracion=refresh_token_expires
    )

    nuevo_db_refresh = RefreshToken(
        jti=nuevo_jti,
        usuario_id=usuario.id,
        expira_en=ahora + refresh_token_expires,
        revocado=False
    )
    db.add(nuevo_db_refresh)
    db.commit()

    return TokenRespuesta(
        access_token=nuevo_access_token,
        refresh_token=nuevo_refresh_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds())
    )


def logout_usuario(db: Session, token_str: str) -> None:
    """Revoca el refresh token presentado."""
    try:
        payload = decodificar_token(token_str)
    except Exception:
        return

    jti = payload.get("jti")
    if jti:
        token_db = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
        if token_db:
            token_db.revocado = True
            db.commit()


def cambiar_password_me(
    db: Session,
    usuario: Usuario,
    datos: CambiarPasswordPeticion
) -> None:
    """Cambia la contraseña del usuario autenticado y revoca todos sus refresh tokens."""
    if not verificar_password(datos.password_actual, usuario.password_hash):
        raise NoAutenticado("Contraseña actual incorrecta")

    usuario.password_hash = hashear_password(datos.password_nueva)

    # Revocar todos los refresh tokens del usuario
    tokens_usuario = list(
        db.scalars(select(RefreshToken).where(RefreshToken.usuario_id == usuario.id)).all()
    )
    for t in tokens_usuario:
        t.revocado = True

    db.commit()

