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
    assert "Statistics Short Term" in appjs
    assert "statisticsShortTermConfig" in appjs
    assert "/api/statistics-short-term" in appjs
    assert "statistics_short_term" in appjs
