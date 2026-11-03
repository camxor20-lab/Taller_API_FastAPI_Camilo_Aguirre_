from datetime import datetime, timedelta, timezone
from uuid import uuid4
import jwt
from pwdlib import PasswordHash
from .config import get_settings

settings = get_settings()

# Hasher de contraseñas recomendado (Argon2)
password_hasher = PasswordHash.recommended()


def hashear_password(password: str) -> str:
    """Genera el hash seguro Argon2 de la contraseña."""
    return password_hasher.hash(password)


def verificar_password(password: str, hash_guardado: str) -> bool:
    """Verifica si la contraseña en texto plano coincide con el hash Argon2 guardado."""
    return password_hasher.verify(password, hash_guardado)


def crear_token(sub: str, rol: str, tipo: str, duracion: timedelta) -> tuple[str, str]:
    """
    Genera un token JWT (access o refresh) con claims estandarizados:
    - sub: identificador del usuario como texto
    - rol: rol del usuario
    - type: 'access' o 'refresh'
    - iat: fecha de emisión (UTC)
    - exp: fecha de vencimiento (UTC)
    - jti: identificador único del token (uuid4)
    Retorna la tupla (token_jwt, jti).
    """
    ahora = datetime.now(timezone.utc)
    jti = str(uuid4())
    payload = {
        "sub": str(sub),
        "rol": str(rol),
        "type": tipo,
        "iat": ahora,
        "exp": ahora + duracion,
        "jti": jti
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, jti


def decodificar_token(token: str) -> dict:
    """Decodifica y verifica la firma y expiración de un token JWT usando HS256."""
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm]
    )

