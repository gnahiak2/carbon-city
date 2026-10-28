from __future__ import annotations

import random

from game.core import warfare
from game.core.state import GameState


def emissions(state: GameState) -> float:
    return sum(
        civ.emissions + civ.power * state.config.civ_emissions_per_power
        for civ in state.civs
        if not civ.defeated
    )


def advance(state: GameState) -> None:
    if state.tick < state.config.attack_grace_ticks:
        return

    for civ in state.civs:
        if civ.defeated:
            continue
        civ.power += state.config.civ_power_growth
        rng = random.Random(f"{state.seed}:{state.tick}:{civ.id}")
        if rng.random() < civ.aggression:
            warfare.launch_enemy_strike(state, civ)
