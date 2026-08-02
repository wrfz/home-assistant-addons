#!/usr/bin/env python3
"""Create a demo Home Assistant recorder DB (SQLite) with realistic data.

The schema mirrors the full set of HA recorder tables this addon understands
(states, states_meta, state_attributes, statistics, statistics_meta,
statistics_short_term, statistics_runs, events, event_types, event_data,
recorder_runs, schema_changes, excluded_events, migration_changes). It is a
superset of the pytest schema (tests/schema.sqlite.sql). Output defaults to
scripts/demo.db. Run the app against it with:
    HA_DB_URL=sqlite:///scripts/demo.db ./scripts/run-local.sh
"""
import json
import random
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Full HA recorder schema (SQLite flavour) covering every table the addon
# lists/links. Attribute/event payloads are stored JSON-encoded, like HA.
SCHEMA = """
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS event_data;
DROP TABLE IF EXISTS event_types;
DROP TABLE IF EXISTS statistics_runs;
DROP TABLE IF EXISTS statistics;
DROP TABLE IF EXISTS statistics_short_term;
DROP TABLE IF EXISTS statistics_meta;
DROP TABLE IF EXISTS states;
DROP TABLE IF EXISTS states_meta;
DROP TABLE IF EXISTS state_attributes;
DROP TABLE IF EXISTS recorder_runs;
DROP TABLE IF EXISTS schema_changes;
DROP TABLE IF EXISTS excluded_events;
DROP TABLE IF EXISTS migration_changes;

CREATE TABLE states_meta (
    metadata_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT UNIQUE
);
CREATE TABLE state_attributes (
    attributes_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT,
    shared_attrs TEXT
);
CREATE TABLE states (
    state_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT,
    metadata_id INTEGER,
    attributes_id INTEGER,
    state TEXT,
    last_updated_ts REAL,
    last_changed_ts REAL
);
CREATE TABLE statistics_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    statistic_id TEXT UNIQUE
);
CREATE TABLE statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metadata_id INTEGER,
    start_ts REAL,
    state TEXT,
    mean REAL,
    min REAL,
    max REAL,
    sum REAL
);
CREATE TABLE statistics_short_term (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metadata_id INTEGER,
    start_ts REAL,
    state TEXT,
    mean REAL,
    min REAL,
    max REAL,
    sum REAL
);
CREATE TABLE statistics_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    start REAL
);
CREATE TABLE event_types (
    event_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT UNIQUE
);
CREATE TABLE event_data (
    data_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT,
    shared_data TEXT
);
CREATE TABLE events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type_id INTEGER,
    event_type TEXT,
    data_id INTEGER,
    time_fired_ts REAL
);
CREATE TABLE recorder_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    start REAL,
    end REAL,
    closed_incorrectly INTEGER,
    created REAL
);
CREATE TABLE schema_changes (
    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    schema_version INTEGER,
    changed REAL
);
CREATE TABLE excluded_events (
    event_id INTEGER PRIMARY KEY,
    event_type TEXT,
    time_fired REAL
);
CREATE TABLE migration_changes (
    migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    migration TEXT,
    version INTEGER
);
"""

ENTITIES = [
    "binary_sensor.keller_heizstab_eingang",
    "binary_sensor.keller_heizstab_eingang_0",
    "binary_sensor.keller_heizstab_eingang_1",
    "binary_sensor.keller_heizstab_ausgang",
    "binary_sensor.wohnzimmer_fenster",
    "climate.wohnzimmer",
    "climate.schlafzimmer",
    "light.wohnzimmer_decke",
    "light.keller",
    "sensor.aussentemperatur",
    "sensor.wohnzimmer_temperatur",
    "sensor.wohnzimmer_luftfeuchte",
    "sensor.energie_heute",
    "sensor.leistung_aktuell",
    "switch.heizstab",
    "switch.wohnzimmer_steckdose",
    "weather.haus",
]

EVENT_TYPES = [
    "state_changed",
    "homeassistant_start",
    "homeassistant_stop",
    "call_service",
    "automation_triggered",
    "logbook_entry",
]

STATE_VALUES = {
    "binary_sensor": ["on", "off"],
    "climate": ["heat", "off", "auto"],
    "light": ["on", "off"],
    "sensor": ["18.5", "19.2", "21.0", "22.4", "45.0", "60.0", "123.4", "0.0"],
    "switch": ["on", "off"],
    "weather": ["sunny", "partlycloudy", "cloudy", "rainy"],
}


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "scripts" / "demo.db"
    out.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(out))
    conn.executescript(SCHEMA)
    cur = conn.cursor()

    now = int(time.time())
    hour = 3600.0

    def domain(entity):
        return entity.split(".", 1)[0]

    def attr_json(entity_id, state):
        return json.dumps({
            "friendly_name": entity_id.split(".", 1)[1].replace("_", " ").title(),
            "unit_of_measurement": "°C" if domain(entity_id) == "sensor" else None,
            "state_class": "measurement",
            "last_updated": state,
        })

    # meta tables
    for entity_id in ENTITIES:
        cur.execute("INSERT INTO states_meta (entity_id) VALUES (?)", (entity_id,))
        stats_id = f"{entity_id}_mean"
        cur.execute("INSERT INTO statistics_meta (statistic_id) VALUES (?)", (stats_id,))
    for et in EVENT_TYPES:
        cur.execute("INSERT INTO event_types (event_type) VALUES (?)", (et,))

    # state_attributes: a handful of shared attribute blobs, like HA dedupes them
    attr_ids = []
    for entity_id in ENTITIES:
        for i in range(random.randint(1, 3)):
            cur.execute(
                "INSERT INTO state_attributes (hash, shared_attrs) VALUES (?,?)",
                (f"{entity_id}:{i}:hash", attr_json(entity_id, "1.0")),
            )
            attr_ids.append(cur.lastrowid)

    # event_data: shared JSON payloads referenced by events
    data_ids = []
    for i in range(20):
        cur.execute(
            "INSERT INTO event_data (hash, shared_data) VALUES (?,?)",
            (f"data-hash-{i}", json.dumps({"domain": "homeassistant", "service": "reload", "i": i})),
        )
        data_ids.append(cur.lastrowid)

    states_meta_ids = list(range(1, len(ENTITIES) + 1))
    stats_meta_ids = list(range(1, len(ENTITIES) + 1))
    event_type_ids = {et: i + 1 for i, et in enumerate(EVENT_TYPES)}

    # states: 2-3 days of history, several changes per hour per entity
    state_id = 0
    for meta_id, entity_id in zip(states_meta_ids, ENTITIES):
        values = STATE_VALUES.get(domain(entity_id), ["on", "off"])
        n = random.randint(60, 400)
        ts = now - random.randint(24 * hour, 72 * hour)
        for _ in range(n):
            state_id += 1
            ts += random.uniform(30, 1800)
            cur.execute(
                "INSERT INTO states (entity_id, metadata_id, attributes_id, state, "
                "last_updated_ts, last_changed_ts) VALUES (?,?,?,?,?,?)",
                (entity_id, meta_id, random.choice(attr_ids), random.choice(values), ts, ts),
            )

    # statistics: one row per hour over the last 3 days
    for meta_id, entity_id in zip(stats_meta_ids, ENTITIES):
        ts = now - 72 * hour
        while ts < now:
            mean = round(random.uniform(15.0, 25.0), 2)
            cur.execute(
                "INSERT INTO statistics (metadata_id, start_ts, state, mean, min, max, sum) "
                "VALUES (?,?,?,?,?,?,?)",
                (meta_id, ts, str(mean), mean, mean - 1, mean + 1, mean * 3),
            )
            cur.execute(
                "INSERT INTO statistics_short_term (metadata_id, start_ts, state, mean, min, max, sum) "
                "VALUES (?,?,?,?,?,?,?)",
                (meta_id, ts, str(mean), mean, mean - 1, mean + 1, mean * 3),
            )
            ts += hour

    # events: a few hundred spread over the last day
    n_events = random.randint(400, 800)
    for _ in range(n_events):
        et = random.choice(EVENT_TYPES)
        ts = now - random.uniform(0, 24 * hour)
        cur.execute(
            "INSERT INTO events (event_type_id, event_type, data_id, time_fired_ts) "
            "VALUES (?,?,?,?)",
            (event_type_ids[et], et, random.choice(data_ids), ts),
        )

    # statistics_runs / recorder_runs / schema_changes / excluded_events / migration_changes
    run_start = now - 72 * hour
    for i in range(4):
        cur.execute("INSERT INTO statistics_runs (start) VALUES (?)", (run_start + i * 24 * hour,))
        cur.execute(
            "INSERT INTO recorder_runs (start, end, closed_incorrectly, created) VALUES (?,?,?,?)",
            (run_start + i * 24 * hour, run_start + (i + 1) * 24 * hour, 0, run_start),
        )
    cur.execute("INSERT INTO schema_changes (schema_version, changed) VALUES (?,?)", (41, now))
    cur.execute(
        "INSERT INTO excluded_events (event_id, event_type, time_fired) VALUES (?,?,?)",
        (1, "homeassistant_stop", now - hour),
    )
    cur.executemany(
        "INSERT INTO migration_changes (migration, version) VALUES (?,?)",
        [("migration_a", 1), ("migration_b", 2)],
    )

    conn.commit()
    conn.execute("DELETE FROM sqlite_sequence")
    conn.commit()
    conn.close()
    print(f"Demo DB written to {out}")


if __name__ == "__main__":
    main()
