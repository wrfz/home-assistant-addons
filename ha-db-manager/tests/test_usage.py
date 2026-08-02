import sqlite3


def _rows(data):
    return {r["entity_id"]: r for r in data["rows"]}


async def test_states_usage(client):
    r = await client.get("/api/table/states_meta", params={"counts": "1"})
    assert r.status == 200
    data = await r.json()
    assert data["counts"] is True
    assert data["page"] == 1
    assert data["page_size"] == 100
    assert data["total_rows"] == 3
    assert data["total_pages"] == 1
    assert data["global_baseline"] == 4
    assert data["columns"] == ["entity_id", "metadata_id", "state_count", "new_count"]
    by_id = _rows(data)
    assert by_id["sensor.a"]["state_count"] == 2
    assert by_id["sensor.b"]["state_count"] == 1
    assert by_id["light.c"]["state_count"] == 1
    assert by_id["sensor.a"]["new_count"] == 0


async def test_states_usage_paged(client):
    r = await client.get(
        "/api/table/states_meta", params={"counts": "1", "page": "2", "page_size": "2", "sort": "entity_id", "dir": "asc"}
    )
    data = await r.json()
    assert data["page"] == 2
    assert data["total_rows"] == 3
    assert data["total_pages"] == 2
    assert len(data["rows"]) == 1
    assert data["rows"][0]["entity_id"] == "sensor.b"

    r = await client.get(
        "/api/table/states_meta", params={"counts": "1", "page": "1", "page_size": "2", "sort": "entity_id", "dir": "desc"}
    )
    data = await r.json()
    assert [row["entity_id"] for row in data["rows"]] == ["sensor.b", "sensor.a"]


async def test_states_usage_sorted_by_new_count(client):
    r = await client.get("/api/table/states_meta", params={"counts": "1", "since": "0", "sort": "new_count", "dir": "desc"})
    data = await r.json()
    assert "new_count" in data["columns"]
    assert data["rows"][0]["entity_id"] == "sensor.a"
    assert data["rows"][0]["new_count"] == 2
    assert all("new_count" in row for row in data["rows"])

    r = await client.get("/api/table/states_meta", params={"counts": "1", "since": "0", "sort": "new_count", "dir": "asc"})
    data = await r.json()
    assert data["rows"][-1]["entity_id"] == "sensor.a"


async def test_states_usage_with_since(client, seed_db):
    r = await client.get("/api/table/states_meta", params={"counts": "1", "since": "4"})
    data = await r.json()
    assert "new_count" in data["columns"]
    by_id = _rows(data)
    assert by_id["sensor.a"]["new_count"] == 0
    assert by_id["sensor.b"]["new_count"] == 0
    assert by_id["light.c"]["new_count"] == 0

    conn = sqlite3.connect(seed_db)
    conn.executemany(
        "INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES (?,?,?,?)",
        [("sensor.a", 1, "3.0", 1200.0), ("sensor.b", 2, "on", 1300.0)],
    )
    conn.commit()
    conn.close()

    r = await client.get("/api/table/states_meta", params={"counts": "1", "since": "4"})
    data = await r.json()
    by_id = _rows(data)
    # interleaved inserts must count only the two new rows for their owners
    assert by_id["sensor.a"]["new_count"] == 1
    assert by_id["sensor.b"]["new_count"] == 1
    assert by_id["light.c"]["new_count"] == 0


async def test_statistics_usage(client):
    r = await client.get("/api/table/statistics_meta", params={"counts": "1"})
    assert r.status == 200
    data = await r.json()
    assert data["total_rows"] == 2
    assert data["columns"] == ["statistic_id", "metadata_id", "stat_count", "short_stat_count", "new_count"]
    by_id = {d["statistic_id"]: d for d in data["rows"]}
    assert by_id["sensor.a_mean"]["stat_count"] == 2
    assert by_id["sensor.a_mean"]["short_stat_count"] == 1
    assert by_id["sensor.b_mean"]["short_stat_count"] == 0


async def test_filtered_view_returns_label(client):
    # short-term statistics filtered by metadata_id should resolve to statistic_id
    r = await client.get(
        "/api/table/statistics_short_term",
        params={"filter_col": "metadata_id", "filter_value": "1"},
    )
    assert r.status == 200
    data = await r.json()
    assert data["filter_label"] == "sensor.a_mean"

    r = await client.get(
        "/api/table/states",
        params={"filter_col": "metadata_id", "filter_value": "1"},
    )
    data = await r.json()
    assert data["filter_label"] == "sensor.a"

    r = await client.get(
        "/api/table/events",
        params={"filter_col": "event_type_id", "filter_value": "1"},
    )
    data = await r.json()
    assert data["filter_label"] == "state_changed"

    # unfiltered views have no label
    r = await client.get("/api/table/states")
    assert (await r.json())["filter_label"] is None

    # unknown filter values have no label
    r = await client.get("/api/table/states", params={"filter_col": "metadata_id", "filter_value": "999"})
    assert (await r.json())["filter_label"] is None


async def test_statistics_since_new_count(client, seed_db):
    r = await client.get("/api/table/statistics_meta", params={"counts": "1", "since": "1"})
    data = await r.json()
    by_id = {d["statistic_id"]: d for d in data["rows"]}
    assert by_id["sensor.a_mean"]["new_count"] == 1

    conn = sqlite3.connect(seed_db)
    conn.execute(
        "INSERT INTO statistics (metadata_id, start_ts, state) VALUES (?,?,?)",
        (1, 1200.0, "3.0"),
    )
    conn.commit()
    conn.close()

    r = await client.get("/api/table/statistics_meta", params={"counts": "1", "since": "1"})
    data = await r.json()
    assert {d["statistic_id"]: d["new_count"] for d in data["rows"]}["sensor.a_mean"] == 2


async def test_event_types_usage(client):
    r = await client.get("/api/table/event_types", params={"counts": "1"})
    assert r.status == 200
    data = await r.json()
    assert data["total_rows"] == 2
    assert data["columns"] == ["event_type", "event_type_id", "event_count", "new_count"]
    by_type = {d["event_type"]: d for d in data["rows"]}
    assert by_type["state_changed"]["event_count"] == 2


async def test_event_types_since_new_count(client, seed_db):
    r = await client.get("/api/table/event_types", params={"counts": "1", "since": "2"})
    data = await r.json()
    assert {d["event_type"]: d["new_count"] for d in data["rows"]}["state_changed"] == 0

    conn = sqlite3.connect(seed_db)
    conn.execute(
        "INSERT INTO events (event_type_id, event_type, time_fired_ts) VALUES (?,?,?)",
        (1, "state_changed", 1200.0),
    )
    conn.commit()
    conn.close()

    r = await client.get("/api/table/event_types", params={"counts": "1", "since": "2"})
    data = await r.json()
    assert {d["event_type"]: d["new_count"] for d in data["rows"]}["state_changed"] == 1


async def test_count_view_filter(client):
    r = await client.get(
        "/api/table/states_meta",
        params={"counts": "1", "filter_col": "metadata_id", "filter_value": "1"},
    )
    assert r.status == 200
    data = await r.json()
    assert data["total_rows"] == 1
    assert data["rows"][0]["entity_id"] == "sensor.a"
    assert data["rows"][0]["state_count"] == 2


async def test_new_baseline_persists_server_side(client, seed_db):
    # first request without `since` establishes a baseline = current max pk
    r = await client.get("/api/table/states_meta", params={"counts": "1"})
    data = await r.json()
    assert {row["entity_id"]: row["new_count"] for row in data["rows"]} == {
        "sensor.a": 0, "sensor.b": 0, "light.c": 0,
    }

    # new rows inserted after the baseline count as "new" on later requests
    conn = sqlite3.connect(seed_db)
    conn.execute(
        "INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES (?,?,?,?)",
        ("sensor.a", 1, "3.0", 1200.0),
    )
    conn.commit()
    conn.close()

    r = await client.get("/api/table/states_meta", params={"counts": "1"})
    data = await r.json()
    assert {row["entity_id"]: row["new_count"] for row in data["rows"]} == {
        "sensor.a": 1, "sensor.b": 0, "light.c": 0,
    }

    # sorting and paging reuse the same server-held baseline
    r = await client.get(
        "/api/table/states_meta", params={"counts": "1", "sort": "new_count", "dir": "desc"}
    )
    data = await r.json()
    assert data["rows"][0]["entity_id"] == "sensor.a"
    assert data["rows"][0]["new_count"] == 1


async def test_clean_new_resets_baselines(client, seed_db):
    # establish a baseline, then add a new row
    await client.get("/api/table/states_meta", params={"counts": "1"})
    conn = sqlite3.connect(seed_db)
    conn.execute(
        "INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES (?,?,?,?)",
        ("sensor.a", 1, "3.0", 1200.0),
    )
    conn.commit()
    conn.close()

    r = await client.get("/api/table/states_meta", params={"counts": "1"})
    data = await r.json()
    assert {row["entity_id"]: row["new_count"] for row in data["rows"]}["sensor.a"] == 1

    # Clean New just resets the stored baselines to 0 (no DB access needed)
    r = await client.post("/api/clean-new")
    assert r.status == 200

    # the next count view request re-establishes the baseline, so nothing is new
    r = await client.get("/api/table/states_meta", params={"counts": "1"})
    data = await r.json()
    assert {row["entity_id"]: row["new_count"] for row in data["rows"]} == {
        "sensor.a": 0, "sensor.b": 0, "light.c": 0,
    }


async def test_clean_new_covers_all_usage_tables(client):
    # establish baselines for all usage tables first
    for table in ("states_meta", "statistics_meta", "event_types"):
        await client.get(f"/api/table/{table}", params={"counts": "1"})
    r = await client.post("/api/clean-new")
    assert r.status == 200
    # no persistence side effects: settings file stays baseline-free
    assert "baselines" not in (await r.json())
