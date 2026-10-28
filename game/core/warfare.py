from __future__ import annotations

import random

from game.catalog import BUILDINGS
from game.core import climate
from game.core.errors import GameError
from game.core.state import Civilization, Fallout, GameState, Missile, count_buildings


def civ_target(state: GameState, index: int) -> tuple[float, float]:
    """Where a rival civilisation sits on the map edge."""
    if index == 0:
        return (1.8, state.config.height * 0.42)
    return (state.config.width - 2.8, state.config.height * 0.3)


def _rng(state: GameState, salt: str) -> random.Random:
    return random.Random(f"{state.seed}:{state.tick}:{salt}")


def spawn_fallout(
    state: GameState, x: int, z: int, count: int, ttl: int | None = None, salt: str = ""
) -> None:
    ttl = state.config.fallout_ttl if ttl is None else ttl
    occupied = {(f.x, f.z) for f in state.fallout}
    every_tile = [
        (tx, tz)
        for tz in range(state.config.height)
        for tx in range(state.config.width)
    ]
    candidates = [
        (tx, tz)
        for (tx, tz) in every_tile
        if (tx, tz) not in occupied and abs(tx - x) <= 2 and abs(tz - z) <= 2
    ]
    if len(candidates) < count:
        candidates += [
            (tx, tz)
            for (tx, tz) in every_tile
            if (tx, tz) not in occupied and (tx, tz) not in candidates
        ]
    rng = _rng(state, f"fallout:{x}:{z}:{salt}")
    rng.shuffle(candidates)
    for tx, tz in candidates[:count]:
        state.fallout.append(Fallout(x=tx, z=tz, ttl=ttl))


def _silo_origin(state: GameState) -> tuple[float, float]:
    for (x, z), building in sorted(state.buildings.items()):
        if building.type == "missile_silo":
            return (x + 0.5, z + 0.5)
    raise GameError("Build a missile silo first.")


def launch(state: GameState, target_id: str, kind: str) -> Missile:
    if count_buildings(state, "missile_silo") == 0:
        raise GameError("You need a missile silo before you can launch anything.")

    civ_index = next(
        (i for i, civ in enumerate(state.civs) if civ.id == target_id), None
    )
    if civ_index is None:
        raise GameError("That civilisation does not exist.")
    civ = state.civs[civ_index]
    if civ.defeated:
        raise GameError(f"{civ.name} has already been defeated.")

    if kind == "missile":
        eco_cost = state.config.missile_cost_eco
        materials_cost = state.config.missile_cost_materials
        damage = state.config.missile_damage
        flight = state.config.missile_flight_ticks
    elif kind == "nuke":
        if state.eco_earned < state.config.nuke_unlock_earned:
            raise GameError(
                f"Nukes unlock at {state.config.nuke_unlock_earned:.0f} total Eco Points."
            )
        eco_cost = state.config.nuke_cost_eco
        materials_cost = state.config.nuke_cost_materials
        damage = state.config.nuke_damage
        flight = state.config.nuke_flight_ticks
    else:
        raise GameError("Unknown weapon type.")

    if state.eco_points < eco_cost:
        raise GameError(f"Not enough Eco Points ({eco_cost:.0f} needed).")
    if state.materials < materials_cost:
        raise GameError(f"Not enough materials ({materials_cost:.0f} needed).")

    state.eco_points -= eco_cost
    state.materials -= materials_cost
    x, z = _silo_origin(state)
    tx, tz = civ_target(state, civ_index)
    missile = Missile(
        id=state.next_id,
        kind=kind,
        x=x,
        z=z,
        tx=tx,
        tz=tz,
        flight_ticks=flight,
        target_civ=civ.id,
        damage=damage,
    )
    state.next_id += 1
    state.missiles.append(missile)
    return missile


def launch_enemy_strike(state: GameState, civ: Civilization) -> Missile:
    index = state.civs.index(civ)
    x, z = civ_target(state, index)
    targets = sorted(state.buildings)
    rng = _rng(state, f"strike:{civ.id}")
    if targets:
        tx_i, tz_i = rng.choice(targets)
    else:
        tx_i, tz_i = state.config.width // 2, state.config.height // 2
    missile = Missile(
        id=state.next_id,
        kind="enemy",
        x=x,
        z=z,
        tx=tx_i + 0.5,
        tz=tz_i + 0.5,
        flight_ticks=state.config.enemy_flight_ticks,
        target_civ=civ.id,
    )
    state.next_id += 1
    state.missiles.append(missile)
    return missile


def _impact(state: GameState, missile: Missile) -> None:
    if missile.kind == "enemy":
        civ = next((c for c in state.civs if c.id == missile.target_civ), None)
        x, z = int(missile.tx), int(missile.tz)
        if (x, z) in state.buildings:
            del state.buildings[(x, z)]
        state.money = max(0.0, state.money - state.config.attack_money_loss)
        state.last_attack_tick = state.tick
        state.last_attack_civ = civ.name if civ else "A rival"
        spawn_fallout(
            state,
            x,
            z,
            state.config.enemy_fallout_count,
            state.config.fallout_ttl,
            "enemy",
        )
        climate.add_burst(state, state.config.missile_ppm_burst)
        return

    civ = next((c for c in state.civs if c.id == missile.target_civ), None)
    if civ is not None and not civ.defeated:
        civ.health = max(0.0, civ.health - missile.damage)
        if civ.health <= 0:
            civ.defeated = True

    x, z = int(missile.tx), int(missile.tz)
    if missile.kind == "nuke":
        spawn_fallout(
            state,
            x,
            z,
            state.config.nuke_fallout_count,
            state.config.nuke_fallout_ttl,
            "nuke",
        )
        climate.add_burst(state, state.config.nuke_ppm_burst)
    else:
        spawn_fallout(
            state,
            x,
            z,
            state.config.missile_fallout_count,
            state.config.missile_fallout_ttl,
            "missile",
        )
        climate.add_burst(state, state.config.missile_ppm_burst)


def advance(state: GameState) -> None:
    remaining: list[Missile] = []
    for missile in state.missiles:
        missile.ticks += 1
        if missile.ticks >= missile.flight_ticks:
            _impact(state, missile)
        else:
            remaining.append(missile)
    state.missiles = remaining
