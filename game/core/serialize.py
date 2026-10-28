from __future__ import annotations

from typing import Any

from game.config import Config
from game.core import ai_civ, climate, economy, grid, power, warfare
from game.core.state import GameState, count_buildings, forest_count
from game.core.tips import active_tips


def _round(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def snapshot(state: GameState) -> dict[str, Any]:
    power_report = power.report(state)
    econ = economy.report(state, power_report)
    silos = count_buildings(state, "missile_silo")
    defeated = sum(1 for civ in state.civs if civ.defeated)
    victory = defeated == len(state.civs)
    expand_eco, expand_materials = grid.expansion_cost(state)

    return {
        "tick": state.tick,
        "resources": {
            "money": _round(state.money, 1),
            "materials": _round(state.materials, 1),
            "eco_points": _round(state.eco_points, 1),
            "eco_earned": _round(state.eco_earned, 1),
        },
        "stats": {
            "income": _round(econ.income, 1),
            "materials_rate": _round(econ.materials_rate, 1),
            "eco_rate": _round(econ.eco_rate, 1),
            "power_output": _round(power_report.supply, 1),
            "power_demand": _round(power_report.demand, 1),
            "power_ratio": _round(power_report.ratio, 3),
            "population": int(econ.population),
            "happiness": _round(econ.happiness, 1),
            "emissions": _round(econ.emissions, 1),
            "total_emissions": _round(econ.emissions + ai_civ.emissions(state), 1),
            "fallout": len(state.fallout),
            "forest": forest_count(state),
        },
        "climate": {
            "co2_ppm": _round(state.co2_ppm, 1),
            "warming_c": _round(climate.warming_c(state), 2),
            "baseline_ppm": _round(state.config.baseline_ppm, 1),
        },
        "grid": {
            "width": state.config.width,
            "height": state.config.height,
            "terrain": grid.terrain_rows(state),
            "unlocked": grid.unlocked_rows(state),
            "radius": state.radius,
            "can_expand": grid.can_expand(state),
            "expand_cost": {
                "eco": _round(expand_eco, 0),
                "materials": _round(expand_materials, 0),
            },
        },
        "buildings": [
            {"x": b.x, "z": b.z, "type": b.type}
            for b in sorted(state.buildings.values(), key=lambda b: (b.z, b.x))
        ],
        "fallout": [
            {"x": f.x, "z": f.z, "ttl": f.ttl}
            for f in sorted(state.fallout, key=lambda f: (f.z, f.x))
        ],
        "missiles": [
            {
                "id": m.id,
                "kind": m.kind,
                "x": _round(m.x, 2),
                "z": _round(m.z, 2),
                "tx": _round(m.tx, 2),
                "tz": _round(m.tz, 2),
                "progress": _round(m.progress, 3),
                "flight_ticks": m.flight_ticks,
            }
            for m in state.missiles
        ],
        "civs": [
            {
                "id": civ.id,
                "name": civ.name,
                "color": civ.color,
                "health": _round(civ.health, 1),
                "max_health": _round(civ.max_health, 1),
                "power": _round(civ.power, 1),
                "emissions": _round(
                    civ.emissions + civ.power * state.config.civ_emissions_per_power, 1
                )
                if not civ.defeated
                else 0.0,
                "description": civ.description,
                "defeated": civ.defeated,
                "target": {
                    "x": _round(warfare.civ_target(state, i)[0], 2),
                    "z": _round(warfare.civ_target(state, i)[1], 2),
                },
            }
            for i, civ in enumerate(state.civs)
        ],
        "tips": active_tips(state),
        "war": {
            "silos": silos,
            "can_launch": silos > 0 and not victory,
            "nuke_unlocked": state.eco_earned >= state.config.nuke_unlock_earned,
            "missile_cost": {
                "eco": _round(state.config.missile_cost_eco, 0),
                "materials": _round(state.config.missile_cost_materials, 0),
            },
            "nuke_cost": {
                "eco": _round(state.config.nuke_cost_eco, 0),
                "materials": _round(state.config.nuke_cost_materials, 0),
            },
            "damage": {
                "missile": _round(state.config.missile_damage, 0),
                "nuke": _round(state.config.nuke_damage, 0),
            },
        },
        "victory": victory,
        "last_attack": (
            {"tick": state.last_attack_tick, "civ": state.last_attack_civ}
            if state.last_attack_tick is not None
            else None
        ),
    }


def meta(config: Config) -> dict[str, Any]:
    return {
        "tick_seconds": config.tick_seconds,
        "grid": {"width": config.width, "height": config.height},
        "baseline_ppm": config.baseline_ppm,
        "silo_unlock_earned": config.silo_unlock_earned,
        "nuke_unlock_earned": config.nuke_unlock_earned,
        "materials_buy_cost_eco": config.materials_buy_cost_eco,
        "materials_buy_amount": config.materials_buy_amount,
    }
