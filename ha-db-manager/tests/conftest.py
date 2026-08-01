import os
import sqlite3
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HA_STATIC_DIR", str(_ROOT / "static"))
os.environ.setdefault("HA_CONFIG_YAML", str(_ROOT / "config.yaml"))

import db
import app as app_module

SCHEMA = (Path(__file__).parent / "schema.sqlite.sql").read_text()


def build_db(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def seed(conn):
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO states_meta (entity_id) VALUES (?)",
        [("sensor.a",), ("sensor.b",), ("light.c",)],
    )
    cur.executemany(
        "INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES (?,?,?,?)",
        [
            ("sensor.a", 1, "1.0", 1000.0),
            ("sensor.a", 1, "2.0", 1100.0),
            ("sensor.b", 2, "off", 1000.0),
            ("light.c", 3, "on", 900.0),
        ],
    )
    cur.executemany(
        "INSERT INTO statistics_meta (statistic_id) VALUES (?)",
        [("sensor.a_mean",), ("sensor.b_mean",)],
    )
    cur.executemany(
        "INSERT INTO statistics (metadata_id, start_ts, state) VALUES (?,?,?)",
        [(1, 1000.0, "1.0"), (1, 1100.0, "2.0"), (2, 1000.0, "0.5")],
    )
    cur.executemany(
        "INSERT INTO statistics_short_term (metadata_id, start_ts, state) VALUES (?,?,?)",
        [(1, 1000.0, "1.1")],
    )
    cur.executemany(
        "INSERT INTO event_types (event_type) VALUES (?)",
        [("state_changed",), ("homeassistant_start",)],
    )
    cur.executemany(
        "INSERT INTO events (event_type_id, event_type, time_fired_ts) VALUES (?,?,?)",
        [
            (1, "state_changed", 1000.0),
            (1, "state_changed", 1100.0),
            (2, "homeassistant_start", 900.0),
        ],
    )
    conn.commit()


@pytest.fixture
def seed_db(tmp_path):
    path = tmp_path / "test.db"
    conn = build_db(str(path))
    seed(conn)
    conn.close()
    return str(path)


@pytest_asyncio.fixture
async def client(seed_db, tmp_path, monkeypatch):
    monkeypatch.setenv("HA_DB_URL", f"sqlite:///{seed_db}")
    monkeypatch.setenv("HA_SQLITE_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setenv("HA_DISABLE_WATCH_LOOP", "1")
    db.init(f"sqlite:///{seed_db}")
    app = app_module.create_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client
    await client.close()


@pytest.fixture
def conn(seed_db):
    db.init(f"sqlite:///{seed_db}")
    c = sqlite3.connect(seed_db)
    c.row_factory = sqlite3.Row
    yield c
    c.close()
