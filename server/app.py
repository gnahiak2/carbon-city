from __future__ import annotations

import json
import logging
import mimetypes
import threading
import time
from pathlib import Path
from typing import Any, Iterator

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    request,
    send_from_directory,
    stream_with_context,
)

from game.catalog import BUILDINGS, CATEGORIES
from game.config import DEFAULT_CONFIG, Config
from game.core import save, serialize, simulation
from game.core.errors import GameError
from game.sessions import GameSession, SessionRegistry, is_valid_session_id

mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/plain", ".wgsl")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
DEFAULT_SAVES_DIR = Path(__file__).resolve().parent / "saves"
LOG = logging.getLogger("carbon_city")


def _error(message: str, status: int = 400) -> tuple[Response, int]:
    return jsonify({"ok": False, "error": message}), status


def _session_id(body: dict[str, Any] | None = None) -> str | None:
    session_id = request.args.get("session") or request.headers.get("X-Session-Id")
    if session_id is None and body is not None:
        session_id = body.get("session")
    return str(session_id) if session_id is not None else None


def _tick_loop(registry: SessionRegistry, stop: threading.Event, interval: float) -> None:
    ticks = 0
    while not stop.wait(interval):
        try:
            registry.tick_all()
        except Exception:  # keep the ticker alive no matter what
            LOG.exception("tick failed")
        ticks += 1
        if ticks % 60 == 0:
            registry.prune()


def create_app(
    config: Config = DEFAULT_CONFIG,
    *,
    start_ticker: bool = True,
    saves_dir: Path | str | None = None,
) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["SAVES_DIR"] = str(saves_dir or DEFAULT_SAVES_DIR)
    Path(app.config["SAVES_DIR"]).mkdir(parents=True, exist_ok=True)

    registry = SessionRegistry(config)
    app.extensions["registry"] = registry

    if start_ticker:
        stop = threading.Event()
        thread = threading.Thread(
            target=_tick_loop,
            args=(registry, stop, config.tick_seconds),
            daemon=True,
            name="carbon-city-ticker",
        )
        app.extensions["ticker_stop"] = stop
        thread.start()

    # -- pages ---------------------------------------------------------------

    @app.get("/")
    def index() -> Response:
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/favicon.ico")
    def favicon() -> Response:
        return Response(status=204)

    @app.get("/<path:filename>")
    def static_files(filename: str) -> Response:
        if filename.startswith("api/"):
            abort(404)
        return send_from_directory(WEB_DIR, filename)

    # -- state ---------------------------------------------------------------

    @app.get("/api/state")
    def get_state() -> Response:
        session_id = _session_id()
        if not is_valid_session_id(session_id):
            return _error("Missing or invalid session id.")
        session = registry.get_or_create(str(session_id))
        session.touch()
        return jsonify(
            {
                "ok": True,
                "session": session.id,
                "state": session.snapshot(),
                "catalog": BUILDINGS,
                "categories": CATEGORIES,
                "meta": serialize.meta(config),
            }
        )

    @app.post("/api/command")
    def command() -> Response:
        body = request.get_json(silent=True) or {}
        session_id = _session_id(body)
        if not is_valid_session_id(session_id):
            return _error("Missing or invalid session id.")

        command_type = body.get("type")
        session = registry.get_or_create(str(session_id))
        try:
            with session.lock:
                state = session.state
                if command_type == "build":
                    simulation.build(
                        state, int(body["x"]), int(body["z"]), str(body["building"])
                    )
                elif command_type == "demolish":
                    simulation.demolish(state, int(body["x"]), int(body["z"]))
                elif command_type == "expand":
                    simulation.expand(state)
                elif command_type == "buy_materials":
                    simulation.buy_materials(state)
                elif command_type == "launch":
                    simulation.launch(
                        state, str(body["target"]), str(body["kind"])
                    )
                else:
                    return _error("Unknown command.")
                session.version += 1
                payload = serialize.snapshot(state)
        except GameError as exc:
            return _error(str(exc))
        except (KeyError, TypeError, ValueError):
            return _error("Invalid command.")
        session.touch()
        return jsonify({"ok": True, "state": payload})

    # -- save / load ---------------------------------------------------------

    def _save_path(session_id: str) -> Path:
        return Path(app.config["SAVES_DIR"]) / f"{session_id}.json"

    @app.post("/api/save")
    def save_game() -> Response:
        body = request.get_json(silent=True) or {}
        session_id = _session_id(body)
        if not is_valid_session_id(session_id):
            return _error("Missing or invalid session id.")
        session = registry.get_or_create(str(session_id))
        with session.lock:
            data = save.to_save(session.state)
        path = _save_path(session.id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
        session.touch()
        return jsonify({"ok": True, "saved_at": time.time()})

    @app.post("/api/load")
    def load_game() -> Response:
        body = request.get_json(silent=True) or {}
        session_id = _session_id(body)
        if not is_valid_session_id(session_id):
            return _error("Missing or invalid session id.")
        path = _save_path(str(session_id))
        if not path.exists():
            return _error("No saved city for this session yet.", 404)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            state = save.from_save(data, config)
        except (ValueError, KeyError, TypeError) as exc:
            return _error(f"Could not load save: {exc}")

        session = registry.replace_state(str(session_id), state)
        session.touch()
        return jsonify({"ok": True, "state": session.snapshot()})

    # -- SSE -----------------------------------------------------------------

    @app.get("/api/stream")
    def stream() -> Response:
        session_id = _session_id()
        if not is_valid_session_id(session_id):
            return _error("Missing or invalid session id.")
        session = registry.get_or_create(str(session_id))

        @stream_with_context
        def events() -> Iterator[str]:
            last_version = -1
            last_touch = 0.0
            last_ping = 0.0
            try:
                while True:
                    with session.lock:
                        version = session.version
                        if version != last_version:
                            payload = json.dumps(
                                serialize.snapshot(session.state),
                                separators=(",", ":"),
                            )
                        else:
                            payload = None
                    if payload is not None:
                        last_version = version
                        yield f"event: state\ndata: {payload}\n\n"
                    else:
                        now = time.time()
                        if now - last_ping >= 10:
                            last_ping = now
                            yield ": keepalive\n\n"
                    now = time.time()
                    if now - last_touch > 5:
                        session.touch()
                        last_touch = now
                    time.sleep(0.25)
            except GeneratorExit:
                return

        return Response(
            events(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.after_request
    def no_cache(response: Response) -> Response:
        if request.path.startswith("/api/") or request.path.startswith("/js/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    return app
