import json

import db
import app as app_module


async def test_hidden_columns_default_empty(client):
    r = await client.get("/api/settings")
    data = await r.json()
    assert data["hidden_columns"] == {}


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


async def test_hide_column_filters_count_view(client):
    r = await client.post("/api/columns/hide", json={"table": "states_meta", "column": "metadata_id"})
    assert r.status == 200
    r = await client.get("/api/table/states_meta", params={"counts": "1"})
    assert r.status == 200
    tdata = await r.json()
    assert "metadata_id" not in tdata["columns"]
    assert "entity_id" in tdata["columns"]


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


async def test_hidden_count_column_not_joined_in_sql(client, monkeypatch):
    await client.post("/api/columns/hide", json={"table": "states_meta", "column": "new_count"})
    statements = []
    real_execute = db.execute

    def capture(conn, sql, params=None):
        statements.append(sql)
        return real_execute(conn, sql, params)

    monkeypatch.setattr(db, "execute", capture)
    r = await client.get("/api/table/states_meta", params={"counts": "1"})
    assert r.status == 200
    data = await r.json()
    assert "new_count" not in data["columns"]
    assert "state_count" in data["columns"]
    joins = " ".join(statements)
    assert "new_count" not in joins


async def test_show_all_columns_persisted_across_reboot(client, tmp_path, monkeypatch):
    import app as app_module

    settings_file = tmp_path / "settings.json"
    monkeypatch.setenv("HA_SQLITE_SETTINGS_FILE", str(settings_file))
    await client.post("/api/columns/hide", json={"table": "states", "column": "entity_id"})
    await client.post("/api/columns/show-all")
    app2 = app_module.create_app()
    assert app2["state"]["hidden_columns"] == {}
