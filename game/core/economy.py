from __future__ import annotations

from dataclasses import dataclass

from game.catalog import BUILDINGS
from game.core import power
from game.core.grid import has_road_neighbour
from game.core.state import GameState, forest_count


@dataclass(frozen=True)
class EconomyReport:
    income: float
    materials_rate: float
    eco_rate: float
    emissions: float
    population: float
    clean_output: float
    happiness: float


def report(state: GameState, power_report: power.PowerReport | None = None) -> EconomyReport:
    if power_report is None:
        power_report = power.report(state)

    income = 0.0
    materials_rate = state.config.materials_per_tick
    eco_rate = 0.0
    emissions = 0.0
    population = 0.0
    clean_output = 0.0
    parks = 0

    for building in state.buildings.values():
        stats = BUILDINGS[building.type]
        population += stats.get("population", 0)
        parks += 1 if building.type == "park" else 0
        emissions += stats.get("emissions", 0)
        eco_rate += stats.get("eco", 0)

        if stats.get("category") == "industry":
            materials_rate += state.config.materials_per_factory

        output = stats.get("power_output", 0)
        if output > 0 and stats.get("emissions", 0) == 0:
            clean_output += output

        building_income = stats.get("income", 0)
        if building_income and has_road_neighbour(state, building.x, building.z):
            building_income *= 1.0 + state.config.road_income_bonus
        income += building_income

    income += population * state.config.tax_per_person
    income *= power_report.ratio

    # Fallout makes people stay home and spend less.
    fallout_penalty = max(
        0.5, 1.0 - len(state.fallout) * state.config.fallout_income_penalty
    )
    income *= fallout_penalty

    eco_rate += clean_output * state.config.eco_per_clean_kw
    eco_rate += forest_count(state) * state.config.eco_per_forest

    happiness = (
        state.config.happiness_base
        + parks * state.config.happiness_per_park
        - len(state.fallout) * state.config.happiness_per_fallout
    )
    happiness += (
        state.config.happiness_powered_bonus
        if power_report.ratio >= 1.0
        else -state.config.happiness_unpowered_penalty
    )
    happiness += min(
        state.config.happiness_forest_cap,
        forest_count(state) * state.config.happiness_forest_bonus,
    )
    happiness = max(0.0, min(100.0, happiness))

    return EconomyReport(
        income=income,
        materials_rate=materials_rate,
        eco_rate=eco_rate,
        emissions=emissions,
        population=population,
        clean_output=clean_output,
        happiness=happiness,
    )
