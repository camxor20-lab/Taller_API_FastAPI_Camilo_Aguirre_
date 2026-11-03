from pydantic import BaseModel, Field, field_validator


class TokenRespuesta(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=900, description="Segundos de validez del access token")


class RefreshTokenPeticion(BaseModel):
    refresh_token: str = Field(..., description="Refresh token para rotación o cierre de sesión")


class CambiarPasswordPeticion(BaseModel):
    password_actual: str = Field(..., description="Contraseña actual del usuario")
    password_nueva: str = Field(..., min_length=8, max_length=64, description="Nueva contraseña segura")

    @field_validator("password_nueva")
    @classmethod
    def validar_password_nueva(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 64:
            raise ValueError("La contraseña debe tener entre 8 y 64 caracteres")
        if not any(c.isupper() for c in v):
            raise ValueError("La contraseña debe contener al menos una letra mayúscula")
        if not any(c.islower() for c in v):
            raise ValueError("La contraseña debe contener al menos una letra minúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("La contraseña debe contener al menos un número")
        return v

