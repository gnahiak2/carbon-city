from __future__ import annotations

from game.core.state import GameState


def warming_c(state: GameState) -> float:
    delta = state.co2_ppm - state.config.baseline_ppm
    return max(0.0, delta * state.config.warming_per_ppm)


def advance(state: GameState, emissions: float) -> None:
    """Add this tick's emissions, minus a small natural absorption."""
    if emissions < 0:
        emissions = 0.0
    ppm = state.co2_ppm
    ppm += emissions * state.config.ppm_per_kg_co2
    ppm -= state.config.co2_absorption
    state.co2_ppm = max(state.config.baseline_ppm, ppm)


def add_burst(state: GameState, ppm: float) -> None:
    state.co2_ppm += max(0.0, ppm)
