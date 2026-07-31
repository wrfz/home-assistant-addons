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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ha-sqlite-manager")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


async def index(request):
    log.info("Serving index page")
    return web.FileResponse(STATIC_DIR / "index.html")


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
    page = int(request.query.get("page", 1))
    page_size = int(request.query.get("page_size", 100))

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


def create_app():
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/api/tables", api_tables)
    app.router.add_get("/api/states", api_states)
    app.router.add_get("/api/table/{table_name}", api_table)
    return app


if __name__ == "__main__":
    log.info("Starting HA SQLite Manager on port 8099")
    log.info("Database: %s (exists: %s)", DB_PATH, DB_PATH.exists())
    app = create_app()
    web.run_app(app, port=8099)
