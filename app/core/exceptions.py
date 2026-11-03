class ErrorAplicacion(Exception):
    """Clase base de todas las excepciones propias de la aplicación."""
    status_code: int = 400
    headers: dict[str, str] | None = None

    def __init__(self, mensaje: str = "Error en la aplicación"):
        super().__init__(mensaje)
        self.mensaje = mensaje


class NoEncontrado(ErrorAplicacion):
    """El recurso solicitado no existe."""
    status_code: int = 404

    def __init__(self, mensaje: str = "Recurso no encontrado"):
        super().__init__(mensaje)


class Conflicto(ErrorAplicacion):
    """Conflicto de integridad: datos duplicados o borrado con dependencias."""
    status_code: int = 409

    def __init__(self, mensaje: str = "Conflicto en la operación"):
        super().__init__(mensaje)


class ReglaNegocio(ErrorAplicacion):
    """Incumplimiento de una regla de negocio del sistema de biblioteca."""
    status_code: int = 422

    def __init__(self, mensaje: str = "Regla de negocio no cumplida"):
        super().__init__(mensaje)


class NoAutenticado(ErrorAplicacion):
    """Falta el token, es inválido, venció o credenciales erróneas."""
    status_code: int = 401

    def __init__(self, mensaje: str = "No autenticado"):
        super().__init__(mensaje)
        self.headers = {"WWW-Authenticate": "Bearer"}


class Prohibido(ErrorAplicacion):
    """El usuario está autenticado pero no tiene los permisos suficientes."""
    status_code: int = 403

    def __init__(self, mensaje: str = "No tiene permisos para esta acción"):
        super().__init__(mensaje)


class CuentaBloqueada(ErrorAplicacion):
    """Demasiados intentos fallidos consecutivos de inicio de sesión."""
    status_code: int = 423

    def __init__(self, mensaje: str = "Cuenta bloqueada temporalmente"):
        super().__init__(mensaje)
