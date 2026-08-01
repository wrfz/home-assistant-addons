import sqlite3

import db
import app as app_module

from .conftest import build_db, seed


def test_view_key_dedup():
    a = {"kind": "usage", "table": "states"}
    b = {"table": "states", "kind": "usage"}
    assert app_module.view_key(a) == app_module.view_key(b)


def test_max_id_usage(conn):
    spec = {"kind": "usage", "table": "states"}
    assert app_module.max_id(conn, spec) == 4
    spec_stats = {"kind": "usage", "table": "statistics"}
    assert app_module.max_id(conn, spec_stats) == 3
    spec_short = {"kind": "usage", "table": "statistics_short_term"}
    assert app_module.max_id(conn, spec_short) == 1
    spec_events = {"kind": "usage", "table": "events"}
    assert app_module.max_id(conn, spec_events) == 3


def test_max_id_statistic_short_term(conn):
    assert app_module.max_id(conn, {"kind": "statistic", "table": "statistics", "id": "sensor.a_mean"}) == 2
    assert app_module.max_id(conn, {"kind": "statistic", "table": "statistics_short_term", "id": "sensor.a_mean"}) == 1


def test_max_id_entity(conn):
    assert app_module.max_id(conn, {"kind": "entity", "id": "sensor.a"}) == 2


def test_max_id_table_uses_rowid(conn):
    assert app_module.max_id(conn, {"kind": "table", "table": "states"}) == 4


def test_page_signature_stable_and_changes(tmp_path):
    path = tmp_path / "watch.db"
    c = build_db(str(path))
    seed(c)
    spec = {"kind": "table", "table": "statistics", "page": 1, "page_size": 100}
    sig1 = app_module.page_signature(c, spec)
    c.execute(
        "INSERT INTO statistics (metadata_id, start_ts, state) VALUES (?,?,?)",
        (1, 2000.0, "9.0"),
    )
    c.commit()
    sig2 = app_module.page_signature(c, spec)
    assert sig1 != sig2
    c.close()


def test_page_signature_none_for_usage(conn):
    assert app_module.page_signature(conn, {"kind": "usage", "table": "states"}) is None


def test_check_view_changed_first_false_then_true(tmp_path):
    path = tmp_path / "watch.db"
    c = build_db(str(path))
    seed(c)
    spec = {"kind": "usage", "table": "states"}
    state = {"max_id": None, "sig": None}
    assert app_module.check_view_changed(c, spec, state) is False
    c.execute(
        "INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES (?,?,?,?)",
        ("sensor.b", 2, "on", 9999.0),
    )
    c.commit()
    assert app_module.check_view_changed(c, spec, state) is True
    assert app_module.check_view_changed(c, spec, state) is False
    c.close()


def test_check_view_changed_stats_uses_signature(tmp_path):
    path = tmp_path / "watch.db"
    c = build_db(str(path))
    seed(c)
    spec = {"kind": "table", "table": "statistics_short_term", "page": 1, "page_size": 100}
    state = {"max_id": None, "sig": None}
    assert app_module.check_view_changed(c, spec, state) is False
    c.execute(
        "INSERT INTO statistics_short_term (metadata_id, start_ts, state) VALUES (?,?,?)",
        (2, 2000.0, "7.0"),
    )
    c.commit()
    assert app_module.check_view_changed(c, spec, state) is True
    c.close()


def test_check_view_changed_table_without_rowid_no_crash(tmp_path):
    path = tmp_path / "nowrowid.db"
    c = build_db(str(path))
    c.execute("CREATE TABLE no_pk (x INTEGER)")
    c.commit()
    c.close()
    db.init(f"sqlite:///{path}")
    conn = db.get_connection()
    spec = {"kind": "table", "table": "no_pk"}
    state = {"max_id": None, "sig": None}
    # no monotonic detection -> always False, never crashes
    assert app_module.check_view_changed(conn, spec, state) is False
    conn.close()
