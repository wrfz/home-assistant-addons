def _names(tables):
    return {t["name"] for t in tables}


async def test_list_tables(client):
    r = await client.get("/api/tables")
    assert r.status == 200
    tables = await r.json()
    names = _names(tables)
    assert "states" in names
    assert "events" in names
    assert "statistics" in names
    # count views are marked and carry default sort / links metadata
    by_name = {t["name"]: t for t in tables}
    assert by_name["states_meta"]["counts"] is True
    assert by_name["states_meta"]["default_sort"] == "entity_id"
    assert "entity_id" in by_name["states_meta"]["links"]
    assert by_name["states"]["counts"] is False
    assert by_name["states"]["links"]["metadata_id"]["target"] == "states_meta"
    assert by_name["statistics_meta"]["links"]["short_stat_count"]["target"] == "statistics_short_term"
    assert by_name["events"]["links"]["event_type_id"]["target"] == "event_types"


async def test_table_page(client):
    r = await client.get("/api/table/states", params={"page_size": "2"})
    assert r.status == 200
    data = await r.json()
    assert data["table_name"] == "states"
    assert data["counts"] is False
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


async def test_table_filter(client):
    r = await client.get("/api/table/states", params={"filter_col": "metadata_id", "filter_value": "1"})
    assert r.status == 200
    data = await r.json()
    assert data["total_rows"] == 2


async def test_table_filter_invalid_column(client):
    r = await client.get(
        "/api/table/states", params={"filter_col": "nope; DROP TABLE states", "filter_value": "1"}
    )
    assert r.status == 400


async def test_table_filter_does_not_leak(client):
    r = await client.get("/api/table/states", params={"filter_col": "metadata_id", "filter_value": "1"})
    d = await r.json()
    assert all(row["metadata_id"] == 1 for row in d["rows"])


async def test_count_view_invalid_filter_column(client):
    r = await client.get(
        "/api/table/states_meta",
        params={"counts": "1", "filter_col": "state_count", "filter_value": "2"},
    )
    assert r.status == 400
