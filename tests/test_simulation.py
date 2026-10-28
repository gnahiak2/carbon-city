from __future__ import annotations

import pytest

from game.core import economy, grid, power, save, serialize, simulation
from game.core.errors import GameError

from conftest import grass_tiles


def test_build_deducts_resources_and_occupies_tile(state):
    (x, z) = grass_tiles(state, 1)[0]
    money = state.money
    materials = state.materials
    eco = state.eco_points
    simulation.build(state, x, z, "solar_plant")
    assert state.buildings[(x, z)].type == "solar_plant"
    assert state.money == money - 900
    assert state.materials == materials - 24
    assert state.eco_points == eco - 6
    with pytest.raises(GameError):
        simulation.build(state, x, z, "house")


def test_unlock_and_affordability_checks(state):
    (x, z), (x2, z2) = grass_tiles(state, 2)
    with pytest.raises(GameError, match="water or rock"):
        state.terrain[z2][x2] = grid.WATER
        simulation.build(state, x2, z2, "house")

    with pytest.raises(GameError, match="unlocks"):
        simulation.build(state, x, z, "nuclear_plant")

    state.eco_earned = 1000
    state.money = 10
    with pytest.raises(GameError, match="money"):
        simulation.build(state, x, z, "nuclear_plant")


def test_power_report_and_unpowered_income(state):
    (x, z) = grass_tiles(state, 1)[0]
    simulation.build(state, x, z, "apartment")
    report = power.report(state)
    assert report.supply == 0
    assert report.demand == 12
    assert report.ratio == 0
    econ = economy.report(state, report)
    assert econ.income == 0

    simulation.build(state, x + 1, z, "solar_plant")
    report = power.report(state)
    assert report.supply == 50
    assert report.ratio == 1
    assert economy.report(state, report).income > 0


def test_solar_earns_eco_and_tick_applies_it(state):
    (x, z) = grass_tiles(state, 1)[0]
    simulation.build(state, x, z, "solar_plant")
    eco_before = state.eco_points
    money_before = state.money
    simulation.tick(state)
    assert state.eco_points > eco_before
    assert state.eco_earned > state.config.starting_eco_points
    assert state.money >= money_before
    assert state.tick == 1


def test_coal_raises_co2_and_warming(state):
    (x, z) = grass_tiles(state, 1)[0]
    simulation.build(state, x, z, "coal_plant")
    assert state.co2_ppm == state.config.baseline_ppm
    simulation.tick(state)
    assert state.co2_ppm > state.config.baseline_ppm
    assert serialize.snapshot(state)["climate"]["warming_c"] > 0


def test_clearing_forest_releases_carbon(state):
    (x, z) = grass_tiles(state, 1)[0]
    state.terrain[z][x] = grid.FOREST
    before = state.co2_ppm
    simulation.build(state, x, z, "house")
    assert state.co2_ppm == before + state.config.forest_co2_on_clear
    assert state.terrain[z][x] == grid.GRASS


def test_demolish_refunds_and_frees_tile(state):
    (x, z) = grass_tiles(state, 1)[0]
    simulation.build(state, x, z, "house")
    money = state.money
    simulation.demolish(state, x, z)
    assert (x, z) not in state.buildings
    assert state.money == money + 300 * state.config.demolish_refund
    with pytest.raises(GameError):
        simulation.demolish(state, x, z)


def test_buy_materials(state):
    state.eco_points = 100
    simulation.buy_materials(state)
    assert state.materials == state.config.starting_materials + state.config.materials_buy_amount
    assert state.eco_points == 100 - state.config.materials_buy_cost_eco


def test_tips_warn_about_power_shortage(state):
    for (x, z) in grass_tiles(state, 3):
        simulation.build(state, x, z, "apartment")
    snapshot = serialize.snapshot(state)
    assert "power_shortage" in [tip["id"] for tip in snapshot["tips"]]


def test_serialize_has_expected_shape(state):
    snapshot = serialize.snapshot(state)
    assert len(snapshot["grid"]["terrain"]) == state.config.height
    assert len(snapshot["grid"]["terrain"][0]) == state.config.width
    assert len(snapshot["grid"]["unlocked"]) == state.config.height
    assert snapshot["grid"]["radius"] == state.config.starting_radius
    assert snapshot["resources"]["money"] == state.config.starting_money
    assert snapshot["victory"] is False


def test_save_roundtrip(state):
    (x, z) = grass_tiles(state, 1)[0]
    simulation.build(state, x, z, "wind_turbine")
    simulation.tick(state)
    data = save.to_save(state)
    restored = save.from_save(data)
    assert restored.tick == state.tick
    assert restored.money == pytest.approx(state.money)
    assert restored.buildings[(x, z)].type == "wind_turbine"
    assert serialize.snapshot(restored)["grid"]["unlocked"] == serialize.snapshot(state)["grid"]["unlocked"]
