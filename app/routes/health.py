from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from ..core.dependencies import SessionDep

router = APIRouter(
    prefix="/health",
    tags=["Salud"]
)


@router.get("", status_code=status.HTTP_200_OK, summary="Verificación del estado de salud del sistema")
def check_health(db: SessionDep):
    """Comprueba la disponibilidad de la API y la conectividad con la base de datos."""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "ok"
        }
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "database": "unavailable"
            }
        )

