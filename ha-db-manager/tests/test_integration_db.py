"""Integration tests against real MySQL / PostgreSQL servers.

These tests are skipped unless ``HA_TEST_MYSQL_URL`` and ``HA_TEST_PG_URL``
environment variables are set, e.g.::

    mysql://root:secret@localhost:3307/hass?charset=utf8mb4
    postgresql://postgres:secret@localhost:5433/hass
"""
import os

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

import db
import app as app_module


def _mysql_schema():
    return [
        "CREATE TABLE states_meta (metadata_id BIGINT AUTO_INCREMENT PRIMARY KEY, entity_id VARCHAR(255) UNIQUE)",
        "CREATE TABLE states (state_id BIGINT AUTO_INCREMENT PRIMARY KEY, entity_id VARCHAR(255), metadata_id BIGINT, state VARCHAR(255), last_updated_ts DOUBLE)",
        "CREATE TABLE statistics_meta (id BIGINT AUTO_INCREMENT PRIMARY KEY, statistic_id VARCHAR(255) UNIQUE)",
        "CREATE TABLE statistics (id BIGINT AUTO_INCREMENT PRIMARY KEY, metadata_id BIGINT, start_ts DOUBLE, state VARCHAR(255))",
        "CREATE TABLE statistics_short_term (id BIGINT AUTO_INCREMENT PRIMARY KEY, metadata_id BIGINT, start_ts DOUBLE, state VARCHAR(255))",
        "CREATE TABLE event_types (event_type_id BIGINT AUTO_INCREMENT PRIMARY KEY, event_type VARCHAR(255) UNIQUE)",
        "CREATE TABLE events (event_id BIGINT AUTO_INCREMENT PRIMARY KEY, event_type_id BIGINT, event_type VARCHAR(255), time_fired_ts DOUBLE)",
    ]


def _pg_schema():
    return [
        "CREATE TABLE states_meta (metadata_id BIGSERIAL PRIMARY KEY, entity_id VARCHAR(255) UNIQUE)",
        "CREATE TABLE states (state_id BIGSERIAL PRIMARY KEY, entity_id VARCHAR(255), metadata_id BIGINT, state VARCHAR(255), last_updated_ts DOUBLE PRECISION)",
        "CREATE TABLE statistics_meta (id BIGSERIAL PRIMARY KEY, statistic_id VARCHAR(255) UNIQUE)",
        "CREATE TABLE statistics (id BIGSERIAL PRIMARY KEY, metadata_id BIGINT, start_ts DOUBLE PRECISION, state VARCHAR(255))",
        "CREATE TABLE statistics_short_term (id BIGSERIAL PRIMARY KEY, metadata_id BIGINT, start_ts DOUBLE PRECISION, state VARCHAR(255))",
        "CREATE TABLE event_types (event_type_id BIGSERIAL PRIMARY KEY, event_type VARCHAR(255) UNIQUE)",
        "CREATE TABLE events (event_id BIGSERIAL PRIMARY KEY, event_type_id BIGINT, event_type VARCHAR(255), time_fired_ts DOUBLE PRECISION)",
    ]


def _drop_statements():
    return [
        "DROP TABLE IF EXISTS states",
        "DROP TABLE IF EXISTS states_meta",
        "DROP TABLE IF EXISTS statistics",
        "DROP TABLE IF EXISTS statistics_short_term",
        "DROP TABLE IF EXISTS statistics_meta",
        "DROP TABLE IF EXISTS events",
        "DROP TABLE IF EXISTS event_types",
    ]


def _seed(b, conn):
    b.execute(conn, "INSERT INTO states_meta (entity_id) VALUES (?)", ["sensor.a"])
    b.execute(conn, "INSERT INTO states_meta (entity_id) VALUES (?)", ["sensor.b"])
    b.execute(conn, "INSERT INTO states_meta (entity_id) VALUES (?)", ["light.c"])
    b.execute(
        conn,
        "INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES (?,?,?,?)",
        ["sensor.a", 1, "1.0", 1000.0],
    )
    b.execute(
        conn,
        "INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES (?,?,?,?)",
        ["sensor.a", 1, "2.0", 1100.0],
    )
    b.execute(
        conn,
        "INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES (?,?,?,?)",
        ["sensor.b", 2, "off", 1000.0],
    )
    b.execute(
        conn,
        "INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES (?,?,?,?)",
        ["light.c", 3, "on", 900.0],
    )
    b.execute(conn, "INSERT INTO statistics_meta (statistic_id) VALUES (?)", ["sensor.a_mean"])
    b.execute(conn, "INSERT INTO statistics_meta (statistic_id) VALUES (?)", ["sensor.b_mean"])
    b.execute(
        conn,
        "INSERT INTO statistics (metadata_id, start_ts, state) VALUES (?,?,?)",
        [1, 1000.0, "1.0"],
    )
    b.execute(
        conn,
        "INSERT INTO statistics (metadata_id, start_ts, state) VALUES (?,?,?)",
        [1, 1100.0, "2.0"],
    )
    b.execute(
        conn,
        "INSERT INTO statistics (metadata_id, start_ts, state) VALUES (?,?,?)",
        [2, 1000.0, "0.5"],
    )
    b.execute(
        conn,
        "INSERT INTO statistics_short_term (metadata_id, start_ts, state) VALUES (?,?,?)",
        [1, 1000.0, "1.1"],
    )
    b.execute(conn, "INSERT INTO event_types (event_type) VALUES (?)", ["state_changed"])
    b.execute(conn, "INSERT INTO event_types (event_type) VALUES (?)", ["homeassistant_start"])
    b.execute(
        conn,
        "INSERT INTO events (event_type_id, event_type, time_fired_ts) VALUES (?,?,?)",
        [1, "state_changed", 1000.0],
    )
    b.execute(
        conn,
        "INSERT INTO events (event_type_id, event_type, time_fired_ts) VALUES (?,?,?)",
        [1, "state_changed", 1100.0],
    )


async def _make_client(url, schema, monkeypatch, tmp_path):
    backend = db.init(url)
    conn = backend.connect()
    for st in _drop_statements():
        backend.execute(conn, st)
    for st in schema():
        backend.execute(conn, st)
    _seed(backend, conn)
    conn.commit()
    conn.close()

    monkeypatch.setenv("HA_SQLITE_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setenv("HA_DISABLE_WATCH_LOOP", "1")
    app = app_module.create_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client
    await client.close()

    conn = backend.connect()
    for st in _drop_statements():
        backend.execute(conn, st)
    conn.commit()
    conn.close()


@pytest_asyncio.fixture
async def pg_client(monkeypatch, tmp_path):
    url = os.environ.get("HA_TEST_PG_URL")
    if not url:
        pytest.skip("HA_TEST_PG_URL not set")
    async for c in _make_client(url, _pg_schema, monkeypatch, tmp_path):
        yield c


@pytest_asyncio.fixture
async def mysql_client(monkeypatch, tmp_path):
    url = os.environ.get("HA_TEST_MYSQL_URL")
    if not url:
        pytest.skip("HA_TEST_MYSQL_URL not set")
    async for c in _make_client(url, _mysql_schema, monkeypatch, tmp_path):
        yield c


async def _assert_endpoints(client):
    r = await client.get("/api/tables")
    tables = await r.json()
    names = {t["name"] for t in tables}
    assert {"states", "statistics", "events", "event_types"} <= names

    r = await client.get("/api/table/states_meta", params={"counts": "1"})
    assert r.status == 200
    data = await r.json()
    by_id = {d["entity_id"]: d for d in data["rows"]}
    assert by_id["sensor.a"]["state_count"] == 2
    assert by_id["sensor.a"]["max_state_id"] == 2

    r = await client.get("/api/table/states", params={"sort": "last_updated_ts", "dir": "desc"})
    data = await r.json()
    assert data["total_rows"] == 4
    ts = [row["last_updated_ts"] for row in data["rows"]]
    assert ts == sorted(ts, reverse=True)

    r = await client.get("/api/table/states", params={"filter_col": "metadata_id", "filter_value": "1"})
    data = await r.json()
    assert data["total_rows"] == 2

    r = await client.get("/api/table/statistics_meta", params={"counts": "1"})
    data = await r.json()
    assert {d["statistic_id"]: d["stat_count"] for d in data["rows"]}["sensor.a_mean"] == 2

    r = await client.get("/api/table/statistics_short_term", params={"filter_col": "metadata_id", "filter_value": "1"})
    data = await r.json()
    assert data["total_rows"] == 1

    r = await client.get("/api/table/event_types", params={"counts": "1"})
    data = await r.json()
    assert {d["event_type"]: d["event_count"] for d in data["rows"]}["state_changed"] == 2

    r = await client.get("/api/settings")
    assert (await r.json())["watch_interval"] == 3


async def test_endpoints_on_postgres(pg_client):
    await _assert_endpoints(pg_client)


async def test_endpoints_on_mysql(mysql_client):
    await _assert_endpoints(mysql_client)


@pytest.mark.parametrize("kind", ["pg", "mysql"])
async def test_max_row_id_detects_insert(kind, monkeypatch):
    url = os.environ.get("HA_TEST_PG_URL" if kind == "pg" else "HA_TEST_MYSQL_URL")
    if not url:
        pytest.skip(f"HA_TEST_{kind.upper()}_URL not set")
    backend = db.init(url)
    conn = backend.connect()
    schema = _pg_schema if kind == "pg" else _mysql_schema
    for st in _drop_statements():
        backend.execute(conn, st)
    for st in schema():
        backend.execute(conn, st)
    _seed(backend, conn)
    conn.commit()

    before = db.max_row_id(conn, "states")
    assert before is not None
    backend.execute(
        conn,
        "INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES (?,?,?,?)",
        ["sensor.b", 2, "on", 9999.0],
    )
    conn.commit()
    after = db.max_row_id(conn, "states")
    assert after == before + 1

    conn.close()
    conn = backend.connect()
    for st in _drop_statements():
        backend.execute(conn, st)
    conn.commit()
    conn.close()
