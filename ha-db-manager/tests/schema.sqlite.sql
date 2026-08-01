-- HA recorder schema (subset) for SQLite
-- Used by the pytest suite (tests/conftest.py builds the test DB from this file).

DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS event_types;
DROP TABLE IF EXISTS statistics;
DROP TABLE IF EXISTS statistics_short_term;
DROP TABLE IF EXISTS statistics_meta;
DROP TABLE IF EXISTS states;
DROP TABLE IF EXISTS states_meta;

CREATE TABLE states_meta (
    metadata_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT UNIQUE
);
CREATE TABLE states (
    state_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT,
    metadata_id INTEGER,
    state TEXT,
    last_updated_ts REAL
);
CREATE TABLE statistics_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    statistic_id TEXT UNIQUE
);
CREATE TABLE statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metadata_id INTEGER,
    start_ts REAL,
    state TEXT
);
CREATE TABLE statistics_short_term (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metadata_id INTEGER,
    start_ts REAL,
    state TEXT
);
CREATE TABLE event_types (
    event_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT UNIQUE
);
CREATE TABLE events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type_id INTEGER,
    event_type TEXT,
    time_fired_ts REAL
);
