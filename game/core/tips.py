from __future__ import annotations

from game.catalog import BUILDINGS, load_tips
from game.core import climate, economy, power
from game.core.state import GameState, count_buildings, forest_count

MAX_TIPS = 3


def active_tips(state: GameState) -> list[dict[str, object]]:
    power_report = power.report(state)
    econ = economy.report(state, power_report)
    warming = climate.warming_c(state)
    text = load_tips()

    fossil_count = count_buildings(state, "coal_plant") + count_buildings(
        state, "gas_plant"
    )
    silos = count_buildings(state, "missile_silo")
    defeated = sum(1 for civ in state.civs if civ.defeated)
    has_income_building = any(
        BUILDINGS[b.type].get("income", 0) > 0 for b in state.buildings.values()
    )
    has_road = count_buildings(state, "road") > 0

    active: list[str] = []
    if defeated == len(state.civs):
        active.append("victory")
    if power_report.ratio < 0.999:
        active.append("power_shortage")
    if warming >= 2.0 and defeated < len(state.civs):
        active.append("warming_high")
    if (
        state.last_attack_tick is not None
        and state.tick - state.last_attack_tick <= 20
        and defeated < len(state.civs)
    ):
        active.append("under_attack")
    if fossil_count > 0:
        active.append("fossil_fuel")
    if state.eco_earned >= state.config.silo_unlock_earned and silos == 0:
        active.append("silo_unlocked")
    if (
        state.eco_earned >= state.config.nuke_unlock_earned
        and silos > 0
        and defeated < len(state.civs)
    ):
        active.append("nuke_unlocked")
    if econ.clean_output > 0 and fossil_count == 0:
        active.append("clean_start")
    if defeated == len(state.civs) - 1 and len(state.civs) > 0:
        active.append("one_rival_left")
    if state.eco_points >= 50 and silos == 0 and defeated < len(state.civs):
        active.append("unspent_eco")
    if state.materials < 10:
        active.append("low_materials")
    if forest_count(state) >= 10:
        active.append("forest")
    if has_income_building and not has_road:
        active.append("roads")
    if count_buildings(state, "park") == 0 and state.tick >= 20:
        active.append("park_tip")

    chosen = sorted(
        dict.fromkeys(active),
        key=lambda tip_id: int(text[tip_id].get("priority", 0)),
        reverse=True,
    )[:MAX_TIPS]
    return [
        {
            "id": tip_id,
            "level": text[tip_id]["level"],
            "title": text[tip_id]["title"],
            "body": text[tip_id]["body"],
        }
        for tip_id in chosen
    ]
