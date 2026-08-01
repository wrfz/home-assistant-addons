import os
import sqlite3
from datetime import datetime, timezone

import pytest

import db


class TestResolveUrl:
    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("HA_DB_URL", "mysql://u:p@h/db")
        assert db.resolve_db_url() == "mysql://u:p@h/db"

    def test_config_yaml(self, monkeypatch, tmp_path):
        cfg = tmp_path / "configuration.yaml"
        cfg.write_text(
            "homeassistant:\n"
            "  name: test\n"
            "recorder:\n"
            "  db_url: 'postgresql://u:p@h:5432/homeassistant'\n"
            "  purge_days: 7\n"
        )
        monkeypatch.setenv("HA_CONFIGURATION_YAML", str(cfg))
        monkeypatch.delenv("HA_DB_URL", raising=False)
        assert db.resolve_db_url() == "postgresql://u:p@h:5432/homeassistant"

    def test_config_yaml_unquoted_with_comment(self, monkeypatch, tmp_path):
        cfg = tmp_path / "configuration.yaml"
        cfg.write_text("recorder:\n  db_url: mysql://u:p@h/db  # recorder db\n")
        monkeypatch.setenv("HA_CONFIGURATION_YAML", str(cfg))
        monkeypatch.delenv("HA_DB_URL", raising=False)
        assert db.resolve_db_url() == "mysql://u:p@h/db"

    def test_default_sqlite(self, monkeypatch):
        monkeypatch.delenv("HA_DB_URL", raising=False)
        monkeypatch.delenv("RECORDER_DB_URL", raising=False)
        monkeypatch.setenv("HA_CONFIGURATION_YAML", str("/nonexistent/configuration.yaml"))
        assert db.resolve_db_url() == "sqlite:///config/home-assistant_v2.db"


class TestParseUrl:
    def test_sqlite_abs(self):
        b = db.Backend("sqlite:////config/home-assistant_v2.db")
        assert b.kind == "sqlite"
        assert b.path_or_params == "/config/home-assistant_v2.db"

    def test_sqlite_single(self):
        b = db.Backend("sqlite:///config/db.db")
        assert b.path_or_params == "/config/db.db"

    def test_mysql_params(self):
        b = db.Backend("mysql://user:secret@dbhost:3307/hass?charset=utf8mb4")
        assert b.kind == "mysql"
        assert b.path_or_params["user"] == "user"
        assert b.path_or_params["password"] == "secret"
        assert b.path_or_params["host"] == "dbhost"
        assert b.path_or_params["port"] == 3307
        assert b.path_or_params["database"] == "hass"
        assert b.path_or_params["charset"] == "utf8mb4"

    def test_postgres(self):
        b = db.Backend("postgresql://u:p@h/db")
        assert b.kind == "postgres"

    def test_unsupported(self):
        with pytest.raises(ValueError):
            db.Backend("oracle://u:p@h/db")


class TestDialect:
    @pytest.mark.parametrize("kind", ["sqlite", "mysql", "postgres"])
    def test_quote(self, kind):
        b = db.Backend(f"{kind}://x/db") if kind != "sqlite" else db.Backend("sqlite:///x.db")
        assert b.quote("col") == ("`col`" if kind == "mysql" else '"col"')

    def test_mysql_quote_escapes(self):
        b = db.Backend("mysql://x/db")
        assert b.quote("a`b") == "`a``b`"

    def test_placeholders_sqlite(self):
        assert db.Backend("sqlite:///x.db").convert_placeholders("a=? AND b=?") == "a=? AND b=?"

    def test_placeholders_mysql(self):
        assert db.Backend("mysql://x/db").convert_placeholders("a=? AND b=?") == "a=%s AND b=%s"

    def test_placeholders_postgres(self):
        sql = db.Backend("postgresql://x/db").convert_placeholders("a=? AND b=?")
        assert sql == "a=%s AND b=%s"


class TestEpoch:
    def test_naive_datetime_assumed_utc(self):
        dt = datetime(2026, 8, 1, 12, 0, 0)  # naive
        out = db._epoch(dt)
        assert out == datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()

    def test_passthrough(self):
        assert db._epoch(42) == 42
        assert db._epoch("x") == "x"
        assert db._epoch(None) is None


class TestExecute:
    def test_returns_dicts_and_aliases(self, conn):
        rows = db.execute(conn, "SELECT COUNT(*) AS c FROM states").fetchall()
        assert rows == [{"c": 4}]

    def test_values_pass_through(self, conn):
        rows = db.execute(
            conn, "SELECT state, last_updated_ts FROM states ORDER BY state_id LIMIT 1"
        ).fetchall()
        assert rows[0]["state"] == "1.0"
        assert rows[0]["last_updated_ts"] == 1000.0

    def test_epoch_normalization_of_datetime(self):
        # datetime/Decimal handling is applied by the mysql/postgres drivers;
        # verify the conversion logic against a dict row directly.
        backend = db.get_backend()
        row = {
            "ts": datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
            "n": 5,
        }
        normalized = {k: db._epoch(v) for k, v in row.items()}
        assert isinstance(normalized["ts"], float)
        assert normalized["ts"] == datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        assert normalized["n"] == 5


class TestMaxRowId:
    def test_sqlite_uses_rowid(self, conn):
        mid = db.max_row_id(conn, "states")
        assert mid == 4

    def test_sqlite_empty_table(self, seed_db):
        c = sqlite3.connect(seed_db)
        c.row_factory = sqlite3.Row
        c.execute("CREATE TABLE empty_t (x INTEGER)")
        c.commit()
        assert db.get_backend().max_row_id(c, "empty_t") is None
        c.close()

    def test_sqlite_table_not_found(self, conn):
        assert db.max_row_id(conn, "no_such_table") is None
