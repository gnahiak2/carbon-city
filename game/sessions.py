from __future__ import annotations

import hashlib
import re
import threading
import time

from game.config import DEFAULT_CONFIG, Config
from game.core import serialize, simulation
from game.core.state import GameState

SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


def is_valid_session_id(session_id: str | None) -> bool:
    return bool(session_id and SESSION_ID_RE.match(session_id))


def _seed_for(session_id: str) -> int:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


class GameSession:
    def __init__(self, session_id: str, state: GameState) -> None:
        self.id = session_id
        self.state = state
        self.lock = threading.RLock()
        self.version = 0
        self.created_at = time.time()
        self.last_seen = self.created_at

    def touch(self) -> None:
        self.last_seen = time.time()

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return serialize.snapshot(self.state)


class SessionRegistry:
    """One authoritative city per browser session."""

    def __init__(self, config: Config = DEFAULT_CONFIG) -> None:
        self.config = config
        self._sessions: dict[str, GameSession] = {}
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str) -> GameSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                state = simulation.new_game(seed=_seed_for(session_id), config=self.config)
                session = GameSession(session_id, state)
                self._sessions[session_id] = session
            session.touch()
            return session

    def get(self, session_id: str) -> GameSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def tick_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            with session.lock:
                simulation.tick(session.state)
                session.version += 1

    def tick(self, session_id: str) -> None:
        session = self.get(session_id)
        if session is None:
            raise KeyError(session_id)
        with session.lock:
            simulation.tick(session.state)
            session.version += 1

    def replace_state(self, session_id: str, state: GameState) -> GameSession:
        session = self.get_or_create(session_id)
        with session.lock:
            session.state = state
            session.version += 1
        return session

    def prune(self, ttl_seconds: int | None = None) -> int:
        ttl = self.config.session_ttl_seconds if ttl_seconds is None else ttl_seconds
        cutoff = time.time() - ttl
        with self._lock:
            stale = [
                session_id
                for session_id, session in self._sessions.items()
                if session.last_seen < cutoff
            ]
            for session_id in stale:
                del self._sessions[session_id]
        return len(stale)

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)
