from __future__ import annotations

import math
import random

from game.core.state import Coord, GameState

WATER = "w"
ROCK = "r"
GRASS = "g"
FOREST = "f"

BUILDABLE = {GRASS, FOREST}


def generate_terrain(width: int, height: int, seed: int) -> list[list[str]]:
    """A readable map: grass, a river, a few lakes, rock and forest patches."""
    rng = random.Random(seed)
    terrain = [[GRASS for _ in range(width)] for _ in range(height)]
    cx, cy = width // 2, height // 2
    protected = 6

    def protected_tile(x: int, z: int) -> bool:
        return max(abs(x - cx), abs(z - cy)) <= protected

    # River down the right-hand side.
    river_x = int(width * 0.8)
    for z in range(height):
        x = river_x + round(math.sin(z / 3.6) * 1.8)
        for offset in (0, 1):
            tx = x + offset
            if 0 <= tx < width and not protected_tile(tx, z):
                terrain[z][tx] = WATER

    def blob(kind: str, count: int, min_radius: int, max_radius: int, salt: int) -> None:
        local = random.Random(seed + salt)
        placed = 0
        attempts = 0
        while placed < count and attempts < count * 20:
            attempts += 1
            bx = local.randint(2, width - 3)
            bz = local.randint(2, height - 3)
            if protected_tile(bx, bz):
                continue
            radius = local.randint(min_radius, max_radius)
            for z in range(bz - radius, bz + radius + 1):
                for x in range(bx - radius, bx + radius + 1):
                    if not (0 <= x < width and 0 <= z < height):
                        continue
                    if protected_tile(x, z):
                        continue
                    if (x - bx) ** 2 + (z - bz) ** 2 <= radius * radius:
                        terrain[z][x] = kind
            placed += 1

    blob(WATER, 2, 2, 3, 11)
    blob(ROCK, 5, 1, 2, 23)
    blob(FOREST, 7, 1, 2, 37)

    # Guarantee a clean, buildable town centre.
    for z in range(max(0, cy - 3), min(height, cy + 4)):
        for x in range(max(0, cx - 3), min(width, cx + 4)):
            terrain[z][x] = GRASS

    return terrain


def in_bounds(state: GameState, x: int, z: int) -> bool:
    return 0 <= x < state.config.width and 0 <= z < state.config.height


def is_unlocked(state: GameState, x: int, z: int) -> bool:
    return (x, z) in state.unlocked


def is_buildable_terrain(state: GameState, x: int, z: int) -> bool:
    return in_bounds(state, x, z) and state.terrain[z][x] in BUILDABLE


def unlock_area(state: GameState, radius: int) -> None:
    cx, cy = state.config.width // 2, state.config.height // 2
    for z in range(state.config.height):
        for x in range(state.config.width):
            if max(abs(x - cx), abs(z - cy)) <= radius:
                state.unlocked.add((x, z))


def expansion_cost(state: GameState) -> tuple[float, float]:
    steps = (state.radius - state.config.starting_radius) // state.config.expand_step
    eco = state.config.expand_cost_eco + steps * state.config.expand_cost_growth
    materials = state.config.expand_cost_materials + steps * state.config.expand_cost_growth
    return eco, materials


def can_expand(state: GameState) -> bool:
    return state.radius + state.config.expand_step <= state.config.max_radius


def terrain_rows(state: GameState) -> list[str]:
    return ["".join(row) for row in state.terrain]


def unlocked_rows(state: GameState) -> list[str]:
    return [
        "".join("1" if (x, z) in state.unlocked else "0" for x in range(state.config.width))
        for z in range(state.config.height)
    ]


def neighbours(x: int, z: int) -> list[Coord]:
    return [(x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)]


def has_road_neighbour(state: GameState, x: int, z: int) -> bool:
    for nx, nz in neighbours(x, z):
        building = state.buildings.get((nx, nz))
        if building is not None and building.type == "road":
            return True
    return False
