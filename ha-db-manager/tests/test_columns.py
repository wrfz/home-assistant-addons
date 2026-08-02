import json

import db
import app as app_module


async def test_hidden_columns_default_empty(client):
    r = await client.get("/api/settings")
    data = await r.json()
    assert data["hidden_columns"] == {}


async def test_column_info_in_tables_meta(client):
    r = await client.get("/api/tables")
    assert r.status == 200
    data = await r.json()
    by_name = {t["name"]: t for t in data}
    states = by_name["states"]
    assert "column_info" in states
    assert "state_id" in states["column_info"]
    assert "state" in states["column_info"]
    assert "metadata_id" in states["column_info"]
    assert by_name["events"]["column_info"]["origin_idx"]
    assert by_name["states_meta"]["column_info"]["entity_id"]
    # sqlite_sequence is described too
    assert by_name["sqlite_sequence"]["column_info"]["name"]
    # every table ships a column_info map (possibly empty)
    assert all("column_info" in t for t in data)


def test_format_bytes():
    assert app_module.format_bytes(0) == "0B"
    assert app_module.format_bytes(12) == "12B"
    assert app_module.format_bytes(1024) == "1.0kB"
    assert app_module.format_bytes(30 * 1024) == "30.0kB"
    assert app_module.format_bytes(45 * 1024 * 1024) == "45.0MB"
    assert app_module.format_bytes(1.2 * 1024 ** 3) == "1.2GB"


def test_safe_encoder_renders_bytes_as_size():
    import json as _json

    out = _json.dumps({"data": b"\x01\x02\x03"}, cls=app_module.SafeEncoder)
    assert '"3B"' in out


async def test_hide_column(client):
    r = await client.post("/api/columns/hide", json={"table": "states", "column": "entity_id"})
    assert r.status == 200
    data = await r.json()
    assert data["hidden_columns"]["states"] == ["entity_id"]

    r = await client.get("/api/table/states")
    assert r.status == 200
    tdata = await r.json()
    assert "entity_id" not in tdata["columns"]
    assert "state" in tdata["columns"]


async def test_hide_column_filters_plain_table(client):
    r = await client.post("/api/columns/hide", json={"table": "states", "column": "entity_id"})
    assert r.status == 200
    r = await client.get("/api/table/states")
    assert r.status == 200
    tdata = await r.json()
    assert "entity_id" not in tdata["columns"]
    assert "state" in tdata["columns"]


async def test_hide_column_requires_fields(client):
    r = await client.post("/api/columns/hide", json={"table": "states"})
    assert r.status == 400
    r = await client.post("/api/columns/hide", json={"column": "entity_id"})
    assert r.status == 400
    r = await client.post("/api/columns/hide", data="not json")
    assert r.status == 400


async def test_hide_empty_columns(client, conn):
    conn.execute("CREATE TABLE empty_test (id INTEGER, always_null TEXT, also_empty TEXT)")
    conn.executemany(
        "INSERT INTO empty_test (id, always_null, also_empty) VALUES (?, ?, ?)",
        [(1, None, ""), (2, None, None)],
    )
    conn.commit()

    r = await client.post("/api/columns/hide-empty")
    assert r.status == 200
    data = await r.json()
    hidden = data["hidden_columns"]
    assert set(hidden.get("empty_test", [])) == {"always_null", "also_empty"}
    assert "id" not in hidden.get("empty_test", [])

    r = await client.get("/api/table/empty_test")
    tdata = await r.json()
    assert "always_null" not in tdata["columns"]
    assert "id" in tdata["columns"]


async def test_hide_empty_recognises_empty_blob(client, conn):
    # an empty BLOB (x'') must count as empty even though it compares unequal
    # to '' in SQLite; a populated BLOB / numeric 0 / NULL handling as well
    conn.execute(
        "CREATE TABLE blob_test (id INTEGER, empty_blob BLOB, real_blob BLOB, "
        "ts REAL, txt TEXT)"
    )
    conn.executemany(
        "INSERT INTO blob_test (id, empty_blob, real_blob, ts, txt) VALUES (?, ?, ?, ?, ?)",
        [
            (1, b"", b"\x01\x02", None, ""),
            (2, b"", b"\x03", 0.0, None),
        ],
    )
    conn.commit()

    r = await client.post("/api/columns/hide-empty")
    assert r.status == 200
    data = await r.json()
    hidden = data["hidden_columns"]
    assert set(hidden.get("blob_test", [])) == {"empty_blob", "txt"}
    assert "id" not in hidden.get("blob_test", [])
    assert "real_blob" not in hidden.get("blob_test", [])
    assert "ts" not in hidden.get("blob_test", [])


async def test_show_all_columns(client):
    r = await client.post("/api/columns/hide", json={"table": "states", "column": "entity_id"})
    assert r.status == 200
    r = await client.post("/api/columns/show-all")
    assert r.status == 200
    data = await r.json()
    assert data["hidden_columns"] == {}

    r = await client.get("/api/table/states")
    tdata = await r.json()
    assert "entity_id" in tdata["columns"]


async def test_hidden_columns_persisted_across_reboot(client, tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setenv("HA_SQLITE_SETTINGS_FILE", str(settings_file))
    r = await client.post("/api/columns/hide", json={"table": "states", "column": "entity_id"})
    assert r.status == 200
    assert json.loads(settings_file.read_text())["hidden_columns"]["states"] == ["entity_id"]

    import app as app_module

    app2 = app_module.create_app()
    assert app2["state"]["hidden_columns"]["states"] == {"entity_id"}


async def test_hidden_columns_not_selected_in_sql(client, monkeypatch):
    await client.post("/api/columns/hide", json={"table": "states", "column": "entity_id"})
    statements = []
    real_execute = db.execute

    def capture(conn, sql, params=None):
        statements.append(sql)
        return real_execute(conn, sql, params)

    monkeypatch.setattr(db, "execute", capture)
    r = await client.get("/api/table/states")
    assert r.status == 200
    data = await r.json()
    assert "entity_id" not in data["columns"]
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert selects, "expected a SELECT statement"
    # the hidden column must not appear in any SELECT column list
    for sql in selects:
        assert "entity_id" not in sql


async def test_count_view_columns_all_protected(client):
    # every count-view column is a link, a link value column or virtual, so
    # none of them may be hidden
    for col in ("entity_id", "metadata_id", "state_count", "new_count"):
        r = await client.post("/api/columns/hide", json={"table": "states_meta", "column": col})
        assert r.status == 400, col


async def test_link_column_cannot_be_hidden(client):
    r = await client.post("/api/columns/hide", json={"table": "states_meta", "column": "entity_id"})
    assert r.status == 400
    data = await r.json()
    assert data["error"]
    r = await client.post("/api/columns/hide", json={"table": "states", "column": "metadata_id"})
    assert r.status == 400


async def test_hide_empty_skips_link_columns(client, conn):
    conn.execute("UPDATE statistics_meta SET statistic_id = NULL")
    conn.execute("UPDATE event_types SET event_type = NULL")
    conn.commit()
    r = await client.post("/api/columns/hide-empty")
    assert r.status == 200
    data = await r.json()
    hidden = data["hidden_columns"]
    # link columns are skipped even though their values are now empty
    assert "statistic_id" not in hidden.get("statistics_meta", [])
    assert "event_type" not in hidden.get("event_types", [])
    # but a non-protected column with empty values is hidden
    conn2 = conn
    conn2.execute("UPDATE states SET state = ''")
    conn2.commit()
    r = await client.post("/api/columns/hide-empty")
    data = await r.json()
    assert "state" in data["hidden_columns"].get("states", [])


async def test_virtual_column_cannot_be_hidden(client):
    r = await client.post("/api/columns/hide", json={"table": "states_meta", "column": "state_count"})
    assert r.status == 400
    r = await client.post("/api/columns/hide", json={"table": "states_meta", "column": "new_count"})
    assert r.status == 400


async def test_show_all_columns_persisted_across_reboot(client, tmp_path, monkeypatch):
    import app as app_module

    settings_file = tmp_path / "settings.json"
    monkeypatch.setenv("HA_SQLITE_SETTINGS_FILE", str(settings_file))
    await client.post("/api/columns/hide", json={"table": "states", "column": "entity_id"})
    await client.post("/api/columns/show-all")
    app2 = app_module.create_app()
    assert app2["state"]["hidden_columns"] == {}
