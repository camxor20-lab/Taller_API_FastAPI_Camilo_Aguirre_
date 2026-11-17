from contextlib import asynccontextmanager
import logging
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from .core.config import get_settings
from .core.exceptions import ErrorAplicacion
from .core.rate_limit import limiter
from .routes.auth_router import router as auth_router
from .routes.autor_router import router as autor_router
from .routes.categoria_router import router as categoria_router
from .routes.health import router as health_router
from .routes.libro_router import router as libro_router
from .routes.prestamo_router import router as prestamo_router
from .routes.reporte_router import router as reporte_router
from .routes.socio_router import router as socio_router
from .routes.usuario_router import router as usuario_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("biblioteca")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="API Biblioteca SENA",
    description="Backend completo y seguro para gestión de biblioteca con FastAPI, SQLAlchemy y PostgreSQL",
    version="2.0.0",
    docs_url="/docs" if settings.environment != "prod" else None,
    redoc_url="/redoc" if settings.environment != "prod" else None,
    lifespan=lifespan
)

app.state.limiter = limiter

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware Request ID y Registro de Accesos (sin registrar contraseñas ni tokens)
@app.middleware("http")
async def request_id_and_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start_time = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    response.headers["X-Request-ID"] = request_id

    logger.info(
        f"[{request_id}] {request.method} {request.url.path} -> {response.status_code} ({elapsed_ms:.2f} ms)"
    )
    return response


# Manejador de límite de peticiones (429)
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Se superó el límite de peticiones por minuto"}
    )


# Manejador centralizado para todas las excepciones propias de la aplicación
@app.exception_handler(ErrorAplicacion)
async def error_aplicacion_handler(request: Request, exc: ErrorAplicacion):
    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.mensaje},
        headers=headers
    )


# Manejador para errores internos no controlados (500)
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Error interno no controlado: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor"}
    )


# Enrutador principal v1 (/api/v1)
api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(autor_router)
api_v1_router.include_router(categoria_router)
api_v1_router.include_router(libro_router)
api_v1_router.include_router(socio_router)
api_v1_router.include_router(prestamo_router)
api_v1_router.include_router(reporte_router)
api_v1_router.include_router(usuario_router)

app.include_router(api_v1_router)

# Configuración y montaje del frontend estático
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", tags=["Frontend"], include_in_schema=False)
def root():
    """Sirve la interfaz web moderna de la biblioteca."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "mensaje": "API de Biblioteca en ejecución",
        "version": "2.0.0",
        "docs": "/docs" if settings.environment != "prod" else None
    }
