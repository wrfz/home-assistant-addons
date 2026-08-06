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


def test_count_view_signature_stable_and_changes(tmp_path):
    path = tmp_path / "watch.db"
    c = build_db(str(path))
    seed(c)
    sig1 = app_module.count_view_signature(c, "states_meta")
    c.execute(
        "INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES (?,?,?,?)",
        ("sensor.b", 2, "on", 9999.0),
    )
    c.commit()
    sig2 = app_module.count_view_signature(c, "states_meta")
    assert sig1 != sig2
    c.close()


def test_count_view_signature_detects_purge(tmp_path):
    path = tmp_path / "watch.db"
    c = build_db(str(path))
    seed(c)
    sig1 = app_module.count_view_signature(c, "states_meta")
    c.execute("DELETE FROM states WHERE state_id = 1")
    c.commit()
    sig2 = app_module.count_view_signature(c, "states_meta")
    assert sig1 != sig2
    c.close()


def test_get_count_counts_builds_then_delta(tmp_path):
    path = tmp_path / "watch.db"
    c = build_db(str(path))
    seed(c)
    cdef = app_module.USAGE_SPECS["states_meta"]["counts"][0]
    state = {}
    entry = app_module.get_count_counts(c, cdef, state)
    assert entry["counts"] == {1: 2, 2: 1, 3: 1}
    assert entry["last_max"] == 4

    # a new row is folded in as a delta, keeping the same entry object
    c.execute(
        "INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES (?,?,?,?)",
        ("sensor.a", 1, "3.0", 1200.0),
    )
    c.commit()
    entry2 = app_module.get_count_counts(c, cdef, state)
    assert entry2 is entry
    assert entry["counts"] == {1: 3, 2: 1, 3: 1}
    assert entry["last_max"] == 5
    c.close()


def test_get_count_counts_rebuilds_after_purge(tmp_path):
    path = tmp_path / "watch.db"
    c = build_db(str(path))
    seed(c)
    cdef = app_module.USAGE_SPECS["states_meta"]["counts"][0]
    state = {}
    entry = app_module.get_count_counts(c, cdef, state)
    entry["baseline"] = 4
    entry["baseline_counts"] = dict(entry["counts"])

    # deleting the oldest rows changes MIN -> full rebuild and baseline reset
    c.execute("DELETE FROM states WHERE state_id IN (1, 2)")
    c.commit()
    entry2 = app_module.get_count_counts(c, cdef, state)
    assert entry2 is not entry
    assert entry2["counts"] == {2: 1, 3: 1}
    assert entry2["last_min"] == 3
    assert entry2["baseline"] is None
    assert entry2["baseline_counts"] is None
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
