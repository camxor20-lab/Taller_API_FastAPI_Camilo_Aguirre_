from typing import Annotated
from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from ..controllers import auth_controller
from ..core.dependencies import CurrentUser, SessionDep
from ..core.rate_limit import limiter
from ..schemas.auth import (
    CambiarPasswordPeticion,
    RefreshTokenPeticion,
    TokenRespuesta,
)
from ..schemas.usuario import UsuarioRegistro, UsuarioRespuesta

router = APIRouter(
    prefix="/auth",
    tags=["Autenticación"]
)


@router.post(
    "/registro",
    response_model=UsuarioRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Registro público de socios"
)
@limiter.limit("5/minute")
def registrar_socio(request: Request, datos: UsuarioRegistro, db: SessionDep):
    """Crea una cuenta de usuario con rol socio y su ficha de socio asociada en una única transacción."""
    return auth_controller.registrar_socio(db=db, datos=datos)


@router.post(
    "/login",
    response_model=TokenRespuesta,
    status_code=status.HTTP_200_OK,
    summary="Inicio de sesión (OAuth2 Password Flow)"
)
@limiter.limit("10/minute")
def login_usuario(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: SessionDep
):
    """Autentica las credenciales del usuario y retorna un access token y un refresh token."""
    return auth_controller.login_usuario(
        db=db,
        email=form_data.username,
        password=form_data.password
    )


@router.post(
    "/refresh",
    response_model=TokenRespuesta,
    status_code=status.HTTP_200_OK,
    summary="Rotación de refresh token"
)
def rotar_token(datos: RefreshTokenPeticion, db: SessionDep):
    """Invalida el refresh token provisto y emite un nuevo par de tokens."""
    return auth_controller.rotar_refresh_token(db=db, token_str=datos.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cierre de sesión"
)
def logout(datos: RefreshTokenPeticion, db: SessionDep, _usuario: CurrentUser):
    """Revoca el refresh token provisto."""
    auth_controller.logout_usuario(db=db, token_str=datos.refresh_token)
    return None


@router.get(
    "/me",
    response_model=UsuarioRespuesta,
    status_code=status.HTTP_200_OK,
    summary="Perfil del usuario autenticado"
)
def obtener_perfil_me(usuario: CurrentUser):
    """Retorna los datos del usuario actualmente autenticado."""
    return usuario


@router.patch(
    "/me/password",
    status_code=status.HTTP_200_OK,
    summary="Cambio de contraseña del usuario autenticado"
)
def cambiar_password(
    datos: CambiarPasswordPeticion,
    usuario: CurrentUser,
    db: SessionDep
):
    """Cambia la contraseña del usuario autenticado y revoca todas sus sesiones activas."""
    auth_controller.cambiar_password_me(db=db, usuario=usuario, datos=datos)
    return {"mensaje": "Contraseña actualizada exitosamente. Todas las sesiones han sido revocadas."}
