async def test_states_filtered_by_metadata(client):
    r = await client.get("/api/table/states", params={"filter_col": "metadata_id", "filter_value": "1"})
    assert r.status == 200
    data = await r.json()
    assert data["total_rows"] == 2
    assert len(data["rows"]) == 2
    # default sort last_updated_ts DESC
    ts = [row["last_updated_ts"] for row in data["rows"]]
    assert ts == sorted(ts, reverse=True)


async def test_states_filtered_sort_asc(client):
    r = await client.get(
        "/api/table/states",
        params={"filter_col": "metadata_id", "filter_value": "1", "sort": "last_updated_ts", "dir": "asc"},
    )
    data = await r.json()
    ts = [row["last_updated_ts"] for row in data["rows"]]
    assert ts == [1000.0, 1100.0]


async def test_states_filter_not_found(client):
    r = await client.get("/api/table/states", params={"filter_col": "metadata_id", "filter_value": "999"})
    assert r.status == 200
    data = await r.json()
    assert data["total_rows"] == 0


async def test_statistic_data(client):
    r = await client.get("/api/table/statistics", params={"filter_col": "metadata_id", "filter_value": "1"})
    assert r.status == 200
    data = await r.json()
    assert data["total_rows"] == 2


async def test_statistic_short_term_data(client):
    r = await client.get("/api/table/statistics_short_term", params={"filter_col": "metadata_id", "filter_value": "1"})
    assert r.status == 200
    data = await r.json()
    assert data["total_rows"] == 1


async def test_event_type_data(client):
    r = await client.get("/api/table/events", params={"filter_col": "event_type_id", "filter_value": "1"})
    assert r.status == 200
    data = await r.json()
    assert data["total_rows"] == 2


async def test_event_type_not_found(client):
    r = await client.get("/api/table/events", params={"filter_col": "event_type_id", "filter_value": "999"})
    assert r.status == 200
    assert (await r.json())["total_rows"] == 0


async def test_detail_sort_injection_safe(client):
    r = await client.get(
        "/api/table/states",
        params={"filter_col": "metadata_id", "filter_value": "1",
                "sort": "state; DROP TABLE states", "dir": "desc"},
    )
    assert r.status == 200
    r2 = await client.get("/api/table/states")
    assert (await r2.json())["total_rows"] == 4


async def test_detail_filter_injection_safe(client):
    r = await client.get(
        "/api/table/states",
        params={"filter_col": "metadata_id; DROP TABLE states;--", "filter_value": "1"},
    )
    assert r.status in (200, 400)
    r2 = await client.get("/api/table/states")
    assert (await r2.json())["total_rows"] == 4


async def test_static_appjs_served_with_version(client):
    r = await client.get("/static/app.js")
    assert r.status == 200
    assert r.headers.get("Content-Type", "").startswith("application/javascript")
    assert r.headers.get("Cache-Control") == "public, max-age=31536000, immutable"
    body = await r.text()
    assert "__APP_VERSION__" not in body
    assert "Home Assistant DB Manager" in body


async def test_static_stylecss_served(client):
    r = await client.get("/static/style.css")
    assert r.status == 200
    assert r.headers.get("Content-Type", "").startswith("text/css")
    body = await r.text()
    assert "--app-accent" in body


async def test_static_version_query_ignored(client):
    r = await client.get("/static/app.js?v=0.40.0")
    assert r.status == 200


async def test_static_traversal_blocked(client):
    r = await client.get("/static/../app.py")
    assert r.status == 404
