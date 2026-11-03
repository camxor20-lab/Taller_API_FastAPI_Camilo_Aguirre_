from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from ..models.usuario import RolUsuario


class UsuarioBase(BaseModel):
    email: EmailStr = Field(..., description="Correo electrónico único del usuario")
    nombre: str = Field(..., min_length=3, max_length=100, description="Nombre completo en formato título")

    @field_validator("email")
    @classmethod
    def formatear_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("nombre")
    @classmethod
    def validar_y_formatear_nombre(cls, v: str) -> str:
        limpio = v.strip()
        if len(limpio) < 3 or len(limpio) > 100:
            raise ValueError("El nombre debe tener entre 3 y 100 caracteres")
        return limpio.title()


class UsuarioRegistro(UsuarioBase):
    telefono: str | None = Field(
        default=None,
        pattern=r"^[0-9+ ]{7,15}$",
        description="Teléfono opcional (7 a 15 caracteres: dígitos, espacios o +)"
    )
    password: str = Field(..., min_length=8, max_length=64, description="Contraseña segura")
    confirmar_password: str = Field(..., min_length=8, max_length=64, description="Confirmación de contraseña")

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v: str | None) -> str | None:
        if v is not None:
            limpio = v.strip()
            return limpio if limpio else None
        return None

    @field_validator("password")
    @classmethod
    def validar_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 64:
            raise ValueError("La contraseña debe tener entre 8 y 64 caracteres")
        if not any(c.isupper() for c in v):
            raise ValueError("La contraseña debe contener al menos una letra mayúscula")
        if not any(c.islower() for c in v):
            raise ValueError("La contraseña debe contener al menos una letra minúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("La contraseña debe contener al menos un número")
        return v

    @model_validator(mode="after")
    def validar_contrasenas_coinciden(self):
        if self.password != self.confirmar_password:
            raise ValueError("Las contraseñas no coinciden")
        return self


class UsuarioCrear(UsuarioBase):
    rol: RolUsuario = Field(default=RolUsuario.bibliotecario, description="Rol asignado (admin o bibliotecario)")
    password: str = Field(..., min_length=8, max_length=64)

    @field_validator("password")
    @classmethod
    def validar_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 64:
            raise ValueError("La contraseña debe tener entre 8 y 64 caracteres")
        if not any(c.isupper() for c in v):
            raise ValueError("La contraseña debe contener al menos una letra mayúscula")
        if not any(c.islower() for c in v):
            raise ValueError("La contraseña debe contener al menos una letra minúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("La contraseña debe contener al menos un número")
        return v


class CambiarRol(BaseModel):
    rol: RolUsuario = Field(..., description="Nuevo rol asignado al usuario")


class CambiarActivo(BaseModel):
    activo: bool = Field(..., description="Estado activo o inactivo del usuario")


class SocioActualizarPropio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    telefono: str | None = Field(default=None, pattern=r"^[0-9+ ]{7,15}$")

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str | None) -> str | None:
        if v is not None:
            limpio = v.strip()
            if len(limpio) < 2 or len(limpio) > 100:
                raise ValueError("El nombre debe tener entre 2 y 100 caracteres")
            return limpio.title()
        return None

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v: str | None) -> str | None:
        if v is not None:
            limpio = v.strip()
            return limpio if limpio else None
        return None


class UsuarioRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nombre: str
    rol: RolUsuario
    activo: bool
    socio_id: int | None = None
    creado_en: datetime

