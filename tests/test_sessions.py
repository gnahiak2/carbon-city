from __future__ import annotations

import time

from game.core import simulation
from game.sessions import SessionRegistry, is_valid_session_id

from conftest import grass_tiles


def test_session_ids_are_validated():
    assert is_valid_session_id("abc12345")
    assert is_valid_session_id("a" * 64)
    assert not is_valid_session_id("short")
    assert not is_valid_session_id("../bad")
    assert not is_valid_session_id("a" * 65)
    assert not is_valid_session_id(None)


def test_sessions_are_isolated():
    registry = SessionRegistry()
    a = registry.get_or_create("session-aaaa")
    b = registry.get_or_create("session-bbbb")
    (x, z) = grass_tiles(a.state, 1)[0]
    simulation.build(a.state, x, z, "house")
    a.version += 1
    assert (x, z) in a.state.buildings
    assert not b.state.buildings
    assert a.state is not b.state


def test_same_id_returns_same_city_and_same_seed_terrain():
    registry = SessionRegistry()
    first = registry.get_or_create("session-same")
    second = registry.get_or_create("session-same")
    assert first is second

    other = SessionRegistry()
    recreated = other.get_or_create("session-same")
    assert recreated.state.terrain == first.state.terrain
    assert recreated.state.seed == first.state.seed


def test_tick_all_advances_every_session():
    registry = SessionRegistry()
    a = registry.get_or_create("session-aaaa")
    b = registry.get_or_create("session-bbbb")
    registry.tick_all()
    assert a.state.tick == 1
    assert b.state.tick == 1
    assert a.version == 1


def test_prune_removes_idle_sessions():
    registry = SessionRegistry()
    registry.get_or_create("session-aaaa")
    registry.get_or_create("session-bbbb")
    assert len(registry) == 2
    time.sleep(0.01)
    assert registry.prune(ttl_seconds=0) == 2
    assert len(registry) == 0
