async def test_chart_hourly(client):
    r = await client.get("/api/chart/1")
    assert r.status == 200
    data = await r.json()
    assert data["statistic_id"] == "sensor.a_mean"
    assert data["table"] == "statistics"
    assert data["metadata_id"] == 1
    # the minimal test schema only has start_ts/state, so only state is selected
    assert data["value_columns"] == ["state"]
    assert [row["start_ts"] for row in data["rows"]] == [1000.0, 1100.0]
    assert [row["state"] for row in data["rows"]] == ["1.0", "2.0"]


async def test_chart_short_term(client):
    r = await client.get("/api/chart/1", params={"table": "statistics_short_term"})
    assert r.status == 200
    data = await r.json()
    assert data["table"] == "statistics_short_term"
    assert len(data["rows"]) == 1
    assert data["rows"][0]["start_ts"] == 1000.0


async def test_chart_limit_returns_latest_chronological(client):
    r = await client.get("/api/chart/1", params={"limit": "1"})
    assert r.status == 200
    data = await r.json()
    assert [row["start_ts"] for row in data["rows"]] == [1100.0]


async def test_chart_statistic_not_found(client):
    r = await client.get("/api/chart/999")
    assert r.status == 404


async def test_chart_invalid_params(client):
    r = await client.get("/api/chart/notanumber")
    assert r.status == 400

    r = await client.get("/api/chart/1", params={"table": "states"})
    assert r.status == 400

    r = await client.get("/api/chart/1", params={"limit": "0"})
    assert r.status == 400
