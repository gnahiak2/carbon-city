from __future__ import annotations

import pytest

from game.core import ai_civ, serialize, simulation, warfare
from game.core.errors import GameError

from conftest import grass_tiles


def ready_for_war(state):
    state.eco_earned = 1000
    state.eco_points = 1000
    state.money = 20000
    state.materials = 1000
    (x, z) = grass_tiles(state, 1)[0]
    silo = simulation.build(state, x, z, "missile_silo")
    return silo


def test_launch_requires_silo(state):
    with pytest.raises(GameError, match="silo"):
        simulation.launch(state, state.civs[0].id, "missile")


def test_missile_flies_and_damages_civ(state):
    silo = ready_for_war(state)
    civ = state.civs[0]
    eco = state.eco_points
    materials = state.materials
    simulation.launch(state, civ.id, "missile")
    assert state.missiles
    assert state.eco_points == eco - state.config.missile_cost_eco
    assert state.materials == materials - state.config.missile_cost_materials
    missile = state.missiles[0]
    assert (missile.x, missile.z) == (silo.x + 0.5, silo.z + 0.5)

    for _ in range(state.config.missile_flight_ticks):
        simulation.tick(state)
    assert not state.missiles
    assert civ.health == civ.max_health - state.config.missile_damage
    assert state.fallout


def test_nuke_requires_eco_threshold(state):
    ready_for_war(state)
    state.eco_earned = 300
    with pytest.raises(GameError, match="Nukes unlock"):
        simulation.launch(state, state.civs[0].id, "nuke")
    state.eco_earned = state.config.nuke_unlock_earned
    simulation.launch(state, state.civs[0].id, "nuke")
    assert state.missiles[0].kind == "nuke"


def test_defeating_a_civ(state):
    ready_for_war(state)
    civ = state.civs[0]
    civ.health = 1
    simulation.launch(state, civ.id, "missile")
    for _ in range(state.config.missile_flight_ticks):
        simulation.tick(state)
    assert civ.defeated
    assert civ.health == 0
    assert serialize.snapshot(state)["civs"][0]["defeated"] is True
    with pytest.raises(GameError, match="already been defeated"):
        simulation.launch(state, civ.id, "missile")


def test_enemy_strike_destroys_a_building_and_leaves_fallout(state):
    (x, z) = grass_tiles(state, 1)[0]
    simulation.build(state, x, z, "house")
    state.tick = state.config.attack_grace_ticks
    civ = state.civs[0]
    civ.aggression = 1.0
    ai_civ.advance(state)
    enemy = [m for m in state.missiles if m.kind == "enemy"]
    assert enemy
    for _ in range(enemy[0].flight_ticks):
        warfare.advance(state)
    assert (x, z) not in state.buildings
    assert state.last_attack_tick == state.tick
    assert state.fallout
    assert any(tip["id"] == "under_attack" for tip in serialize.snapshot(state)["tips"])


def test_nuke_fallout_lands_at_the_impact_site(state):
    ready_for_war(state)
    simulation.launch(state, state.civs[0].id, "nuke")
    for _ in range(state.config.nuke_flight_ticks):
        simulation.tick(state)
    tx, tz = warfare.civ_target(state, 0)
    assert any(
        abs(f.x - int(tx)) <= 2 and abs(f.z - int(tz)) <= 2
        for f in state.fallout
    )


def test_fallout_decays(state):
    state.fallout = []
    warfare.spawn_fallout(state, 12, 12, 1, ttl=1)
    assert len(state.fallout) == 1
    simulation.tick(state)
    assert len(state.fallout) == 0
