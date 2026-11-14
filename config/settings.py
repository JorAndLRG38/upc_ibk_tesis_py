"""Carga .env desde la raiz del proyecto y valida la conexion a SQL Server."""
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        hide_input_in_errors=True,
        str_strip_whitespace=True,
        frozen=True,
    )

    app_env: Literal["local", "test", "lab", "production"] = "local"
    app_timezone: str = "America/Lima"
    db_dialect: Literal["mssql"] = "mssql"
    db_driver: Literal["System.Data.SqlClient"] = "System.Data.SqlClient"
    db_host: str = Field(default="localhost", min_length=1)
    db_port: int = Field(default=1433, ge=1, le=65535)
    db_name: str = Field(min_length=1)
    db_schema: str = Field(default="dbo", min_length=1)
    db_auth: Literal["windows", "sql"] = "windows"
    db_user: str = Field(default="", repr=False)
    db_password: SecretStr = Field(default_factory=lambda: SecretStr(""), repr=False)
    db_encrypt: bool = True
    db_trust_server_certificate: bool = False
    db_connect_timeout_seconds: int = Field(default=10, ge=1, le=120)
    db_query_timeout_seconds: int = Field(default=10, ge=1, le=120)
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=0, ge=0, le=50)
    db_echo: bool = False

    @model_validator(mode="after")
    def validate_connection_options(self) -> "DatabaseSettings":
        if not self.db_encrypt:
            raise ValueError("La conexion requiere DB_ENCRYPT=true")
        if self.db_echo:
            raise ValueError("DB_ECHO debe ser false para no exponer datos de conexion")
        if self.db_auth == "sql" and (
            not self.db_user or not self.db_password.get_secret_value()
        ):
            raise ValueError("DB_AUTH=sql requiere DB_USER y DB_PASSWORD")
        if self.app_env == "production" and self.db_trust_server_certificate:
            raise ValueError("Produccion requiere validar el certificado del servidor")
        return self


def load_settings(env_file: str | Path | None = None) -> DatabaseSettings:
    """Las variables de entorno prevalecen sobre el archivo seleccionado."""
    path = Path(env_file).resolve() if env_file is not None else DEFAULT_ENV_FILE
    return DatabaseSettings(_env_file=path)
