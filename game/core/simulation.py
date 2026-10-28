from __future__ import annotations

import random

from game.catalog import BUILDINGS, load_civilizations
from game.config import DEFAULT_CONFIG, Config
from game.core import ai_civ, climate, economy, grid, power, warfare
from game.core.errors import GameError
from game.core.state import Building, Civilization, GameState


def new_game(seed: int | None = None, config: Config = DEFAULT_CONFIG) -> GameState:
    if seed is None:
        seed = random.randrange(1, 2**31)
    terrain = grid.generate_terrain(config.width, config.height, seed)
    state = GameState(
        config=config,
        seed=seed,
        tick=0,
        terrain=terrain,
        unlocked=set(),
        radius=config.starting_radius,
        buildings={},
        fallout=[],
        missiles=[],
        civs=[
            Civilization(
                id=data["id"],
                name=data["name"],
                color=list(data["color"]),
                health=float(data["health"]),
                max_health=float(data["health"]),
                power=float(data["power"]),
                aggression=float(data["aggression"]),
                emissions=float(data["emissions"]),
                description=data["description"],
            )
            for data in load_civilizations()
        ],
        money=config.starting_money,
        materials=config.starting_materials,
        eco_points=config.starting_eco_points,
        eco_earned=config.starting_eco_points,
        co2_ppm=config.baseline_ppm,
    )
    grid.unlock_area(state, state.radius)
    return state


def tick(state: GameState) -> None:
    power_report = power.report(state)
    econ = economy.report(state, power_report)
    state.money += econ.income
    state.materials += econ.materials_rate
    state.eco_points += econ.eco_rate
    state.eco_earned += econ.eco_rate

    warfare.advance(state)
    ai_civ.advance(state)

    for fallout in state.fallout:
        fallout.ttl -= 1
    state.fallout = [f for f in state.fallout if f.ttl > 0]

    total_emissions = economy.report(state).emissions + ai_civ.emissions(state)
    climate.advance(state, total_emissions)
    state.tick += 1


def build(state: GameState, x: int, z: int, building_type: str) -> Building:
    stats = BUILDINGS.get(building_type)
    if stats is None:
        raise GameError("Unknown building type.")
    if not grid.in_bounds(state, x, z):
        raise GameError("That tile is outside the map.")
    if not grid.is_unlocked(state, x, z):
        raise GameError("That land is not yours yet. Expand your city first.")
    if not grid.is_buildable_terrain(state, x, z):
        raise GameError("You cannot build on water or rock.")
    if (x, z) in state.buildings:
        raise GameError("That tile already has a building.")
    if state.eco_earned < stats.get("unlock_eco_earned", 0):
        raise GameError(
            f"{stats['name']} unlocks at {stats['unlock_eco_earned']:.0f} total Eco Points."
        )

    money_cost = float(stats.get("cost_money", 0))
    materials_cost = float(stats.get("cost_materials", 0))
    eco_cost = float(stats.get("cost_eco", 0))
    if state.money < money_cost:
        raise GameError(f"Not enough money (${money_cost:.0f} needed).")
    if state.materials < materials_cost:
        raise GameError(f"Not enough materials ({materials_cost:.0f} needed).")
    if state.eco_points < eco_cost:
        raise GameError(f"Not enough Eco Points ({eco_cost:.0f} needed).")

    state.money -= money_cost
    state.materials -= materials_cost
    state.eco_points -= eco_cost
    if state.terrain[z][x] == grid.FOREST:
        climate.add_burst(state, state.config.forest_co2_on_clear)
        state.terrain[z][x] = grid.GRASS

    building = Building(type=building_type, x=x, z=z, id=state.next_id)
    state.next_id += 1
    state.buildings[(x, z)] = building
    return building


def demolish(state: GameState, x: int, z: int) -> Building:
    building = state.buildings.pop((x, z), None)
    if building is None:
        raise GameError("There is nothing to demolish there.")
    stats = BUILDINGS[building.type]
    state.money += float(stats.get("cost_money", 0)) * state.config.demolish_refund
    state.materials += (
        float(stats.get("cost_materials", 0)) * state.config.demolish_refund
    )
    return building


def expand(state: GameState) -> None:
    if not grid.can_expand(state):
        raise GameError("Your city already reaches the edge of the map.")
    eco_cost, materials_cost = grid.expansion_cost(state)
    if state.eco_points < eco_cost:
        raise GameError(f"Not enough Eco Points ({eco_cost:.0f} needed).")
    if state.materials < materials_cost:
        raise GameError(f"Not enough materials ({materials_cost:.0f} needed).")
    state.eco_points -= eco_cost
    state.materials -= materials_cost
    state.radius += state.config.expand_step
    grid.unlock_area(state, state.radius)


def buy_materials(state: GameState) -> None:
    if state.eco_points < state.config.materials_buy_cost_eco:
        raise GameError(
            f"Not enough Eco Points ({state.config.materials_buy_cost_eco:.0f} needed)."
        )
    state.eco_points -= state.config.materials_buy_cost_eco
    state.materials += state.config.materials_buy_amount


def launch(state: GameState, target_id: str, kind: str) -> None:
    warfare.launch(state, target_id, kind)
