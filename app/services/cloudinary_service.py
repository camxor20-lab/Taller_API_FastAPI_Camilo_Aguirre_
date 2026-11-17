import logging
from pathlib import Path
from fastapi import UploadFile
import cloudinary
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError

from ..core.config import get_settings
from ..core.exceptions import ErrorAplicacion, ReglaNegocio

logger = logging.getLogger("biblioteca.cloudinary")

# Extensiones y tipos MIME permitidos
MIME_TYPES_PERMITIDOS = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/svg+xml"
}

EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}
TAMANO_MAXIMO_BYTES = 10 * 1024 * 1024  # 10 MB


def configurar_cloudinary() -> None:
    """Configura el SDK de Cloudinary con las credenciales cargadas desde Settings."""
    settings = get_settings()
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True
    )


# Configuración automática al cargar el módulo
configurar_cloudinary()


class CloudinaryService:
    """Servicio para la gestión y subida de archivos multimedia a Cloudinary."""

    @staticmethod
    def validar_archivo_imagen(archivo: UploadFile) -> None:
        """
        Valida que el archivo subido sea una imagen permitida y no exceda el tamaño máximo.
        Lanza ReglaNegocio si no cumple las condiciones.
        """
        # 1. Validar nombre y extensión
        nombre_archivo = archivo.filename or ""
        extension = Path(nombre_archivo).suffix.lower()
        if extension not in EXTENSIONES_PERMITIDAS:
            raise ReglaNegocio(
                f"Extensión de archivo '{extension}' no permitida. Formatos admitidos: JPG, JPEG, PNG, WEBP, GIF, SVG"
            )

        # 2. Validar tipo MIME
        content_type = (archivo.content_type or "").lower()
        if content_type not in MIME_TYPES_PERMITIDOS and not content_type.startswith("image/"):
            raise ReglaNegocio(
                f"Tipo de contenido '{content_type}' no soportado. El archivo debe ser una imagen válida"
            )

        # 3. Validar tamaño (si está disponible a través de archivo.size)
        if archivo.size is not None and archivo.size > TAMANO_MAXIMO_BYTES:
            max_mb = TAMANO_MAXIMO_BYTES // (1024 * 1024)
            raise ReglaNegocio(f"La imagen no debe superar los {max_mb} MB")

    @classmethod
    def subir_imagen(
        cls,
        archivo: UploadFile,
        carpeta: str = "libros"
    ) -> dict[str, str]:
        """
        Sube un archivo de imagen (UploadFile) a Cloudinary de forma segura.

        Retorna:
            dict con 'secure_url' (URL pública HTTPS) y 'public_id' (identificador en Cloudinary).
        """
        cls.validar_archivo_imagen(archivo)

        # Rebobinar el cursor del archivo por seguridad
        try:
            archivo.file.seek(0)
        except Exception:
            pass

        try:
            resultado = cloudinary.uploader.upload(
                archivo.file,
                folder=carpeta,
                resource_type="image",
                overwrite=True
            )
            secure_url = resultado.get("secure_url")
            public_id = resultado.get("public_id")

            if not secure_url:
                raise ErrorAplicacion("Cloudinary no retornó una URL segura para la imagen")

            logger.info("Imagen subida exitosamente a Cloudinary: %s (public_id: %s)", secure_url, public_id)
            return {
                "secure_url": str(secure_url),
                "public_id": str(public_id)
            }

        except CloudinaryError as exc:
            mensaje = str(exc)
            logger.error("Error de la API de Cloudinary: %s", mensaje)
            if "must supply api_key" in mensaje.lower() or "invalid api_key" in mensaje.lower():
                raise ErrorAplicacion(
                    "Credenciales de Cloudinary inválidas o incompletas. Revise el archivo .env"
                )
            raise ErrorAplicacion(f"Error al subir la imagen a Cloudinary: {mensaje}")

        except Exception as exc:
            if isinstance(exc, (ReglaNegocio, ErrorAplicacion)):
                raise exc
            logger.exception("Error inesperado al subir imagen a Cloudinary: %s", exc)
            raise ErrorAplicacion(f"Fallo en el servicio de subida de imágenes: {str(exc)}")

    @classmethod
    def subir_imagen_url(
        cls,
        archivo: UploadFile,
        carpeta: str = "libros"
    ) -> str:
        """
        Sube una imagen a Cloudinary y retorna directamente la URL pública segura (secure_url).
        """
        resultado = cls.subir_imagen(archivo=archivo, carpeta=carpeta)
        return resultado["secure_url"]

    @classmethod
    def eliminar_imagen(cls, public_id: str) -> bool:
        """
        Elimina una imagen de Cloudinary a partir de su public_id.
        Retorna True si fue eliminada satisfactoriamente o ya no existía.
        """
        if not public_id:
            return False

        try:
            respuesta = cloudinary.uploader.destroy(public_id, resource_type="image")
            exito = respuesta.get("result") in ("ok", "not found")
            if exito:
                logger.info("Imagen eliminada de Cloudinary: %s", public_id)
            else:
                logger.warning("Respuesta inesperada al eliminar imagen %s: %s", public_id, respuesta)
            return exito
        except Exception as exc:
            logger.warning("No se pudo eliminar la imagen %s de Cloudinary: %s", public_id, exc)
            return False


# Funciones de conveniencia a nivel de módulo
subir_imagen = CloudinaryService.subir_imagen
subir_imagen_url = CloudinaryService.subir_imagen_url
eliminar_imagen = CloudinaryService.eliminar_imagen

