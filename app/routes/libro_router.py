from fastapi import APIRouter, File, Form, Query, UploadFile, status
from ..controllers import libro_controller
from ..core.dependencies import PaginacionDep, SessionDep, SoloAdmin, Staff
from ..core.exceptions import ReglaNegocio
from ..schemas.libro import (
    LibroActualizar,
    LibroCrear,
    LibroRespuesta,
    OrdenLibrosEnum,
)
from ..schemas.pagina import Pagina
from ..services.cloudinary_service import eliminar_imagen, subir_imagen

router = APIRouter(
    prefix="/libros",
    tags=["Libros"]
)


@router.get("", response_model=Pagina[LibroRespuesta], status_code=status.HTTP_200_OK)
def listar_libros(
    db: SessionDep,
    paginacion: PaginacionDep,
    buscar: str | None = Query(default=None, description="Buscar por título (ilike)"),
    autor: str | None = Query(default=None, description="Buscar por nombre del autor (ilike)"),
    categoria_id: int | None = Query(default=None, description="Filtrar por ID de categoría"),
    desde: int | None = Query(default=None, description="Año de publicación inicial"),
    hasta: int | None = Query(default=None, description="Año de publicación final"),
    orden: OrdenLibrosEnum | None = Query(default=None, description="Criterio de ordenación: titulo, anio o -anio")
):
    """Lista paginada de libros con filtros combinables y cálculo de ejemplares disponibles (Público)."""
    return libro_controller.listar_libros(
        db=db,
        skip=paginacion.skip,
        limit=paginacion.limit,
        buscar=buscar,
        autor=autor,
        categoria_id=categoria_id,
        desde=desde,
        hasta=hasta,
        orden=orden
    )


@router.get("/{id}", response_model=LibroRespuesta, status_code=status.HTTP_200_OK)
def obtener_libro(id: int, db: SessionDep):
    """Consulta un libro por su ID con autor, categorías y ejemplares disponibles (Público)."""
    return libro_controller.obtener_libro(db=db, libro_id=id)


@router.post("", response_model=LibroRespuesta, status_code=status.HTTP_201_CREATED)
def crear_libro(datos: LibroCrear, db: SessionDep, _staff: Staff):
    """Crea un nuevo libro en el catálogo mediante JSON (Staff: Bibliotecario o Admin)."""
    return libro_controller.crear_libro(db=db, datos=datos)


@router.post(
    "/con-imagen",
    response_model=LibroRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Crear libro con imagen de portada",
    description="Crea un libro y sube su archivo de portada a Cloudinary en una sola petición multipart/form-data."
)
def crear_libro_con_imagen(
    db: SessionDep,
    titulo: str = Form(..., min_length=1, max_length=150, description="Título del libro"),
    isbn: str = Form(..., description="Código ISBN de 13 dígitos"),
    anio_publicacion: int = Form(..., ge=1450, description="Año de publicación"),
    ejemplares: int = Form(..., ge=1, le=50, description="Cantidad de ejemplares disponibles (1-50)"),
    autor_id: int = Form(..., gt=0, description="ID del autor existente"),
    categoria_ids: list[str] = Form(..., description="IDs de las categorías (repetir campo o enviar separados por comas)"),
    imagen: UploadFile = File(..., description="Archivo de imagen de la portada (JPG, PNG, WEBP, GIF, SVG)")
):
    """
    Endpoint integrado:
    1. Procesa y valida los datos del formulario multipart.
    2. Sube la imagen a Cloudinary obteniendo su secure_url y public_id.
    3. Registra el nuevo libro con su URL de imagen en PostgreSQL.
    """
    # Parsear IDs de categorías (acepta ["1", "2"] o ["1,2"])
    cat_ids: list[int] = []
    for item in categoria_ids:
        for parte in str(item).split(","):
            parte_limpia = parte.strip()
            if parte_limpia:
                try:
                    cat_ids.append(int(parte_limpia))
                except ValueError:
                    raise ReglaNegocio(f"ID de categoría inválido: '{parte_limpia}'")

    if not cat_ids:
        raise ReglaNegocio("Debe asociar al menos una categoría al libro")

    # Subir imagen a Cloudinary
    subida = subir_imagen(archivo=imagen, carpeta="libros")

    # Crear esquema con la URL segura y public_id
    datos_libro = LibroCrear(
        titulo=titulo,
        isbn=isbn,
        anio_publicacion=anio_publicacion,
        ejemplares=ejemplares,
        autor_id=autor_id,
        categoria_ids=cat_ids,
        imagen_url=subida["secure_url"],
        imagen_public_id=subida["public_id"]
    )

    return libro_controller.crear_libro(db=db, datos=datos_libro)


@router.patch(
    "/{id}/portada",
    response_model=LibroRespuesta,
    status_code=status.HTTP_200_OK,
    summary="Actualizar la imagen de portada de un libro",
    description="Recibe un archivo de imagen (UploadFile), lo sube a Cloudinary y actualiza el campo de portada del libro en PostgreSQL."
)
@router.post(
    "/{id}/portada",
    response_model=LibroRespuesta,
    status_code=status.HTTP_200_OK,
    include_in_schema=False
)
def actualizar_portada_libro(
    id: int,
    db: SessionDep,
    imagen: UploadFile = File(..., description="Archivo de imagen de portada (JPG, PNG, WEBP, GIF, SVG)")
):
    """
    Endpoint PATCH para actualizar la portada de un libro:
    1. Verifica la existencia del libro en PostgreSQL.
    2. Si ya existía una imagen previa en Cloudinary, la elimina automáticamente.
    3. Sube la nueva imagen a Cloudinary usando las credenciales del entorno (.env).
    4. Actualiza los campos 'imagen_url' e 'imagen_public_id' en la base de datos mediante SQLAlchemy.
    5. Retorna la información actualizada del libro.
    """
    libro = libro_controller.obtener_libro(db=db, libro_id=id)

    # Eliminar imagen anterior de Cloudinary si existía
    if libro.imagen_public_id:
        try:
            eliminar_imagen(libro.imagen_public_id)
        except Exception:
            pass

    # Subir nueva portada a Cloudinary
    subida = subir_imagen(archivo=imagen, carpeta="libros")

    # Actualizar libro en PostgreSQL
    return libro_controller.actualizar_portada_libro(
        db=db,
        libro_id=id,
        imagen_url=subida["secure_url"],
        imagen_public_id=subida["public_id"]
    )


@router.patch("/{id}", response_model=LibroRespuesta, status_code=status.HTTP_200_OK)
def actualizar_libro(id: int, datos: LibroActualizar, db: SessionDep, _staff: Staff):
    """Actualiza los datos de un libro y reemplaza categorías si se enviaron (Staff: Bibliotecario o Admin)."""
    return libro_controller.actualizar_libro(db=db, libro_id=id, datos=datos)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_libro(id: int, db: SessionDep, _admin: SoloAdmin):
    """Elimina un libro si no tiene préstamos activos y remueve su portada de Cloudinary (Solo Admin)."""
    libro_controller.eliminar_libro(db=db, libro_id=id)
    return None
