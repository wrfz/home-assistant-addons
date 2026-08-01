import sqlite3


async def test_states_usage(client):
    r = await client.get("/api/states")
    assert r.status == 200
    data = await r.json()
    by_id = {d["entity_id"]: d for d in data}
    assert len(by_id) == 3
    assert by_id["sensor.a"]["state_count"] == 2
    assert by_id["sensor.b"]["state_count"] == 1
    assert by_id["light.c"]["state_count"] == 1
    assert by_id["sensor.a"]["max_state_id"] == 2


async def test_states_usage_with_since(client, seed_db):
    r = await client.get("/api/states", params={"since": "4"})
    data = await r.json()
    by_id = {d["entity_id"]: d for d in data}
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

    r = await client.get("/api/states", params={"since": "4"})
    data = await r.json()
    by_id = {d["entity_id"]: d for d in data}
    # interleaved inserts must count only the two new rows for their owners
    assert by_id["sensor.a"]["new_count"] == 1
    assert by_id["sensor.b"]["new_count"] == 1
    assert by_id["light.c"]["new_count"] == 0


async def test_statistics_usage(client):
    r = await client.get("/api/statistics")
    assert r.status == 200
    data = await r.json()
    by_id = {d["statistic_id"]: d for d in data}
    assert by_id["sensor.a_mean"]["stat_count"] == 2
    assert by_id["sensor.a_mean"]["max_stat_id"] == 2


async def test_statistics_since_new_count(client, seed_db):
    r = await client.get("/api/statistics", params={"since": "1"})
    data = await r.json()
    by_id = {d["statistic_id"]: d for d in data}
    assert by_id["sensor.a_mean"]["new_count"] == 1

    conn = sqlite3.connect(seed_db)
    conn.execute(
        "INSERT INTO statistics (metadata_id, start_ts, state) VALUES (?,?,?)",
        (1, 1200.0, "3.0"),
    )
    conn.commit()
    conn.close()

    r = await client.get("/api/statistics", params={"since": "1"})
    data = await r.json()
    assert {d["statistic_id"]: d["new_count"] for d in data}["sensor.a_mean"] == 2


async def test_statistics_short_term_usage(client):
    r = await client.get("/api/statistics-short-term")
    assert r.status == 200
    data = await r.json()
    by_id = {d["statistic_id"]: d for d in data}
    assert by_id["sensor.a_mean"]["stat_count"] == 1
    assert by_id["sensor.a_mean"]["max_stat_id"] == 1
    assert by_id["sensor.b_mean"]["stat_count"] == 0


async def test_statistics_short_term_since_new_count(client, seed_db):
    r = await client.get("/api/statistics-short-term", params={"since": "0"})
    data = await r.json()
    by_id = {d["statistic_id"]: d for d in data}
    assert by_id["sensor.a_mean"]["new_count"] == 1

    conn = sqlite3.connect(seed_db)
    conn.execute(
        "INSERT INTO statistics_short_term (metadata_id, start_ts, state) VALUES (?,?,?)",
        (1, 1200.0, "1.2"),
    )
    conn.commit()
    conn.close()

    r = await client.get("/api/statistics-short-term", params={"since": "0"})
    data = await r.json()
    assert {d["statistic_id"]: d["new_count"] for d in data}["sensor.a_mean"] == 2


async def test_event_types_usage(client):
    r = await client.get("/api/event-types")
    assert r.status == 200
    data = await r.json()
    by_type = {d["event_type"]: d for d in data}
    assert by_type["state_changed"]["event_count"] == 2
    assert by_type["state_changed"]["max_event_id"] == 2


async def test_event_types_since_new_count(client, seed_db):
    r = await client.get("/api/event-types", params={"since": "2"})
    data = await r.json()
    assert {d["event_type"]: d["new_count"] for d in data}["state_changed"] == 0

    conn = sqlite3.connect(seed_db)
    conn.execute(
        "INSERT INTO events (event_type_id, event_type, time_fired_ts) VALUES (?,?,?)",
        (1, "state_changed", 1200.0),
    )
    conn.commit()
    conn.close()

    r = await client.get("/api/event-types", params={"since": "2"})
    data = await r.json()
    assert {d["event_type"]: d["new_count"] for d in data}["state_changed"] == 1
