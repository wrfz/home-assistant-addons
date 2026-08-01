async def test_list_tables(client):
    r = await client.get("/api/tables")
    assert r.status == 200
    tables = await r.json()
    assert "states" in tables
    assert "events" in tables
    assert "statistics" in tables


async def test_table_page(client):
    r = await client.get("/api/table/states", params={"page_size": "2"})
    assert r.status == 200
    data = await r.json()
    assert data["table_name"] == "states"
    assert data["total_rows"] == 4
    assert data["total_pages"] == 2
    assert len(data["rows"]) == 2
    assert data["rows"][0]["entity_id"] == "sensor.a"


async def test_table_pagination(client):
    r1 = await client.get("/api/table/states", params={"page": "1", "page_size": "2"})
    d1 = await r1.json()
    r2 = await client.get("/api/table/states", params={"page": "2", "page_size": "2"})
    d2 = await r2.json()
    ids1 = [r["state_id"] for r in d1["rows"]]
    ids2 = [r["state_id"] for r in d2["rows"]]
    assert ids1 == [1, 2]
    assert ids2 == [3, 4]


async def test_table_sort(client):
    r = await client.get(
        "/api/table/states", params={"sort": "last_updated_ts", "dir": "desc"}
    )
    data = await r.json()
    ts = [row["last_updated_ts"] for row in data["rows"]]
    assert ts == sorted(ts, reverse=True)


async def test_table_sort_invalid_column_ignored(client):
    r = await client.get(
        "/api/table/states", params={"sort": "not_a_column; DROP TABLE states", "dir": "desc"}
    )
    assert r.status == 200
    data = await r.json()
    assert data["total_rows"] == 4  # states table still intact


async def test_table_invalid_dir_ignored(client):
    r = await client.get("/api/table/states", params={"dir": "drop"})
    assert r.status == 200


async def test_table_not_found(client):
    r = await client.get("/api/table/nope")
    assert r.status == 404


async def test_table_injection_table_name(client):
    r = await client.get('/api/table/states%22%3B%20DROP%20TABLE%20states%3B--')
    # must not crash or delete anything; either 404 or a clean response
    assert r.status in (200, 404)
    r2 = await client.get("/api/table/states")
    assert r2.status == 200
    data = await r2.json()
    assert data["total_rows"] == 4
