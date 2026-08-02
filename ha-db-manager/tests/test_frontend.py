import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "static" / "index.html"
APPJS = ROOT / "static" / "app.js"
STYLECSS = ROOT / "static" / "style.css"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not available")


def test_frontend_script_syntax():
    subprocess.run(["node", "--check", str(APPJS)], check=True)


def test_frontend_html_loads_external_assets():
    html = HTML.read_text()
    assert 'src="static/app.js?v=__APP_VERSION__"' in html
    assert 'href="static/style.css?v=__APP_VERSION__"' in html
    assert "<script>" not in html  # no inline JS left behind
    assert "<style>" not in html  # no inline CSS left behind


def test_frontend_has_version_placeholder():
    assert "__APP_VERSION__" in APPJS.read_text()


def test_frontend_has_short_term_usage():
    appjs = APPJS.read_text()
    assert "/api/table/" in appjs
    assert "counts" in appjs


def test_frontend_async_views_guard_against_stale_renders():
    appjs = APPJS.read_text()
    assert "function beginView()" in appjs
    assert "function isCurrentView(gen)" in appjs
    # every async view that fetches then renders must bump the generation
    # and bail out if a newer view started while awaiting.
    for view in ("showHome", "showTable"):
        assert f"async function {view}(" in appjs
        assert "beginView()" in appjs
    assert appjs.count("isCurrentView(gen)") >= 5


def test_frontend_no_removed_usage_special_cases():
    appjs = APPJS.read_text()
    for legacy in ("showUsageView", "showEntityStates", "showStatisticData",
                   "showEventTypeData", "statesConfig", "statisticsConfig",
                   "eventsConfig", "/api/statistics-short-term", "/api/event-types"):
        assert legacy not in appjs


def test_frontend_has_generic_table_links():
    appjs = APPJS.read_text()
    assert "function showLinked(" in appjs
    assert "tableFilter" in appjs
    assert "counts" in appjs
