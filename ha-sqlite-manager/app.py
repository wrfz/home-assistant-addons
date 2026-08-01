import re
import sqlite3
import json
import logging
from pathlib import Path
from aiohttp import web


class SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            try:
                return obj.decode("utf-8")
            except UnicodeDecodeError:
                return f"<binary {len(obj)} bytes>"
        return super().default(obj)

DB_PATH = Path("/config/home-assistant_v2.db")
STATIC_DIR = Path("/opt/static")
CONFIG_YAML = Path("/opt/config.yaml")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ha-sqlite-manager")


def read_app_version():
    try:
        m = re.search(r'^version:\s*"?([0-9.]+)', CONFIG_YAML.read_text(), re.MULTILINE)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"


APP_VERSION = read_app_version()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def index(request):
    version = request.query.get("v")
    if version != APP_VERSION:
        log.info("Redirecting to versioned URL (v=%s, was=%s)", APP_VERSION, version)
        return web.HTTPFound(f"?v={APP_VERSION}")
    log.info("Serving index page (app version %s)", APP_VERSION)
    html = (STATIC_DIR / "index.html").read_text().replace("__APP_VERSION__", APP_VERSION)
    resp = web.Response(text=html, content_type="text/html")
    resp.headers["X-Addon-Version"] = APP_VERSION
    return resp


async def api_tables(request):
    log.info("Listing tables")
    conn = get_db()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    conn.close()
    log.info("Found %d tables", len(tables))
    return web.json_response([t["name"] for t in tables])


async def api_states(request):
    log.info("Listing entities with state counts")
    conn = get_db()
    rows = conn.execute(
        """
        SELECT sm.metadata_id, sm.entity_id, COUNT(s.state_id) AS state_count
        FROM states_meta sm
        LEFT JOIN states s ON s.metadata_id = sm.metadata_id
        GROUP BY sm.metadata_id, sm.entity_id
        ORDER BY sm.entity_id
        """
    ).fetchall()
    conn.close()
    log.info("Found %d entities", len(rows))
    data = [dict(r) for r in rows]
    return web.Response(
        text=json.dumps(data, cls=SafeEncoder),
        content_type="application/json",
    )


async def api_table(request):
    table_name = request.match_info["table_name"]
    page = parse_int(request.query.get("page"), 1)
    page_size = parse_int(request.query.get("page_size"), 100)

    log.info("Viewing table '%s' (page %d, page_size %d)", table_name, page, page_size)

    conn = get_db()

    valid = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    if not valid:
        conn.close()
        log.warning("Table '%s' not found", table_name)
        return web.json_response({"error": "Table not found"}, status=404)

    total_rows = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
    offset = (page - 1) * page_size

    cursor = conn.execute(
        f'SELECT * FROM "{table_name}" LIMIT ? OFFSET ?', (page_size, offset)
    )
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    log.info("Table '%s': %d rows total, returning %d rows", table_name, total_rows, len(rows))

    data = {
        "table_name": table_name,
        "columns": columns,
        "rows": rows,
        "page": page,
        "page_size": page_size,
        "total_rows": total_rows,
        "total_pages": total_pages,
    }
    return web.Response(
        text=json.dumps(data, cls=SafeEncoder),
        content_type="application/json",
    )


async def api_entity_states(request):
    entity_id = request.match_info["entity_id"]
    page = parse_int(request.query.get("page"), 1)
    page_size = parse_int(request.query.get("page_size"), 100)

    log.info("GET /api/entity/%s/states (page=%d, page_size=%d)", entity_id, page, page_size)

    conn = get_db()

    meta = conn.execute(
        "SELECT metadata_id FROM states_meta WHERE entity_id = ?", (entity_id,)
    ).fetchone()
    if not meta:
        conn.close()
        log.warning("Entity '%s' not found in states_meta", entity_id)
        return web.json_response({"error": "Entity not found"}, status=404)

    metadata_id = meta["metadata_id"]
    log.info("Entity '%s' -> metadata_id=%d", entity_id, metadata_id)

    total_rows = conn.execute(
        "SELECT COUNT(*) FROM states WHERE metadata_id = ?", (metadata_id,)
    ).fetchone()[0]
    log.info("Entity '%s': %d states in total", entity_id, total_rows)

    offset = (page - 1) * page_size
    cursor = conn.execute(
        "SELECT * FROM states WHERE metadata_id = ? "
        "ORDER BY last_updated_ts DESC LIMIT ? OFFSET ?",
        (metadata_id, page_size, offset),
    )
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    log.info("Entity '%s': returning %d rows (page %d/%d)", entity_id, len(rows), page, total_pages)

    data = {
        "entity_id": entity_id,
        "columns": columns,
        "rows": rows,
        "page": page,
        "page_size": page_size,
        "total_rows": total_rows,
        "total_pages": total_pages,
    }
    return web.Response(
        text=json.dumps(data, cls=SafeEncoder),
        content_type="application/json",
    )


async def api_statistics(request):
    log.info("Listing statistics entities with counts")
    conn = get_db()
    rows = conn.execute(
        """
        SELECT sm.id AS metadata_id, sm.statistic_id, COUNT(s.id) AS stat_count
        FROM statistics_meta sm
        LEFT JOIN statistics s ON s.metadata_id = sm.id
        GROUP BY sm.id, sm.statistic_id
        ORDER BY sm.statistic_id
        """
    ).fetchall()
    conn.close()
    log.info("Found %d statistics", len(rows))
    data = [dict(r) for r in rows]
    return web.Response(
        text=json.dumps(data, cls=SafeEncoder),
        content_type="application/json",
    )


async def api_statistic_data(request):
    statistic_id = request.match_info["statistic_id"]
    page = parse_int(request.query.get("page"), 1)
    page_size = parse_int(request.query.get("page_size"), 100)

    log.info("Viewing data for statistic '%s' (page %d, page_size %d)", statistic_id, page, page_size)

    conn = get_db()
    meta = conn.execute(
        "SELECT id FROM statistics_meta WHERE statistic_id = ?", (statistic_id,)
    ).fetchone()
    if not meta:
        conn.close()
        log.warning("Statistic '%s' not found in statistics_meta", statistic_id)
        return web.json_response({"error": "Statistic not found"}, status=404)

    metadata_id = meta["id"]
    total_rows = conn.execute(
        "SELECT COUNT(*) FROM statistics WHERE metadata_id = ?", (metadata_id,)
    ).fetchone()[0]
    offset = (page - 1) * page_size
    cursor = conn.execute(
        "SELECT * FROM statistics WHERE metadata_id = ? "
        "ORDER BY start_ts DESC LIMIT ? OFFSET ?",
        (metadata_id, page_size, offset),
    )
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    log.info("Statistic '%s': returning %d rows (page %d/%d)", statistic_id, len(rows), page, total_pages)

    data = {
        "statistic_id": statistic_id,
        "columns": columns,
        "rows": rows,
        "page": page,
        "page_size": page_size,
        "total_rows": total_rows,
        "total_pages": total_pages,
    }
    return web.Response(
        text=json.dumps(data, cls=SafeEncoder),
        content_type="application/json",
    )


async def api_event_types(request):
    log.info("Listing event types with counts")
    conn = get_db()
    rows = conn.execute(
        """
        SELECT et.event_type_id, et.event_type, COUNT(e.event_id) AS event_count
        FROM event_types et
        LEFT JOIN events e ON e.event_type_id = et.event_type_id
        GROUP BY et.event_type_id, et.event_type
        ORDER BY et.event_type
        """
    ).fetchall()
    conn.close()
    log.info("Found %d event types", len(rows))
    data = [dict(r) for r in rows]
    return web.Response(
        text=json.dumps(data, cls=SafeEncoder),
        content_type="application/json",
    )


async def api_event_type_data(request):
    event_type = request.match_info["event_type"]
    page = parse_int(request.query.get("page"), 1)
    page_size = parse_int(request.query.get("page_size"), 100)

    log.info("Viewing events for type '%s' (page %d, page_size %d)", event_type, page, page_size)

    conn = get_db()
    meta = conn.execute(
        "SELECT event_type_id FROM event_types WHERE event_type = ?", (event_type,)
    ).fetchone()
    if not meta:
        conn.close()
        log.warning("Event type '%s' not found in event_types", event_type)
        return web.json_response({"error": "Event type not found"}, status=404)

    event_type_id = meta["event_type_id"]
    total_rows = conn.execute(
        "SELECT COUNT(*) FROM events WHERE event_type_id = ?", (event_type_id,)
    ).fetchone()[0]
    offset = (page - 1) * page_size
    cursor = conn.execute(
        "SELECT * FROM events WHERE event_type_id = ? "
        "ORDER BY time_fired_ts DESC LIMIT ? OFFSET ?",
        (event_type_id, page_size, offset),
    )
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    log.info("Event type '%s': returning %d rows (page %d/%d)", event_type, len(rows), page, total_pages)

    data = {
        "event_type": event_type,
        "columns": columns,
        "rows": rows,
        "page": page,
        "page_size": page_size,
        "total_rows": total_rows,
        "total_pages": total_pages,
    }
    return web.Response(
        text=json.dumps(data, cls=SafeEncoder),
        content_type="application/json",
    )


@web.middleware
async def no_cache_middleware(request, handler):
    resp = await handler(request)
    resp.headers["Cache-Control"] = "no-store"
    return resp


def create_app():
    app = web.Application(middlewares=[no_cache_middleware])
    app.router.add_get("/", index)
    app.router.add_get("/api/tables", api_tables)
    app.router.add_get("/api/states", api_states)
    app.router.add_get("/api/table/{table_name}", api_table)
    app.router.add_get("/api/entity/{entity_id}/states", api_entity_states)
    app.router.add_get("/api/statistics", api_statistics)
    app.router.add_get("/api/statistic/{statistic_id}/data", api_statistic_data)
    app.router.add_get("/api/event-types", api_event_types)
    app.router.add_get("/api/event-type/{event_type}/data", api_event_type_data)
    return app


if __name__ == "__main__":
    log.info("Starting HA SQLite Manager on port 8099")
    log.info("Database: %s (exists: %s)", DB_PATH, DB_PATH.exists())
    app = create_app()
    web.run_app(app, port=8099)
