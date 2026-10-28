from __future__ import annotations

from dataclasses import dataclass, field

from game.config import Config

Coord = tuple[int, int]


@dataclass
class Building:
    type: str
    x: int
    z: int
    id: int


@dataclass
class Fallout:
    x: int
    z: int
    ttl: int


@dataclass
class Missile:
    id: int
    kind: str  # "missile" | "nuke" | "enemy"
    x: float
    z: float
    tx: float
    tz: float
    flight_ticks: int
    target_civ: str | None = None
    damage: float = 0.0
    ticks: int = 0

    @property
    def progress(self) -> float:
        if self.flight_ticks <= 0:
            return 1.0
        return min(1.0, self.ticks / self.flight_ticks)


@dataclass
class Civilization:
    id: str
    name: str
    color: list[float]
    health: float
    max_health: float
    power: float
    aggression: float
    emissions: float
    description: str
    defeated: bool = False


@dataclass
class GameState:
    config: Config
    seed: int
    tick: int
    terrain: list[list[str]]
    unlocked: set[Coord]
    radius: int
    buildings: dict[Coord, Building]
    fallout: list[Fallout]
    missiles: list[Missile]
    civs: list[Civilization]
    money: float
    materials: float
    eco_points: float
    eco_earned: float
    co2_ppm: float
    next_id: int = 1
    last_attack_tick: int | None = None
    last_attack_civ: str | None = None


def find_building(state: GameState, building_type: str) -> Building | None:
    for building in state.buildings.values():
        if building.type == building_type:
            return building
    return None


def count_buildings(state: GameState, building_type: str) -> int:
    return sum(1 for b in state.buildings.values() if b.type == building_type)


def count_category(state: GameState, category: str) -> int:
    from game.catalog import BUILDINGS

    return sum(
        1 for b in state.buildings.values() if BUILDINGS[b.type]["category"] == category
    )


def forest_count(state: GameState) -> int:
    return sum(row.count("f") for row in state.terrain)
