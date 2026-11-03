from fastapi import APIRouter, status
from ..controllers import categoria_controller
from ..core.dependencies import PaginacionDep, SessionDep, SoloAdmin, Staff
from ..schemas.categoria import (
    CategoriaActualizar,
    CategoriaCrear,
    CategoriaRespuesta
)
from ..schemas.pagina import Pagina

router = APIRouter(
    prefix="/categorias",
    tags=["Categorías"]
)


@router.get("", response_model=Pagina[CategoriaRespuesta], status_code=status.HTTP_200_OK)
def listar_categorias(db: SessionDep, paginacion: PaginacionDep):
    """Lista paginada de categorías registradas en la biblioteca (Público)."""
    return categoria_controller.listar_categorias(
        db=db,
        skip=paginacion.skip,
        limit=paginacion.limit
    )


@router.get("/{id}", response_model=CategoriaRespuesta, status_code=status.HTTP_200_OK)
def obtener_categoria(id: int, db: SessionDep):
    """Consulta una categoría por su ID (Público)."""
    return categoria_controller.obtener_categoria(db=db, categoria_id=id)


@router.post("", response_model=CategoriaRespuesta, status_code=status.HTTP_201_CREATED)
def crear_categoria(datos: CategoriaCrear, db: SessionDep, _staff: Staff):
    """Crea una nueva categoría en minúsculas y sin espacios sobrantes (Staff: Bibliotecario o Admin)."""
    return categoria_controller.crear_categoria(db=db, datos=datos)


@router.patch("/{id}", response_model=CategoriaRespuesta, status_code=status.HTTP_200_OK)
def actualizar_categoria(id: int, datos: CategoriaActualizar, db: SessionDep, _staff: Staff):
    """Actualiza los datos de una categoría (Staff: Bibliotecario o Admin)."""
    return categoria_controller.actualizar_categoria(db=db, categoria_id=id, datos=datos)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_categoria(id: int, db: SessionDep, _admin: SoloAdmin):
    """Elimina una categoría y la retira de los libros que la tenían (Solo Admin)."""
    categoria_controller.eliminar_categoria(db=db, categoria_id=id)
    return None
