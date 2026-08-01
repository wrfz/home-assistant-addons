async def test_entity_states(client):
    r = await client.get("/api/entity/sensor.a/states")
    assert r.status == 200
    data = await r.json()
    assert data["entity_id"] == "sensor.a"
    assert data["total_rows"] == 2
    assert len(data["rows"]) == 2
    # default sort last_updated_ts DESC
    ts = [row["last_updated_ts"] for row in data["rows"]]
    assert ts == sorted(ts, reverse=True)


async def test_entity_states_sort_asc(client):
    r = await client.get(
        "/api/entity/sensor.a/states", params={"sort": "last_updated_ts", "dir": "asc"}
    )
    data = await r.json()
    ts = [row["last_updated_ts"] for row in data["rows"]]
    assert ts == [1000.0, 1100.0]


async def test_entity_not_found(client):
    r = await client.get("/api/entity/sensor.nope/states")
    assert r.status == 404


async def test_statistic_data(client):
    r = await client.get("/api/statistic/sensor.a_mean/data")
    assert r.status == 200
    data = await r.json()
    assert data["statistic_id"] == "sensor.a_mean"
    assert data["total_rows"] == 2


async def test_statistic_not_found(client):
    r = await client.get("/api/statistic/sensor.nope/data")
    assert r.status == 404


async def test_statistic_short_term_data(client):
    r = await client.get("/api/statistic/sensor.a_mean/data", params={"short_term": "1"})
    assert r.status == 200
    data = await r.json()
    assert data["statistic_id"] == "sensor.a_mean"
    assert data["total_rows"] == 1


async def test_statistics_short_term_listing(client):
    r = await client.get("/api/statistics-short-term")
    assert r.status == 200
    data = await r.json()
    by_id = {row["statistic_id"]: row for row in data}
    assert by_id["sensor.a_mean"]["stat_count"] == 1
    assert by_id["sensor.b_mean"]["stat_count"] == 0


async def test_event_type_data(client):
    r = await client.get("/api/event-type/state_changed/data")
    assert r.status == 200
    data = await r.json()
    assert data["event_type"] == "state_changed"
    assert data["total_rows"] == 2


async def test_event_type_not_found(client):
    r = await client.get("/api/event-type/not_an_event/data")
    assert r.status == 404


async def test_detail_sort_injection_safe(client):
    r = await client.get(
        "/api/entity/sensor.a/states",
        params={"sort": "state; DROP TABLE states", "dir": "desc"},
    )
    assert r.status == 200
    r2 = await client.get("/api/table/states")
    assert (await r2.json())["total_rows"] == 4
