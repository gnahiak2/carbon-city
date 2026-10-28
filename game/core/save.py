from __future__ import annotations

from typing import Any

from game.catalog import BUILDINGS, load_civilizations
from game.config import DEFAULT_CONFIG, Config
from game.core import grid
from game.core.state import (
    Building,
    Civilization,
    Fallout,
    GameState,
    Missile,
)

SAVE_VERSION = 1


def to_save(state: GameState) -> dict[str, Any]:
    return {
        "version": SAVE_VERSION,
        "seed": state.seed,
        "tick": state.tick,
        "terrain": grid.terrain_rows(state),
        "unlocked": grid.unlocked_rows(state),
        "radius": state.radius,
        "money": state.money,
        "materials": state.materials,
        "eco_points": state.eco_points,
        "eco_earned": state.eco_earned,
        "co2_ppm": state.co2_ppm,
        "next_id": state.next_id,
        "last_attack_tick": state.last_attack_tick,
        "last_attack_civ": state.last_attack_civ,
        "buildings": [
            {"x": b.x, "z": b.z, "type": b.type}
            for b in sorted(state.buildings.values(), key=lambda b: (b.z, b.x))
        ],
        "fallout": [{"x": f.x, "z": f.z, "ttl": f.ttl} for f in state.fallout],
        "missiles": [
            {
                "id": m.id,
                "kind": m.kind,
                "x": m.x,
                "z": m.z,
                "tx": m.tx,
                "tz": m.tz,
                "flight_ticks": m.flight_ticks,
                "target_civ": m.target_civ,
                "damage": m.damage,
                "ticks": m.ticks,
            }
            for m in state.missiles
        ],
        "civs": [
            {
                "id": civ.id,
                "health": civ.health,
                "power": civ.power,
                "defeated": civ.defeated,
            }
            for civ in state.civs
        ],
    }


def from_save(data: dict[str, Any], config: Config = DEFAULT_CONFIG) -> GameState:
    if data.get("version") != SAVE_VERSION:
        raise ValueError("This save file was made by a different version of the game.")

    width, height = config.width, config.height
    terrain = data["terrain"]
    unlocked_rows = data["unlocked"]
    if (
        len(terrain) != height
        or any(len(row) != width for row in terrain)
        or len(unlocked_rows) != height
        or any(len(row) != width for row in unlocked_rows)
    ):
        raise ValueError("This save file does not match the current map size.")

    civ_data = {civ["id"]: civ for civ in data.get("civs", [])}
    civs: list[Civilization] = []
    for defaults in load_civilizations():
        saved = civ_data.get(defaults["id"], {})
        civs.append(
            Civilization(
                id=defaults["id"],
                name=defaults["name"],
                color=list(defaults["color"]),
                health=float(saved.get("health", defaults["health"])),
                max_health=float(defaults["health"]),
                power=float(saved.get("power", defaults["power"])),
                aggression=float(defaults["aggression"]),
                emissions=float(defaults["emissions"]),
                description=defaults["description"],
                defeated=bool(saved.get("defeated", False)),
            )
        )

    buildings: dict[tuple[int, int], Building] = {}
    for item in data.get("buildings", []):
        if item["type"] not in BUILDINGS:
            raise ValueError(f"Unknown building in save: {item['type']}")
        x, z = int(item["x"]), int(item["z"])
        buildings[(x, z)] = Building(type=item["type"], x=x, z=z, id=0)

    next_id = int(data.get("next_id", 1))
    for i, building in enumerate(
        sorted(buildings.values(), key=lambda b: (b.z, b.x)), start=1
    ):
        building.id = i
    next_id = max(next_id, len(buildings) + 1)

    unlocked = {
        (x, z)
        for z, row in enumerate(unlocked_rows)
        for x, value in enumerate(row)
        if value == "1"
    }

    state = GameState(
        config=config,
        seed=int(data["seed"]),
        tick=int(data["tick"]),
        terrain=[list(row) for row in terrain],
        unlocked=unlocked,
        radius=int(data["radius"]),
        buildings=buildings,
        fallout=[
            Fallout(x=int(f["x"]), z=int(f["z"]), ttl=int(f["ttl"]))
            for f in data.get("fallout", [])
        ],
        missiles=[
            Missile(
                id=int(m["id"]),
                kind=m["kind"],
                x=float(m["x"]),
                z=float(m["z"]),
                tx=float(m["tx"]),
                tz=float(m["tz"]),
                flight_ticks=int(m["flight_ticks"]),
                target_civ=m.get("target_civ"),
                damage=float(m.get("damage", 0)),
                ticks=int(m.get("ticks", 0)),
            )
            for m in data.get("missiles", [])
        ],
        civs=civs,
        money=float(data["money"]),
        materials=float(data["materials"]),
        eco_points=float(data["eco_points"]),
        eco_earned=float(data["eco_earned"]),
        co2_ppm=max(config.baseline_ppm, float(data["co2_ppm"])),
        next_id=next_id,
        last_attack_tick=data.get("last_attack_tick"),
        last_attack_civ=data.get("last_attack_civ"),
    )
    grid.unlock_area(state, state.radius)
    state.unlocked = unlocked
    return state
