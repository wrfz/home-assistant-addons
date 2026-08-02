import sqlite3

import db
import app as app_module

from .conftest import build_db, seed


def test_view_key_dedup():
    a = {"kind": "table", "table": "states", "counts": False}
    b = {"counts": False, "table": "states", "kind": "table"}
    assert app_module.view_key(a) == app_module.view_key(b)


def test_max_id_usage_count_views(conn):
    assert app_module.max_id(conn, {"table": "states_meta", "counts": True}) == 4
    assert app_module.max_id(conn, {"table": "statistics_meta", "counts": True}) == 3
    assert app_module.max_id(conn, {"table": "event_types", "counts": True}) == 3


def test_max_id_usage_count_view_filtered(conn):
    assert app_module.max_id(
        conn, {"table": "states_meta", "counts": True, "filter_col": "metadata_id", "filter_value": "1"}
    ) == 2


def test_max_id_table_uses_rowid(conn):
    assert app_module.max_id(conn, {"kind": "table", "table": "states"}) == 4


def test_max_id_plain_table_count_false(conn):
    assert app_module.max_id(conn, {"table": "states", "counts": False}) == 4


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


def test_page_signature_count_view_stable_and_changes(tmp_path):
    path = tmp_path / "watch.db"
    c = build_db(str(path))
    seed(c)
    spec = {"table": "states_meta", "counts": True, "page": 1, "page_size": 100}
    sig1 = app_module.page_signature(c, spec)
    c.execute(
        "INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES (?,?,?,?)",
        ("sensor.b", 2, "on", 9999.0),
    )
    c.commit()
    sig2 = app_module.page_signature(c, spec)
    assert sig1 != sig2
    c.close()


def test_check_view_changed_first_false_then_true(tmp_path):
    path = tmp_path / "watch.db"
    c = build_db(str(path))
    seed(c)
    spec = {"kind": "table", "table": "states"}
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


def test_check_view_changed_count_view_uses_signature(tmp_path):
    path = tmp_path / "watch.db"
    c = build_db(str(path))
    seed(c)
    spec = {"table": "statistics_meta", "counts": True, "page": 1, "page_size": 100}
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
