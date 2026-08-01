-- HA recorder schema (subset) for PostgreSQL
-- Apply: psql "postgresql://postgres:secret@127.0.0.1:5433/hass" -f tests/schema.postgres.sql

DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS event_types;
DROP TABLE IF EXISTS statistics;
DROP TABLE IF EXISTS statistics_short_term;
DROP TABLE IF EXISTS statistics_meta;
DROP TABLE IF EXISTS states;
DROP TABLE IF EXISTS states_meta;

CREATE TABLE states_meta (
    metadata_id BIGSERIAL PRIMARY KEY,
    entity_id VARCHAR(255) UNIQUE
);
CREATE TABLE states (
    state_id BIGSERIAL PRIMARY KEY,
    entity_id VARCHAR(255),
    metadata_id BIGINT,
    state VARCHAR(255),
    last_updated_ts DOUBLE PRECISION
);
CREATE TABLE statistics_meta (
    id BIGSERIAL PRIMARY KEY,
    statistic_id VARCHAR(255) UNIQUE
);
CREATE TABLE statistics (
    id BIGSERIAL PRIMARY KEY,
    metadata_id BIGINT,
    start_ts DOUBLE PRECISION,
    state VARCHAR(255)
);
CREATE TABLE statistics_short_term (
    id BIGSERIAL PRIMARY KEY,
    metadata_id BIGINT,
    start_ts DOUBLE PRECISION,
    state VARCHAR(255)
);
CREATE TABLE event_types (
    event_type_id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(255) UNIQUE
);
CREATE TABLE events (
    event_id BIGSERIAL PRIMARY KEY,
    event_type_id BIGINT,
    event_type VARCHAR(255),
    time_fired_ts DOUBLE PRECISION
);

INSERT INTO states_meta (entity_id) VALUES ('sensor.a'), ('sensor.b'), ('light.c');
INSERT INTO states (entity_id, metadata_id, state, last_updated_ts) VALUES
    ('sensor.a', 1, '1.0', 1000.0),
    ('sensor.a', 1, '2.0', 1100.0),
    ('sensor.b', 2, 'off', 1000.0),
    ('light.c', 3, 'on', 900.0);
INSERT INTO statistics_meta (statistic_id) VALUES ('sensor.a_mean'), ('sensor.b_mean');
INSERT INTO statistics (metadata_id, start_ts, state) VALUES
    (1, 1000.0, '1.0'),
    (1, 1100.0, '2.0'),
    (2, 1000.0, '0.5');
INSERT INTO statistics_short_term (metadata_id, start_ts, state) VALUES (1, 1000.0, '1.1');
INSERT INTO event_types (event_type) VALUES ('state_changed'), ('homeassistant_start');
INSERT INTO events (event_type_id, event_type, time_fired_ts) VALUES
    (1, 'state_changed', 1000.0),
    (1, 'state_changed', 1100.0),
    (2, 'homeassistant_start', 900.0);
