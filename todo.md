# Carbon City — todo (WebGPU architecture)

One Python simulation, one static browser client. No build step: the client is
plain ES modules plus WGSL served by Flask.

## Simulation (Python)
- [x] Tunable numbers in `game/config.py`, content in `game/data/*.json`
- [x] Grid + terrain generation, land unlocking and build validation
- [x] Power supply/demand, economy, climate (CO2 ppm + warming)
- [x] Two AI civilisations and warfare (silos, missiles, nukes, fallout)
- [x] Contextual advisor tips for students
- [x] State serialisation and save/load

## Server
- [x] Flask app serving the client and JSON endpoints
- [x] Background ticker thread
- [x] SSE state stream
- [x] Per-session game state (session id from the browser)
- [x] Command endpoint: build, demolish, expand, buy materials, launch

## WebGPU client
- [x] WebGPU availability check with a clear fallback message
- [x] Perspective orbit camera (drag, wheel zoom, right-drag pan)
- [x] Instanced box geometry: terrain, roads, buildings, missiles, fallout
- [x] Directional lighting + emissive glow for hot/fresh objects
- [x] Mouse picking and tile placement
- [x] HUD: eco points, money, materials, power, CO2/warming, population
- [x] Build menu, advisor tips, war room, save/load
- [x] Session-scoped state on the client

## Verification
- [x] Pytest suite for simulation and HTTP API
- [x] README with run instructions
- [x] Browser smoke test with WebGPU and with WebGPU disabled
