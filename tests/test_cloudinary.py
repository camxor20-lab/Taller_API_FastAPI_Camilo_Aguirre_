import io
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.core.dependencies import get_current_user
from app.main import app
from app.models.autor import Autor
from app.models.categoria import Categoria
from app.models.libro import Libro
from app.models.usuario import RolUsuario, Usuario
from app.services.cloudinary_service import CloudinaryService, eliminar_imagen, subir_imagen, subir_imagen_url


@pytest.fixture(scope="session", autouse=True)
def preparar_bd():
    """Crea las tablas antes de las pruebas y las limpia al terminar."""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def cliente():
    # Sobrescribir dependencia de autenticación para pruebas con usuario admin
    usuario_test = Usuario(
        id=999,
        email="admin_test@biblioteca.com",
        nombre="Admin de Pruebas",
        password_hash="fakehash",
        rol=RolUsuario.admin,
        activo=True
    )
    app.dependency_overrides[get_current_user] = lambda: usuario_test
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


from sqlalchemy import select

@pytest.fixture
def datos_iniciales(db_session):
    """Obtiene o crea un autor y dos categorías de prueba en la BD."""
    autor = db_session.scalar(select(Autor).where(Autor.nombre == "Gabriel García Márquez"))
    if not autor:
        autor = Autor(nombre="Gabriel García Márquez", nacionalidad="Colombiana", anio_nacimiento=1927)
        db_session.add(autor)

    cat1 = db_session.scalar(select(Categoria).where(Categoria.nombre == "Ficción"))
    if not cat1:
        cat1 = Categoria(nombre="Ficción", descripcion="Libros de ficción")
        db_session.add(cat1)

    cat2 = db_session.scalar(select(Categoria).where(Categoria.nombre == "Realismo Mágico"))
    if not cat2:
        cat2 = Categoria(nombre="Realismo Mágico", descripcion="Obras de realismo mágico")
        db_session.add(cat2)

    db_session.commit()
    db_session.refresh(autor)
    db_session.refresh(cat1)
    db_session.refresh(cat2)
    return {"autor": autor, "categorias": [cat1, cat2]}


# ==============================================================================
# PRUEBAS DEL SERVICIO CLOUDINARY
# ==============================================================================

def test_subir_imagen_valida_mock():
    """Verifica que subir_imagen llame a Cloudinary y retorne secure_url y public_id."""
    archivo_mock = MagicMock()
    archivo_mock.filename = "portada.jpg"
    archivo_mock.content_type = "image/jpeg"
    archivo_mock.size = 1024 * 50
    archivo_mock.file = io.BytesIO(b"fake image bytes")

    mock_resp = {
        "secure_url": "https://res.cloudinary.com/demo/image/upload/v1234/libros/portada.jpg",
        "public_id": "libros/portada_123"
    }

    with patch("cloudinary.uploader.upload", return_value=mock_resp) as mock_upload:
        resultado = subir_imagen(archivo_mock, carpeta="libros")
        assert resultado["secure_url"] == mock_resp["secure_url"]
        assert resultado["public_id"] == mock_resp["public_id"]
        mock_upload.assert_called_once()


def test_subir_imagen_url_mock():
    """Verifica que subir_imagen_url retorne directamente el string con la URL pública."""
    archivo_mock = MagicMock()
    archivo_mock.filename = "portada.png"
    archivo_mock.content_type = "image/png"
    archivo_mock.size = 1024 * 10
    archivo_mock.file = io.BytesIO(b"fake png bytes")

    mock_resp = {
        "secure_url": "https://res.cloudinary.com/demo/image/upload/v1234/libros/portada.png",
        "public_id": "libros/portada_png"
    }

    with patch("cloudinary.uploader.upload", return_value=mock_resp):
        url = subir_imagen_url(archivo_mock)
        assert url == mock_resp["secure_url"]


def test_validar_archivo_imagen_rechaza_formato_invalido():
    """Verifica que el servicio rechace archivos que no sean imágenes (ej: .pdf o .txt)."""
    archivo_pdf = MagicMock()
    archivo_pdf.filename = "documento.pdf"
    archivo_pdf.content_type = "application/pdf"
    archivo_pdf.size = 1024

    from app.core.exceptions import ReglaNegocio
    with pytest.raises(ReglaNegocio) as exc_info:
        CloudinaryService.validar_archivo_imagen(archivo_pdf)
    assert "no permitida" in str(exc_info.value)


def test_eliminar_imagen_mock():
    """Verifica que eliminar_imagen llame al uploader de Cloudinary destroy."""
    with patch("cloudinary.uploader.destroy", return_value={"result": "ok"}) as mock_destroy:
        exito = eliminar_imagen("libros/portada_123")
        assert exito is True
        mock_destroy.assert_called_once_with("libros/portada_123", resource_type="image")


# ==============================================================================
# PRUEBAS DE LOS ENDPOINTS EN LA API
# ==============================================================================

import random

def generar_isbn() -> str:
    return f"978{random.randint(1000000000, 9999999999)}"


def test_endpoint_crear_libro_con_imagen(cliente: TestClient, datos_iniciales: dict):
    """
    Prueba el endpoint POST /api/v1/libros/con-imagen:
    - Sube multipart con datos del libro e imagen.
    - Cloudinary simula la subida exitosa.
    - PostgreSQL almacena el libro con su secure_url y public_id.
    """
    autor = datos_iniciales["autor"]
    cats = datos_iniciales["categorias"]
    isbn_test = generar_isbn()

    mock_cloudinary_result = {
        "secure_url": "https://res.cloudinary.com/test_cloud/image/upload/v1/libros/portada_cien.jpg",
        "public_id": "libros/portada_cien_abc"
    }

    archivo_imagen = ("portada.jpg", io.BytesIO(b"dummy image data"), "image/jpeg")

    datos_formulario = {
        "titulo": "Cien Años de Soledad",
        "isbn": isbn_test,
        "anio_publicacion": 1967,
        "ejemplares": 5,
        "autor_id": autor.id,
        "categoria_ids": [str(c.id) for c in cats]
    }

    with patch("cloudinary.uploader.upload", return_value=mock_cloudinary_result):
        respuesta = cliente.post(
            "/api/v1/libros/con-imagen",
            data=datos_formulario,
            files={"imagen": archivo_imagen}
        )

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["titulo"] == "Cien Años De Soledad"
    assert cuerpo["isbn"] == isbn_test
    assert cuerpo["imagen_url"] == mock_cloudinary_result["secure_url"]
    assert cuerpo["imagen_public_id"] == mock_cloudinary_result["public_id"]
    assert cuerpo["disponibles"] == 5
    assert len(cuerpo["categorias"]) == 2


def test_endpoint_subir_portada_libro_existente(cliente: TestClient, datos_iniciales: dict, db_session):
    """
    Prueba el endpoint POST /api/v1/libros/{id}/portada:
    - Sube una nueva imagen a un libro ya registrado.
    - Actualiza imagen_url en la base de datos PostgreSQL.
    """
    autor = datos_iniciales["autor"]
    cats = datos_iniciales["categorias"]

    # Crear un libro sin imagen inicial
    libro = Libro(
        titulo="El Coronel No Tiene Quien Le Escriba",
        isbn=generar_isbn(),
        anio_publicacion=1961,
        ejemplares=3,
        autor_id=autor.id,
        categorias=cats
    )
    db_session.add(libro)
    db_session.commit()
    db_session.refresh(libro)

    mock_cloudinary_result = {
        "secure_url": "https://res.cloudinary.com/test_cloud/image/upload/v1/libros/coronel.jpg",
        "public_id": "libros/coronel_xyz"
    }

    archivo_imagen = ("coronel.png", io.BytesIO(b"dummy png bytes"), "image/png")

    with patch("cloudinary.uploader.upload", return_value=mock_cloudinary_result):
        respuesta = cliente.patch(
            f"/api/v1/libros/{libro.id}/portada",
            files={"imagen": archivo_imagen}
        )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["id"] == libro.id
    assert cuerpo["imagen_url"] == mock_cloudinary_result["secure_url"]
    assert cuerpo["imagen_public_id"] == mock_cloudinary_result["public_id"]

    # Verificar en la base de datos
    db_session.expire_all()
    libro_db = db_session.get(Libro, libro.id)
    assert libro_db.imagen_url == mock_cloudinary_result["secure_url"]
    assert libro_db.imagen_public_id == mock_cloudinary_result["public_id"]


def test_endpoint_crear_libro_json_con_imagen_url(cliente: TestClient, datos_iniciales: dict):
    """
    Verifica que el endpoint estándar POST /api/v1/libros también persista imagen_url
    cuando se envía en el payload JSON.
    """
    autor = datos_iniciales["autor"]
    cats = datos_iniciales["categorias"]
    isbn_test = generar_isbn()
    url_previa = "https://res.cloudinary.com/demo/image/upload/v1/libros/remoto.jpg"

    payload = {
        "titulo": "Crónica de una Muerte Anunciada",
        "isbn": isbn_test,
        "anio_publicacion": 1981,
        "ejemplares": 2,
        "autor_id": autor.id,
        "categoria_ids": [cats[0].id],
        "imagen_url": url_previa,
        "imagen_public_id": "libros/remoto_123"
    }

    respuesta = cliente.post("/api/v1/libros", json=payload)
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["imagen_url"] == url_previa
    assert cuerpo["imagen_public_id"] == "libros/remoto_123"


def test_endpoint_eliminar_libro_limpia_cloudinary(cliente: TestClient, datos_iniciales: dict, db_session):
    """
    Verifica que al eliminar un libro con portada en Cloudinary (DELETE /api/v1/libros/{id}),
    se invoque la eliminación en Cloudinary.
    """
    autor = datos_iniciales["autor"]
    cats = datos_iniciales["categorias"]

    libro = Libro(
        titulo="Libro Para Eliminar",
        isbn=generar_isbn(),
        anio_publicacion=2010,
        ejemplares=1,
        autor_id=autor.id,
        categorias=cats,
        imagen_url="https://res.cloudinary.com/test/image/upload/v1/libros/a_borrar.jpg",
        imagen_public_id="libros/a_borrar_id"
    )
    db_session.add(libro)
    db_session.commit()
    db_session.refresh(libro)

    with patch("cloudinary.uploader.destroy", return_value={"result": "ok"}) as mock_destroy:
        res = cliente.delete(f"/api/v1/libros/{libro.id}")
        assert res.status_code == 204
        mock_destroy.assert_called_once_with("libros/a_borrar_id", resource_type="image")
