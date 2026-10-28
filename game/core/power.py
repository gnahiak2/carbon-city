from __future__ import annotations

from dataclasses import dataclass

from game.catalog import BUILDINGS
from game.core.state import GameState


@dataclass(frozen=True)
class PowerReport:
    supply: float
    demand: float

    @property
    def ratio(self) -> float:
        if self.demand <= 0:
            return 1.0
        return min(1.0, self.supply / self.demand)


def report(state: GameState) -> PowerReport:
    supply = 0.0
    demand = 0.0
    for building in state.buildings.values():
        stats = BUILDINGS[building.type]
        supply += stats.get("power_output", 0)
        demand += stats.get("power_demand", 0)
    return PowerReport(supply=supply, demand=demand)
