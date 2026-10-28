# Carbon City

A browser-playable city builder that teaches energy use and global warming.
The simulation is authoritative Python. The 3D view is plain ES modules and
WGSL on WebGPU, served by Flask. There is no Node, bundler, pygame or WASM
pipeline.

## Run it

Tested with Homebrew Python 3.15 on macOS. Python 3.12+ should work.

```bash
/opt/homebrew/bin/python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
```

Open **http://127.0.0.1:8000**.

Use a current Chrome or Edge, or Safari 26+. Carbon City shows a clear
"WebGPU is not available in this browser" message with a browser hint if the
canvas cannot start.

Optional flags: `--host 0.0.0.0 --port 8080` (defaults are `127.0.0.1:8000`).

## How to play

- **Eco Points** come from clean power, parks and surviving forest. Spend them
  on clean/premium buildings, materials, land, and eventually a missile silo.
- **Money** comes from population tax, shops and factories. **Materials** come
  from factories and Eco Point purchases.
- Coal and gas are cheap and make lots of power, but they add CO2. CO2 raises
  the global temperature meter. Clean power earns Eco Points instead.
- **Expand Land** unlocks another ring of tiles. Water and rock cannot be built
  on; building on forest releases some stored carbon.
- Roads boost the income of adjacent shops and factories.
- The **Advisor** gives short, friendly tips based on what your city needs.
- Two AI civilisations keep emitting and may attack your city. The **War Room**
  shows their health. Build a silo to launch missiles; nukes unlock later.
  Every strike adds CO2 and fallout, so war has a climate cost.
- **Save** writes your city to `server/saves/<session>.json`; **Load** restores
  it.

### Controls

| Input | Action |
| --- | --- |
| Left drag | Orbit the camera |
| Wheel | Zoom |
| Right drag | Pan |
| Click a tile | Place the selected building |
| Esc | Cancel the tool / close the war room |

## Per-visitor cities

The browser creates a UUID stored in `localStorage` and sends it with every
request and SSE connection. The server keeps one `GameSession` per id, so two
visitors cannot control the same city. Sessions live in memory and expire after
two hours idle; save/load provides persistence across server restarts.

## Project layout

```text
run.py                    server entry point
game/
  config.py               all tunable simulation numbers
  data/*.json             buildings, civilisations, advisor tip text
  catalog.py              JSON loading + category order
  core/
    grid.py               terrain generation, unlocking, build checks
    state.py              dataclasses for the world
    power.py              supply / demand
    economy.py            income, materials, Eco Points, emissions, happiness
    climate.py            CO2 ppm and warming
    ai_civ.py             the two rival civilisations
    warfare.py            silos, missiles, nukes, fallout, enemy strikes
    tips.py               contextual advisor rules
    simulation.py         tick + player commands
    serialize.py          state for the client
    save.py               save/load format
  sessions.py             one city per session id
server/
  app.py                  Flask routes, SSE, ticker thread
  saves/                  per-session saves (gitignored)
web/
  index.html              canvas + overlay containers
  style.css               HUD styling
  js/main.js              boot, input, wiring
  js/renderer.js          instanced box renderer
  js/hud.js               HUD, build menu, tips, war room
  js/camera.js            orbit camera and ray picking
  js/gpu.js               WebGPU availability / adapter setup
  js/api.js               session id, REST + SSE client
  js/shaders/scene.wgsl   lighting / instancing shader
tests/                    pytest suite
```

## HTTP API

All endpoints take `?session=<id>` (or `X-Session-Id`, or `session` in the POST
body).

- `GET /api/state` — session state, building catalog, categories, metadata
- `GET /api/stream?session=...` — SSE `state` events every tick
- `POST /api/command` — `build`, `demolish`, `expand`, `buy_materials`, `launch`
- `POST /api/save`, `POST /api/load`

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/command \
  -H 'Content-Type: application/json' \
  -d '{"session":"mysession","type":"build","x":12,"z":12,"building":"solar_plant"}'
```

## Tests

```bash
.venv/bin/python -m pytest -q
```

The suite covers terrain, build validation, power, economy, climate, warfare,
save/load, session isolation, the HTTP commands, and the SSE stream. A separate
Playwright smoke check (not part of pytest) was used during development to
confirm the WebGPU client renders, places buildings, saves/loads, and shows the
fallback overlay when `navigator.gpu` is absent.

## Tuning

Edit `game/config.py` for balance numbers (starting resources, costs, climate
sensitivity, missile damage, attack chances) and `game/data/*.json` for
building stats, civilisations and tip text. No client rebuild is needed: reload
the page.
