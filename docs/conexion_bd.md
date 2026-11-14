# Validacion de la conexion a SQL Server

Este primer incremento carga la configuracion, abre una conexion a la base
indicada, ejecuta `SELECT 1` y devuelve `OK` solo si esa consulta devuelve 1.
No crea endpoints, tablas ni usuarios; no entrena modelos ni modifica datos.

## Archivos

| Archivo | Responsabilidad |
|---|---|
| `.env` | Variables locales; excluido de Git. |
| `.env.example` | Plantilla sin credenciales para otro equipo. |
| `config/settings.py` | Carga y validacion de configuracion. |
| `database/connection.py` | Clase `DatabaseConnection`, conexiones, pool y errores. |
| `scripts/check_db_connection.py` | Comprobacion por consola y codigo de salida. |
| `requirements-database.txt` | Dependencias del adaptador, separadas del entrenamiento. |

## Instalacion y ejecucion

Requiere Windows, Python 3.12 y .NET Framework 4.7.2 o posterior. Desde la raiz
del proyecto, en PowerShell:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements-database.txt
& .\.venv\Scripts\python.exe -m scripts.check_db_connection
```

Salida correcta:

```text
OK: conexion establecida con la base de datos (SELECT 1 correcto).
```

Tambien se puede ejecutar el archivo directamente o pedir un resultado JSON:

```powershell
& .\.venv\Scripts\python.exe scripts/check_db_connection.py --json
```

```json
{"status": "OK", "database": "connected"}
```

Codigos de salida: `0` conexion correcta; `1` error de conexion/proveedor;
`2` configuracion o argumentos invalidos. Un error no devuelve `OK`.

En PyCharm, usar el interprete `.venv\Scripts\python.exe` y el script
`scripts/check_db_connection.py`. El `.env` se busca junto a la raiz del
proyecto, independientemente del directorio de trabajo.

## Configuracion comprobada en esta laptop

La instancia es `localhost\SQLEXPRESS`, con TCP en el puerto 1433 y base
`upc_risk_model_db`. El archivo `.env` usa `DB_HOST=localhost`, `DB_PORT=1433`
y `DB_AUTH=windows`: el proceso se autentica con la sesion de Windows que lo
ejecuta. No usa la cadena anterior de Azure ni requiere guardar una contrasena.

El certificado del laboratorio no es confiable para Windows. Por eso el `.env`
local activa explicitamente `DB_TRUST_SERVER_CERTIFICATE=true` y conserva
`DB_ENCRYPT=true`. La plantilla mantiene la validacion de certificados activa.
Para entornos con certificado confiable usar `DB_TRUST_SERVER_CERTIFICATE=false`.
La configuracion rechaza desactivar el cifrado o aceptar certificados sin
validar cuando `APP_ENV=production`.

Las variables del entorno tienen prioridad sobre `.env`. Para usar otro archivo:

```powershell
& .\.venv\Scripts\python.exe -m scripts.check_db_connection --env-file C:\ruta\laboratorio.env
```

`DB_AUTH=sql` permite una cuenta SQL existente: configurar `DB_USER` y
`DB_PASSWORD` en el archivo local. Los valores con `#` deben ir entre comillas
en `.env`. El programa no cambia el modo de autenticacion del servidor ni crea
cuentas. `DB_SCHEMA` queda disponible para futuras consultas; `SELECT 1` no
comprueba permisos sobre tablas.

## Gestion de conexiones y limites

```python
from config.settings import load_settings
from database.connection import DatabaseConnection

with DatabaseConnection(load_settings()) as database:
    result = database.check_connection()
    print(result.status)
```

El proveedor .NET reutiliza conexiones mediante su pool. El limite total es
`DB_POOL_SIZE + DB_MAX_OVERFLOW`, con minimo cero. Cada uso libera su conexion;
al salir del gestor se limpia el pool asociado a esa configuracion. Hay limites
independientes para conectar y ejecutar la consulta; no se reintenta
automaticamente un fallo. No se imprimen cadenas, credenciales ni excepciones
originales del proveedor.

Se usa `ApplicationIntent=ReadOnly`, que expresa intencion, pero **no impone
permisos de solo lectura**. La comprobacion ejecuta exclusivamente `SELECT 1`;
la identidad Windows conserva sus permisos existentes. Para una cuenta de
servicio futura se deben conceder solo los permisos necesarios desde SQL Server.

Se eligio `System.Data.SqlClient` con `pythonnet` porque la conexion .NET ya se
comprobo en este equipo, ODBC 18 no esta instalado y el controlador antiguo
`SQL Server` falla al negociar SSL. Es un adaptador inicial para el laboratorio
Windows. Una futura migracion a SQLAlchemy/ODBC 18 o Microsoft.Data.SqlClient
requerira instalar y validar ese proveedor; no se presupone que ya existe.

Referencias: [Python.NET](https://pythonnet.github.io/pythonnet/python.html),
[constructor de cadenas](https://learn.microsoft.com/en-us/dotnet/api/system.data.sqlclient.sqlconnectionstringbuilder?view=netframework-4.8.1)
y [pool de conexiones](https://learn.microsoft.com/en-us/dotnet/framework/data/adonet/sql-server-connection-pooling).

## Errores y alcance de la prueba

| Codigo | Que revisar |
|---|---|
| `CONFIG_ERROR` | Archivo, campos obligatorios, puerto, timeouts y modo de autenticacion. |
| `DRIVER_UNAVAILABLE` | Dependencias Python, Windows y .NET Framework. |
| `DB_TIMEOUT` / `DB_UNREACHABLE` | Servicio, host, puerto y acceso de red. |
| `DB_AUTH_FAILED` / `DB_ACCESS_FAILED` | Identidad del proceso y acceso a la base indicada. |
| `DB_CONNECTION_FAILED` | Autenticacion, certificado o conectividad; no se publica el detalle sensible. |

La IP Tailscale `100.80.131.49` pertenece a esta misma laptop. El puerto
respondio, pero la autenticacion Windows por esa IP produjo un error SSPI.
La configuracion local funcional usa `localhost`; no acredita acceso desde
otro equipo por Tailscale. Tampoco valida calidad de datos, etiquetado o modelos.

Las pruebas de `test/test_database_connection.py` usan dobles de prueba y no
necesitan SQL Server, credenciales ni datos reales:

```powershell
& .\.venv\Scripts\python.exe -m pytest test/test_database_connection.py
```
