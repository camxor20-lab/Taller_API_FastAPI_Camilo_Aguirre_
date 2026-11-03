from functools import lru_cache
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    database_url: str
    test_database_url: str = Field(
        default="postgresql+psycopg://postgres:1234@localhost:5432/biblioteca_test"
    )
    secret_key: str = Field(..., min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    environment: Literal["dev", "test", "prod"] = "dev"

    @model_validator(mode="after")
    def validar_cors_prod(self) -> "Settings":
        if self.environment == "prod" and "*" in self.cors_origins:
            raise ValueError("No se permite '*' en cors_origins en entorno de producción")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

