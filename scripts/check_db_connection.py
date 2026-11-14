"""Comprueba SQL Server sin modificar datos. Ejecutable como modulo o archivo."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError

from config.settings import load_settings
from database.connection import DatabaseConnection, DatabaseConnectionError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validar conexion a SQL Server con SELECT 1")
    parser.add_argument("--env-file", type=Path, help="Archivo .env alternativo")
    parser.add_argument("--json", action="store_true", help="Mostrar resultado en JSON")
    args = parser.parse_args(argv)
    result: dict
    exit_code = 0
    try:
        if args.env_file is not None and not args.env_file.is_file():
            raise FileNotFoundError
        settings = load_settings(args.env_file)
        with DatabaseConnection(settings) as database:
            result = asdict(database.check_connection())
    except FileNotFoundError:
        exit_code = 2
        result = {"status": "ERROR", "code": "CONFIG_ERROR",
                  "message": "No existe el archivo indicado en --env-file."}
    except ValidationError as exc:
        exit_code = 2
        fields = sorted({".".join(map(str, e["loc"])) or "configuracion"
                         for e in exc.errors(include_input=False, include_context=False)})
        result = {"status": "ERROR", "code": "CONFIG_ERROR",
                  "message": "Revise las variables de conexion: " + ", ".join(fields)}
    except DatabaseConnectionError as exc:
        exit_code = 1
        result = {"status": "ERROR", "code": exc.code, "message": str(exc)}
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    elif exit_code == 0:
        print("OK: conexion establecida con la base de datos (SELECT 1 correcto).")
    else:
        print(f"ERROR [{result['code']}]: {result['message']}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
