import re
import shutil
import subprocess
from pathlib import Path

import pytest

HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not available")


def test_frontend_script_syntax(tmp_path):
    html = HTML.read_text()
    match = re.search(r"<script>(.*)</script>", html, re.S)
    assert match, "no inline script found"
    script = match.group(1)
    assert "__APP_VERSION__" in html
    out = tmp_path / "app.js"
    out.write_text(script)
    subprocess.run(["node", "--check", str(out)], check=True)


def test_frontend_has_version_placeholder():
    html = HTML.read_text()
    assert "__APP_VERSION__" in html


def test_frontend_has_short_term_usage():
    html = HTML.read_text()
    assert "Statistics Short Term" in html
    assert "statisticsShortTermConfig" in html
    assert "/api/statistics-short-term" in html
    assert "statistics_short_term" in html
