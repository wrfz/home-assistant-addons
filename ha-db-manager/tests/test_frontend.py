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


def test_frontend_meta_tables_first_with_labels():
    appjs = APPJS.read_text()
    assert "t.counts" in appjs
    assert "table-gap" in appjs
    # count views use their friendly label, no "(counts)" suffix remains
    assert "t.label || t.name" in appjs
    assert "' (counts)'" not in appjs


def test_frontend_sort_reloads_in_place():
    appjs = APPJS.read_text()
    html = HTML.read_text()
    css = STYLECSS.read_text()
    # sorting/pagination re-fetch without wiping the table:
    assert "async function reloadTable(" in appjs
    assert "function showTitleProgress(" in appjs
    assert "updateTableInPlace(data" in appjs
    # header sort actions must route through reloadTable, not showTable:
    assert "reloadTable('${name}', 1, '${k}', '${d}'" in appjs
    # a small progress indicator sits next to the page title:
    assert 'id="title-progress"' in html
    assert "title-progress.hidden" in css
    # the full-content loading spinner must not be used for in-place reloads:
    reload_body = appjs.split("async function reloadTable(")[1].split("async function showLinked(")[0]
    assert "showLoading()" not in reload_body


def test_frontend_filtered_table_title_shows_filter_value():
    appjs = APPJS.read_text()
    # linked cells pass the displayed value through to the title
    assert "showLinked('${link.target}', '${link.filter_col}'" in appjs
    assert "filterLabel" in appjs
    # the title is composed as "<table> of `<value>`" when filtered
    assert "`${meta.label || name} of \\`${filterLabel}\\``" in appjs
    assert "showTable(bt.name, bt.page, bt.sortKey, bt.sortDir, bt.filter, bt.filterLabel)" in appjs

