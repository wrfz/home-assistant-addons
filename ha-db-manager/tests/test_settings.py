import json

import db
import app as app_module


async def test_settings_default(client):
    r = await client.get("/api/settings")
    assert r.status == 200
    data = await r.json()
    assert data["watch_interval"] == 3
    assert data["clients"] == 0
    assert data["views"] == 0


async def test_settings_set(client):
    r = await client.post("/api/settings", json={"watch_interval": 7})
    assert r.status == 200
    data = await r.json()
    assert data["watch_interval"] == 7


async def test_settings_invalid(client):
    r = await client.post("/api/settings", json={"watch_interval": 0})
    assert r.status == 400
    r = await client.post("/api/settings", json={"watch_interval": 999})
    assert r.status == 400
    r = await client.post("/api/settings", json={"watch_interval": "x"})
    assert r.status == 400
    r = await client.post("/api/settings", data="not json")
    assert r.status == 400


async def test_settings_persisted_across_reboot(client, tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setenv("HA_SQLITE_SETTINGS_FILE", str(settings_file))
    r = await client.post("/api/settings", json={"watch_interval": 9})
    assert r.status == 200
    assert json.loads(settings_file.read_text())["watch_interval"] == 9

    # simulate app reboot: fresh app instance loads from file
    app2 = app_module.create_app()
    assert app2["state"]["watch_interval"] == 9
