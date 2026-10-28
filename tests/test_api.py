from __future__ import annotations

import json

from game.core import simulation

from conftest import grass_tiles

SID = "testsession01"
SID2 = "testsession02"


def get_state(client, session=SID):
    response = client.get(f"/api/state?session={session}")
    assert response.status_code == 200
    return response.get_json()


def command(client, payload, session=SID):
    return client.post("/api/command", json={"session": session, **payload})


def test_index_serves_the_client(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Carbon City" in html
    assert "WebGPU" in html


def test_state_requires_a_valid_session(client):
    assert client.get("/api/state").status_code == 400
    assert client.get("/api/state?session=x").status_code == 400
    assert client.get(f"/api/state?session={SID}").status_code == 200


def test_state_includes_catalog_and_meta(client):
    payload = get_state(client)
    assert payload["session"] == SID
    assert "solar_plant" in payload["catalog"]
    assert payload["meta"]["grid"] == {"width": 24, "height": 24}
    assert payload["state"]["tick"] == 0


def test_commands_are_session_scoped(client):
    state = client.get(f"/api/state?session={SID}").get_json()["state"]
    terrain = state["grid"]["terrain"]
    (x, z) = next(
        (x, z)
        for z, row in enumerate(terrain)
        for x, tile in enumerate(row)
        if tile == "g" and state["grid"]["unlocked"][z][x] == "1"
    )
    response = command(client, {"type": "build", "x": x, "z": z, "building": "house"})
    assert response.status_code == 200
    assert response.get_json()["ok"] is True

    first = get_state(client, SID)["state"]
    second = get_state(client, SID2)["state"]
    assert any(b["x"] == x and b["z"] == z for b in first["buildings"])
    assert second["buildings"] == []


def test_invalid_commands_return_errors(client):
    assert command(client, {"type": "nonsense"}).status_code == 400
    assert command(client, {"type": "demolish", "x": 0, "z": 0}).status_code == 400


def test_save_and_load_roundtrip(client):
    state = get_state(client)["state"]
    (x, z) = next(
        (x, z)
        for z, row in enumerate(state["grid"]["terrain"])
        for x, tile in enumerate(row)
        if tile == "g" and state["grid"]["unlocked"][z][x] == "1"
    )
    assert command(client, {"type": "build", "x": x, "z": z, "building": "house"}).status_code == 200

    saved = client.post("/api/save", json={"session": SID})
    assert saved.status_code == 200

    assert command(client, {"type": "expand"}).status_code == 200
    changed = get_state(client)["state"]
    assert changed["grid"]["radius"] == 6

    loaded = client.post("/api/load", json={"session": SID})
    assert loaded.status_code == 200
    restored = loaded.get_json()["state"]
    assert restored["grid"]["radius"] == 4
    assert any(b["x"] == x and b["z"] == z for b in restored["buildings"])


def test_load_without_save_returns_404(client):
    response = client.post("/api/load", json={"session": "nosavehere"})
    assert response.status_code == 404


def test_sse_streams_initial_state(client):
    response = client.get(f"/api/stream?session={SID}", buffered=False)
    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    chunk = next(response.response).decode("utf-8")
    response.close()
    assert "event: state" in chunk
    data = json.loads(chunk.split("data:", 1)[1].strip())
    assert data["resources"]["money"] == 6000.0
