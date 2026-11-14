
from contextlib import contextmanager
from dataclasses import dataclass
import sys
from typing import Any, Iterator

from config.settings import DatabaseSettings


class DatabaseConnectionError(RuntimeError):
    """Error seguro para consola o un futuro endpoint, sin texto del proveedor."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ConnectionCheck:
    status: str = "OK"
    database: str = "connected"


def _load_sql_client() -> Any:
    if sys.platform != "win32":
        raise DatabaseConnectionError(
            "DRIVER_UNAVAILABLE", "Este adaptador requiere Windows y .NET Framework."
        )
    try:
        from pythonnet import load

        load("netfx")
        import clr

        clr.AddReference("System.Data")
        from System.Data import SqlClient

        return SqlClient
    except Exception:
        raise DatabaseConnectionError(
            "DRIVER_UNAVAILABLE",
            "No se pudo cargar el proveedor. Instale requirements-database.txt "
            "y compruebe .NET Framework 4.7.2 o posterior.",
        ) from None


def _connection_error(exc: Exception) -> DatabaseConnectionError:
    number = getattr(exc, "Number", None)
    if number == -2:
        code, action = "DB_TIMEOUT", "Se agoto el tiempo de espera. Revise red y servidor."
    elif number in (18456, 18452):
        code, action = "DB_AUTH_FAILED", "Revise la autenticacion y los permisos del usuario."
    elif number in (4060, 916):
        code, action = "DB_ACCESS_FAILED", "Revise el nombre de la base y el permiso de acceso."
    elif number in (53, 2, 26, 40, 10060, 10061, 11001):
        code, action = "DB_UNREACHABLE", "Revise DB_HOST, DB_PORT y el servicio SQL Server."
    else:
        code = "DB_CONNECTION_FAILED"
        action = "Revise servidor, autenticacion y certificado; consulte docs/conexion_bd.md."
    return DatabaseConnectionError(code, action)


class DatabaseConnection:
    """Crea conexiones por uso; .NET administra el pool limitado por configuracion.

    ApplicationIntent=ReadOnly expresa la intencion del cliente, pero NO cambia
    los permisos del usuario. La unica consulta de check_connection es SELECT 1.
    """

    def __init__(self, settings: DatabaseSettings):
        self.settings = settings
        self._driver: Any = None
        self._pool_key: Any = None
        self._closed = False

    def _get_driver(self) -> Any:
        if self._closed:
            raise DatabaseConnectionError("DB_CLOSED", "El gestor de conexion ya fue cerrado.")
        if self._driver is None:
            self._driver = _load_sql_client()
        return self._driver

    def _new_connection(self) -> Any:
        driver = self._get_driver()
        settings = self.settings
        builder = driver.SqlConnectionStringBuilder()
        # El builder escapa valores y evita concatenar credenciales en SQL/cadenas.
        builder.DataSource = f"tcp:{settings.db_host},{settings.db_port}"
        builder.InitialCatalog = settings.db_name
        builder.IntegratedSecurity = settings.db_auth == "windows"
        if settings.db_auth == "sql":
            builder.UserID = settings.db_user
            builder.Password = settings.db_password.get_secret_value()
        builder.Encrypt = settings.db_encrypt
        builder.TrustServerCertificate = settings.db_trust_server_certificate
        builder.PersistSecurityInfo = False
        builder.ConnectTimeout = settings.db_connect_timeout_seconds
        builder.ConnectRetryCount = 0
        builder.Pooling = True
        builder.MinPoolSize = 0
        builder.MaxPoolSize = settings.db_pool_size + settings.db_max_overflow
        builder.ApplicationIntent = driver.ApplicationIntent.ReadOnly
        builder.ApplicationName = "UPC-Risk-Connection-Check"
        if self._pool_key is None:
            # Conexion sin abrir que conserva la clave del pool para su cierre.
            self._pool_key = driver.SqlConnection(builder.ConnectionString)
        return driver.SqlConnection(builder.ConnectionString)

    @contextmanager
    def connection(self) -> Iterator[Any]:
        """Entrega una conexion abierta y la libera incluso ante errores."""
        driver = self._get_driver()
        connection = self._new_connection()
        try:
            connection.Open()
            yield connection
        except driver.SqlException as exc:
            raise _connection_error(exc) from None
        finally:
            connection.Dispose()

    def check_connection(self) -> ConnectionCheck:
        """Verifica autenticacion, acceso a la base y ejecucion real de SELECT 1."""
        with self.connection() as connection:
            command = connection.CreateCommand()
            try:
                command.CommandTimeout = self.settings.db_query_timeout_seconds
                command.CommandText = "SELECT 1"
                if command.ExecuteScalar() != 1:
                    raise DatabaseConnectionError(
                        "DB_UNEXPECTED_RESULT", "La consulta de verificacion no devolvio 1."
                    )
            finally:
                command.Dispose()
        return ConnectionCheck()

    def close(self) -> None:
        """Libera el pool de esta configuracion, sin afectar otros pools."""
        if self._closed:
            return
        try:
            if self._pool_key is not None:
                self._driver.SqlConnection.ClearPool(self._pool_key)
        finally:
            if self._pool_key is not None:
                self._pool_key.Dispose()
            self._closed = True

    def __enter__(self) -> "DatabaseConnection":
        self._get_driver()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()
