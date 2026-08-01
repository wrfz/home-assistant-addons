"""Database backend abstraction for SQLite, MySQL and PostgreSQL.

The rest of the application writes plain SQL using ``?`` placeholders and
double-quoted identifiers. This module translates those to the active
dialect, normalizes values (datetimes -> epoch floats) and provides
catalog queries (tables / columns / max row id).
"""
import os
import re
import sqlite3
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

DEFAULT_SQLITE_PATH = "/config/home-assistant_v2.db"


def resolve_db_url():
    """Determine the recorder DB URL.

    Priority: env var ``HA_DB_URL`` > HA ``configuration.yaml`` recorder
    ``db_url`` > default SQLite file.
    """
    url = os.environ.get("HA_DB_URL") or os.environ.get("RECORDER_DB_URL")
    if url:
        return url
    url = _db_url_from_config_yaml()
    if url:
        return url
    return f"sqlite://{DEFAULT_SQLITE_PATH}"


def _db_url_from_config_yaml():
    """Extract ``recorder.db_url`` from Home Assistant configuration.yaml.

    Deliberately avoids PyYAML (painful on Alpine) and handles the common
    single-line cases including quoted values.
    """
    path = os.environ.get("HA_CONFIGURATION_YAML", "/config/configuration.yaml")
    try:
        text = Path(path).read_text()
    except Exception:
        return None
    lines = text.splitlines()
    in_recorder = False
    for line in lines:
        if not in_recorder:
            if re.match(r"^recorder\s*:\s*$", line):
                in_recorder = True
            continue
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", "-")) and not line[:1].isspace():
            in_recorder = False
            continue
        m = re.match(r"^[ \t]*db_url[ \t]*:[ \t]*(.*)$", line)
        if not m:
            continue
        value = m.group(1).strip()
        if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
            value = value[1:-1]
        else:
            value = value.split("#", 1)[0].strip()
        if value:
            return value
        return None
    return None


def _redact(url):
    parts = urlsplit(url)
    if not parts.password:
        return url
    netloc = parts.hostname or ""
    if parts.port:
        netloc += f":{parts.port}"
    if parts.username:
        netloc = f"{parts.username}:****@{netloc}"
    return url.replace(parts.netloc, netloc)


def _parse_url(url):
    scheme = url.split(":", 1)[0].lower()
    if scheme == "sqlite":
        rest = url.split("://", 1)[1]
        if rest.startswith("//"):
            rest = "/" + rest[2:]
        return "sqlite", rest
    if scheme in ("mysql", "mariadb", "mysql+pymysql"):
        parts = urlsplit(url)
        params = {
            "port": parts.port or 3306,
            "database": unquote(parts.path.lstrip("/") or ""),
        }
        if parts.hostname:
            params["host"] = parts.hostname
        if parts.username:
            params["user"] = unquote(parts.username)
        if parts.password:
            params["password"] = unquote(parts.password)
        for k, v in parse_qs(parts.query).items():
            params[k] = v[0]
        return "mysql", params
    if scheme in ("postgres", "postgresql", "postgres+psycopg", "postgresql+psycopg"):
        return "postgres", url
    raise ValueError(f"Unsupported database URL scheme: {scheme}")


def _epoch(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
    if isinstance(value, date):
        value = datetime.combine(value, time.min)
        return value.replace(tzinfo=timezone.utc).timestamp()
    if isinstance(value, Decimal):
        return float(value)
    return value


class Result:
    """Cursor-like result object with dict rows."""

    def __init__(self, columns, rows):
        self.columns = columns
        self.rows = rows
        self.description = [(c,) for c in columns]

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Backend:
    def __init__(self, url):
        self.url = url
        self.kind, self.path_or_params = _parse_url(url)

    def display_name(self):
        if self.kind == "sqlite":
            return self.path_or_params
        return _redact(self.url)

    def connect(self):
        if self.kind == "sqlite":
            conn = sqlite3.connect(self.path_or_params)
            conn.row_factory = sqlite3.Row
            return conn
        if self.kind == "mysql":
            try:
                import pymysql
            except ImportError as e:
                raise RuntimeError("MySQL support requires PyMySQL") from e
            kw = dict(self.path_or_params)
            kw.setdefault("charset", "utf8mb4")
            kw.setdefault("connect_timeout", 10)
            kw.setdefault("cursorclass", pymysql.cursors.DictCursor)
            return pymysql.connect(**kw)
        if self.kind == "postgres":
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as e:
                raise RuntimeError("PostgreSQL support requires psycopg") from e
            return psycopg.connect(self.url, row_factory=dict_row)
        raise RuntimeError(f"Unsupported database backend: {self.kind}")

    def quote(self, name):
        if self.kind == "mysql":
            return "`" + name.replace("`", "``") + "`"
        return '"' + name.replace('"', '""') + '"'

    def convert_placeholders(self, sql):
        """Translate ``?`` placeholders to the active dialect.

        SQLite uses ``?``; PyMySQL and psycopg (v3) both use ``%s``.
        """
        if self.kind == "sqlite":
            return sql
        return sql.replace("?", "%s")

    def execute(self, conn, sql, params=None):
        params = list(params) if params else []
        sql = self.convert_placeholders(sql)
        if self.kind == "sqlite":
            cur = conn.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            columns = [d[0] for d in cur.description] if cur.description else []
        elif self.kind == "mysql":
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            columns = [d[0] for d in cur.description] if cur.description else []
            cur.close()
        elif self.kind == "postgres":
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if cur.description is None:
                    return Result([], [])
                rows = [dict(r) for r in cur.fetchall()]
                columns = [d[0] for d in cur.description] if cur.description else []
        else:
            raise RuntimeError(f"Unsupported backend: {self.kind}")
        return Result(columns, [{k: _epoch(v) for k, v in r.items()} for r in rows])

    def list_tables(self, conn):
        if self.kind == "sqlite":
            rows = self.execute(
                conn,
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
            ).fetchall()
            return [r["name"] for r in rows]
        if self.kind == "mysql":
            rows = self.execute(
                conn,
                "SELECT TABLE_NAME AS name FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME",
            ).fetchall()
            return [r["name"] for r in rows]
        rows = self.execute(
            conn,
            "SELECT tablename AS name FROM pg_tables "
            "WHERE schemaname = 'public' ORDER BY tablename",
        ).fetchall()
        return [r["name"] for r in rows]

    def table_columns(self, conn, table):
        if self.kind == "sqlite":
            rows = self.execute(
                conn, f"PRAGMA table_info({self.quote(table)})"
            ).fetchall()
            return {r["name"] for r in rows}
        if self.kind == "mysql":
            rows = self.execute(
                conn,
                "SELECT COLUMN_NAME AS name FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? "
                "ORDER BY ORDINAL_POSITION",
                (table,),
            ).fetchall()
            return {r["name"] for r in rows}
        rows = self.execute(
            conn,
            "SELECT column_name AS name FROM information_schema.COLUMNS "
            "WHERE table_schema = 'public' AND table_name = ? "
            "ORDER BY ordinal_position",
            (table,),
        ).fetchall()
        return {r["name"] for r in rows}

    def max_row_id(self, conn, table):
        """Return a monotonic insert-detection value for a generic table.

        SQLite: ``MAX(rowid)``. MySQL: max of the single ``auto_increment``
        column. PostgreSQL: max of the single integer primary key column.
        Returns None when no usable column exists (no change detection).
        """
        if self.kind == "sqlite":
            try:
                row = self.execute(
                    conn, f"SELECT MAX(rowid) AS m FROM {self.quote(table)}"
                ).fetchone()
            except sqlite3.OperationalError:
                return None
            return row["m"] if row and row["m"] is not None else None
        if self.kind == "mysql":
            col = self.execute(
                conn,
                "SELECT COLUMN_NAME AS c FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? "
                "AND EXTRA = 'auto_increment'",
                (table,),
            ).fetchone()
            if not col:
                return None
            row = self.execute(
                conn,
                f'SELECT MAX({self.quote(col["c"])}) AS m FROM {self.quote(table)}',
            ).fetchone()
            return row["m"] if row and row["m"] is not None else None
        pk = self.execute(
            conn,
            "SELECT a.attname AS c FROM pg_index i "
            "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
            "WHERE i.indrelid = ?::regclass AND i.indisprimary "
            "AND a.atttypid IN (20, 21, 23)",
            (table,),
        ).fetchall()
        if len(pk) != 1:
            return None
        row = self.execute(
            conn,
            f'SELECT MAX({self.quote(pk[0]["c"])}) AS m FROM {self.quote(table)}',
        ).fetchone()
        return row["m"] if row and row["m"] is not None else None


_backend = None


def init(url=None):
    global _backend
    url = url or resolve_db_url()
    _backend = Backend(url)
    return _backend


def get_backend():
    global _backend
    if _backend is None:
        init()
    return _backend


def get_connection():
    return get_backend().connect()


def execute(conn, sql, params=None):
    return get_backend().execute(conn, sql, params)


def quote(name):
    return get_backend().quote(name)


def list_tables(conn):
    return get_backend().list_tables(conn)


def table_columns(conn, table):
    return get_backend().table_columns(conn, table)


def max_row_id(conn, table):
    return get_backend().max_row_id(conn, table)
