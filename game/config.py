from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Every tunable number for the simulation lives here."""

    # World
    width: int = 24
    height: int = 24
    tick_seconds: float = 1.0

    # Starting resources
    starting_money: float = 6000.0
    starting_materials: float = 120.0
    starting_eco_points: float = 40.0
    starting_radius: int = 4

    # Land expansion
    expand_step: int = 2
    expand_cost_eco: float = 40.0
    expand_cost_materials: float = 40.0
    expand_cost_growth: float = 20.0

    # Resources per tick
    materials_per_tick: float = 2.0
    materials_per_factory: float = 2.0
    materials_buy_amount: float = 50.0
    materials_buy_cost_eco: float = 20.0
    demolish_refund: float = 0.25
    tax_per_person: float = 0.35
    road_income_bonus: float = 0.25
    fallout_income_penalty: float = 0.01
    eco_per_clean_kw: float = 0.02
    eco_per_forest: float = 0.02

    # Happiness
    happiness_base: float = 65.0
    happiness_per_park: float = 4.0
    happiness_per_fallout: float = 2.0
    happiness_powered_bonus: float = 10.0
    happiness_unpowered_penalty: float = 25.0
    happiness_forest_bonus: float = 0.1
    happiness_forest_cap: float = 10.0

    # Rival civilisations
    civ_power_growth: float = 0.05
    civ_emissions_per_power: float = 0.03

    # Climate
    baseline_ppm: float = 420.0
    ppm_per_kg_co2: float = 0.002
    co2_absorption: float = 0.02
    warming_per_ppm: float = 0.05
    forest_co2_on_clear: float = 0.4
    nuke_ppm_burst: float = 2.5
    missile_ppm_burst: float = 0.2

    # Warfare
    silo_unlock_earned: float = 200.0
    nuke_unlock_earned: float = 450.0
    missile_cost_eco: float = 50.0
    missile_cost_materials: float = 25.0
    missile_damage: float = 40.0
    missile_flight_ticks: int = 4
    nuke_cost_eco: float = 140.0
    nuke_cost_materials: float = 70.0
    nuke_damage: float = 90.0
    nuke_flight_ticks: int = 5
    attack_grace_ticks: int = 20
    attack_money_loss: float = 250.0
    fallout_ttl: int = 60
    enemy_flight_ticks: int = 3
    enemy_fallout_count: int = 2
    missile_fallout_count: int = 2
    missile_fallout_ttl: int = 45
    nuke_fallout_count: int = 5
    nuke_fallout_ttl: int = 90

    # Sessions
    session_ttl_seconds: int = 7200

    @property
    def max_radius(self) -> int:
        return min(self.width, self.height) // 2


DEFAULT_CONFIG = Config()
