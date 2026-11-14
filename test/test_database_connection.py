"""Configuracion, ciclo de vida y fallos; no acceden a una BD real."""
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import config.settings as settings_module
from config.settings import DatabaseSettings, load_settings
import database.connection as connection_module
from database.connection import DatabaseConnection, DatabaseConnectionError
from scripts import check_db_connection as cli


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    import os

    for key in list(os.environ):
        if key.upper().startswith("DB_") or key.upper() in {"APP_ENV", "APP_TIMEZONE"}:
            monkeypatch.delenv(key)


@pytest.fixture
def settings():
    return DatabaseSettings(_env_file=None, db_name="test_database")


class FakeSqlError(Exception):
    def __init__(self, number, message="provider detail must never be printed"):
        super().__init__(message)
        self.Number = number


@pytest.fixture
def driver(monkeypatch):
    state = SimpleNamespace(connections=[], commands=[], cleared=[], open_error=None,
                            query_error=None, scalar=1)

    class Builder:
        @property
        def ConnectionString(self):
            # No cadena real ni conexion: se conserva la configuracion del doble.
            return dict(vars(self))

    class Command:
        disposed = False

        def ExecuteScalar(self):
            if state.query_error is not None:
                raise state.query_error
            return state.scalar

        def Dispose(self):
            self.disposed = True

    class Connection:
        def __init__(self, options):
            self.options = options
            self.disposed = False
            self.opened = False
            state.connections.append(self)

        def Open(self):
            if state.open_error is not None:
                raise state.open_error
            self.opened = True

        def CreateCommand(self):
            assert self.opened
            command = Command()
            state.commands.append(command)
            return command

        def Dispose(self):
            self.disposed = True

        @staticmethod
        def ClearPool(connection):
            state.cleared.append(connection)

    provider = SimpleNamespace(SqlConnectionStringBuilder=Builder, SqlConnection=Connection,
                               SqlException=FakeSqlError,
                               ApplicationIntent=SimpleNamespace(ReadOnly="ReadOnly"))
    monkeypatch.setattr(connection_module, "_load_sql_client", lambda: provider)
    return state


def test_env_is_independent_of_workdir_and_os_overrides_file(tmp_path, monkeypatch):
    env = tmp_path / "laboratorio.env"
    env.write_text("DB_NAME=fixture\nDB_HOST=from_file\nDB_PORT=1433\n"
                   "DB_ENCRYPT=true\nDB_ECHO=false\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(settings_module, "DEFAULT_ENV_FILE", env)
    monkeypatch.setenv("DB_HOST", "from_environment")
    loaded = load_settings()
    assert loaded.db_host == "from_environment"
    assert loaded.db_name == "fixture"
    assert loaded.db_encrypt is True and loaded.db_echo is False


@pytest.mark.parametrize("overrides", [
    {"db_port": 0}, {"db_port": 65536}, {"db_connect_timeout_seconds": 0},
    {"db_query_timeout_seconds": 0}, {"db_auth": "sql"},
    {"db_auth": "sql", "db_user": "fake_user"}, {"db_encrypt": False},
    {"db_echo": True}, {"app_env": "production", "db_trust_server_certificate": True},
])
def test_invalid_configuration_is_rejected(overrides):
    with pytest.raises(ValidationError):
        DatabaseSettings(_env_file=None, db_name="fixture", **overrides)


def test_windows_identity_and_only_select_1(settings, driver):
    with DatabaseConnection(settings) as database:
        assert database.check_connection().status == "OK"
        opened = [c for c in driver.connections if c.opened]
        assert len(opened) == 1
        assert opened[0].options["IntegratedSecurity"] is True
        assert "Password" not in opened[0].options
        assert opened[0].options["ApplicationIntent"] == "ReadOnly"
        assert opened[0].options["MaxPoolSize"] == 5
        assert driver.commands[0].CommandText == "SELECT 1"
        assert driver.commands[0].CommandTimeout == settings.db_query_timeout_seconds
        assert driver.commands[0].disposed and opened[0].disposed
    assert all(c.disposed for c in driver.connections)
    assert len(driver.cleared) == 1


def test_sql_credentials_are_not_in_settings_repr(driver):
    secret = "synthetic;secret#with}punctuation"
    settings = DatabaseSettings(_env_file=None, db_name="fixture", db_auth="sql",
                                db_user="test_reader", db_password=secret)
    assert secret not in repr(settings)
    with DatabaseConnection(settings) as database:
        database.check_connection()
    opened = next(c for c in driver.connections if c.opened)
    assert opened.options["IntegratedSecurity"] is False
    assert opened.options["Password"] == secret
    assert opened.options["PersistSecurityInfo"] is False


@pytest.mark.parametrize("number,code", [(-2, "DB_TIMEOUT"), (18456, "DB_AUTH_FAILED"),
                                       (4060, "DB_ACCESS_FAILED"), (53, "DB_UNREACHABLE"),
                                       (9999, "DB_CONNECTION_FAILED")])
def test_connection_errors_are_sanitized_and_closed(settings, driver, number, code):
    secret = "synthetic-password-in-provider-error"
    driver.open_error = FakeSqlError(number, secret)
    with pytest.raises(DatabaseConnectionError) as error:
        with DatabaseConnection(settings) as database:
            database.check_connection()
    assert error.value.code == code
    assert secret not in str(error.value)
    assert all(c.disposed for c in driver.connections)
    assert len(driver.cleared) == 1
    assert not driver.commands


def test_query_error_releases_command_and_connection(settings, driver):
    driver.query_error = FakeSqlError(-2)
    with pytest.raises(DatabaseConnectionError, match="tiempo de espera"):
        with DatabaseConnection(settings) as database:
            database.check_connection()
    assert driver.commands[0].disposed
    assert all(c.disposed for c in driver.connections)


def test_unexpected_result_is_not_reported_as_ok(settings, driver):
    driver.scalar = 0
    with pytest.raises(DatabaseConnectionError) as error:
        with DatabaseConnection(settings) as database:
            database.check_connection()
    assert error.value.code == "DB_UNEXPECTED_RESULT"
    assert driver.commands[0].disposed


def test_close_is_idempotent_and_manager_cannot_be_reused(settings, driver):
    database = DatabaseConnection(settings)
    database.check_connection()
    database.close()
    database.close()
    assert len(driver.cleared) == 1
    with pytest.raises(DatabaseConnectionError) as error:
        database.check_connection()
    assert error.value.code == "DB_CLOSED"


def test_cli_success_and_failure_exit_codes(settings, driver, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_settings", lambda _: settings)
    assert cli.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "OK", "database": "connected"}
    driver.open_error = FakeSqlError(18456, "synthetic-password-do-not-log")
    assert cli.main(["--json"]) == 1
    output = capsys.readouterr().out
    assert "synthetic-password-do-not-log" not in output
    assert json.loads(output)["code"] == "DB_AUTH_FAILED"


def test_cli_invalid_config_and_missing_file_do_not_attempt_connection(tmp_path, driver, capsys):
    env = tmp_path / "bad.env"
    env.write_text("DB_NAME=fixture\nDB_PORT=synthetic-secret-value\n", encoding="utf-8")
    assert cli.main(["--env-file", str(env), "--json"]) == 2
    output = capsys.readouterr().out
    assert "synthetic-secret-value" not in output
    assert json.loads(output)["code"] == "CONFIG_ERROR"
    assert cli.main(["--env-file", str(tmp_path / "missing.env")]) == 2
    assert "CONFIG_ERROR" in capsys.readouterr().err
    assert driver.connections == []


def test_missing_provider_reports_safe_error(settings, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_settings", lambda _: settings)
    monkeypatch.setattr(connection_module.sys, "platform", "unsupported")
    assert cli.main(["--json"]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "DRIVER_UNAVAILABLE"
