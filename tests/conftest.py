from __future__ import annotations

import pytest

from game.config import Config
from game.core import simulation
from server.app import create_app

TEST_CONFIG = Config(tick_seconds=0.2)


@pytest.fixture
def state():
    return simulation.new_game(seed=42, config=TEST_CONFIG)


@pytest.fixture
def app(tmp_path):
    app = create_app(TEST_CONFIG, start_ticker=False, saves_dir=tmp_path)
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def grass_tiles(state, count: int) -> list[tuple[int, int]]:
    from game.core.grid import GRASS

    tiles = [
        (x, z)
        for z, row in enumerate(state.terrain)
        for x, value in enumerate(row)
        if value == GRASS and (x, z) in state.unlocked
    ]
    return tiles[:count]
