from __future__ import annotations

from game.core import grid, simulation


def test_terrain_is_deterministic_and_sized():
    a = grid.generate_terrain(24, 24, 7)
    b = grid.generate_terrain(24, 24, 7)
    assert a == b
    assert len(a) == 24
    assert all(len(row) == 24 for row in a)
    assert {tile for row in a for tile in row} <= {"g", "w", "r", "f"}


def test_centre_is_clear_and_unlocked():
    state = simulation.new_game(seed=1)
    cx, cy = state.config.width // 2, state.config.height // 2
    for z in range(cy - 3, cy + 4):
        for x in range(cx - 3, cx + 4):
            assert state.terrain[z][x] == grid.GRASS
            assert (x, z) in state.unlocked
    assert len(state.unlocked) == 9 * 9


def test_expansion_cost_grows_and_unlocks_more_land():
    state = simulation.new_game(seed=1)
    before = len(state.unlocked)
    eco, materials = grid.expansion_cost(state)
    state.eco_points = 1000
    state.materials = 1000
    simulation.expand(state)
    assert state.radius == state.config.starting_radius + state.config.expand_step
    assert len(state.unlocked) > before
    assert state.eco_points == 1000 - eco
    assert state.materials == 1000 - materials
    assert grid.expansion_cost(state)[0] > eco


def test_cannot_build_on_water_rock_or_outside():
    state = simulation.new_game(seed=1)
    cx, cy = state.config.width // 2, state.config.height // 2
    state.terrain[cy][cx] = grid.WATER
    assert not grid.is_buildable_terrain(state, cx, cy)
    state.terrain[cy][cx] = grid.ROCK
    assert not grid.is_buildable_terrain(state, cx, cy)
    assert not grid.is_buildable_terrain(state, -1, 0)
