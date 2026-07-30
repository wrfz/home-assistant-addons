import sqlite3
import os
from pathlib import Path
from aiohttp import web
import jinja2
import aiohttp_jinja2

DB_PATH = Path("/config/home-assistant_v2.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@aiohttp_jinja2.template("index.html")
async def index(request):
    ingress = request.app["ingress"]
    conn = get_db()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    conn.close()
    return {"tables": [t["name"] for t in tables], "ingress": ingress}


@aiohttp_jinja2.template("table.html")
async def view_table(request):
    ingress = request.app["ingress"]
    table_name = request.match_info["table_name"]
    page = int(request.query.get("page", 1))
    page_size = int(request.query.get("page_size", 100))

    conn = get_db()

    valid = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    if not valid:
        conn.close()
        raise web.HTTPNotFound(text="Table not found")

    total_rows = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
    offset = (page - 1) * page_size

    rows = conn.execute(
        f'SELECT * FROM "{table_name}" LIMIT ? OFFSET ?', (page_size, offset)
    ).fetchall()

    columns = (
        [desc[0] for desc in conn.execute(f'SELECT * FROM "{table_name}" LIMIT 1').description]
        if rows
        else []
    )
    conn.close()

    total_pages = max(1, (total_rows + page_size - 1) // page_size)

    return {
        "table_name": table_name,
        "columns": columns,
        "rows": [dict(r) for r in rows],
        "page": page,
        "page_size": page_size,
        "total_rows": total_rows,
        "total_pages": total_pages,
        "ingress": ingress,
    }


def create_app():
    ingress = os.environ.get("INGRESS_PATH", "")
    app = web.Application()
    app["ingress"] = ingress
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader("/opt/templates"))

    prefix = ingress if ingress else ""
    app.router.add_get(f"{prefix}/", index)
    app.router.add_get(f"{prefix}/table/{{table_name}}", view_table)
    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, port=8099)
