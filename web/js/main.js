import { CarbonApi, getSessionId } from "./api.js";
import { OrbitCamera } from "./camera.js";
import { initWebGPU, WebGPUUnavailable } from "./gpu.js";
import { Hud } from "./hud.js";
import { SceneRenderer } from "./renderer.js";

const canvas = document.getElementById("scene");
const loading = document.getElementById("loading");
const unsupported = document.getElementById("unsupported");
const unsupportedTitle = document.getElementById("unsupported-title");
const unsupportedDetail = document.getElementById("unsupported-detail");

let api = null;
let hud = null;
let renderer = null;
let camera = null;
let currentState = null;
let selectedType = null;
let demolishMode = false;
let rendering = true;

function showUnsupported(detail, title = "WebGPU is not available in this browser") {
  loading.hidden = true;
  unsupported.hidden = false;
  unsupportedTitle.textContent = title;
  unsupportedDetail.textContent = detail ? `Details: ${detail}` : "";
}

function showStartupError(message) {
  loading.hidden = false;
  const card = loading.querySelector(".card");
  card.querySelector(".spinner")?.remove();
  card.querySelector("h1").textContent = "Could not start Carbon City";
  const paragraph = card.querySelector("p");
  if (paragraph) paragraph.textContent = message;
}

function applyState(state) {
  const previous = currentState;
  currentState = state;
  renderer?.setState(state);
  hud?.setState(state);
  if (previous && state.tick < previous.tick - 2) {
    hud?.toast("The server restarted — a fresh city was created.", "info");
  }
}

async function runCommand(type, payload = {}, successMessage = "") {
  if (!api) return;
  try {
    const data = await api.command(type, payload);
    applyState(data.state);
    if (successMessage) hud.toast(successMessage, "good");
  } catch (error) {
    hud.toast(error.message, "error");
  }
}

function selectBuilding(type) {
  selectedType = selectedType === type ? null : type;
  demolishMode = false;
  hud.setTool(selectedType, false);
  renderer.setTool(selectedType, false);
}

function toggleDemolish() {
  demolishMode = !demolishMode;
  selectedType = null;
  hud.setTool(null, demolishMode);
  renderer.setTool(null, demolishMode);
}

async function useTool(tile) {
  if (demolishMode) {
    await runCommand("demolish", { x: tile.x, z: tile.z });
    return;
  }
  if (!selectedType) {
    hud.toast("Choose a building from the build bar first.", "info");
    return;
  }
  await runCommand("build", {
    x: tile.x,
    z: tile.z,
    building: selectedType,
  });
}

async function saveGame() {
  try {
    await api.save();
    hud.toast("City saved.", "good");
  } catch (error) {
    hud.toast(error.message, "error");
  }
}

async function loadGame() {
  try {
    const data = await api.load();
    applyState(data.state);
    hud.toast("City loaded.", "good");
  } catch (error) {
    hud.toast(error.message, "error");
  }
}

function attachInput() {
  let drag = null;
  let lastX = 0;
  let lastY = 0;
  let moved = 0;

  const hoverAt = (clientX, clientY) => {
    const rect = canvas.getBoundingClientRect();
    const tile = camera.pickTile(
      clientX - rect.left,
      clientY - rect.top,
      rect.width,
      rect.height,
    );
    renderer.setHover(tile);
    hud.setHover(tile);
  };

  canvas.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 && event.button !== 2) return;
    drag = event.button === 2 ? "pan" : "orbit";
    lastX = event.clientX;
    lastY = event.clientY;
    moved = 0;
    try {
      canvas.setPointerCapture(event.pointerId);
    } catch {
      // Pointer capture is best-effort.
    }
  });

  canvas.addEventListener("pointermove", (event) => {
    if (!drag) {
      hoverAt(event.clientX, event.clientY);
      return;
    }
    const dx = event.clientX - lastX;
    const dy = event.clientY - lastY;
    moved += Math.abs(dx) + Math.abs(dy);
    lastX = event.clientX;
    lastY = event.clientY;
    if (drag === "orbit") camera.orbit(dx, dy);
    else camera.pan(dx, dy);
    hoverAt(event.clientX, event.clientY);
  });

  canvas.addEventListener("pointerup", (event) => {
    const wasOrbit = drag === "orbit";
    const shouldPlace = wasOrbit && event.button === 0 && moved < 6;
    drag = null;
    try {
      if (canvas.hasPointerCapture(event.pointerId)) {
        canvas.releasePointerCapture(event.pointerId);
      }
    } catch {
      // Ignore a missing capture.
    }
    if (!shouldPlace) return;
    const rect = canvas.getBoundingClientRect();
    const tile = camera.pickTile(
      event.clientX - rect.left,
      event.clientY - rect.top,
      rect.width,
      rect.height,
    );
    if (tile) useTool(tile);
  });

  canvas.addEventListener("pointercancel", () => {
    drag = null;
  });

  canvas.addEventListener("pointerleave", () => {
    if (drag) return;
    renderer.setHover(null);
    hud.setHover(null);
  });

  canvas.addEventListener("contextmenu", (event) => event.preventDefault());

  canvas.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      camera.zoom(event.deltaY);
    },
    { passive: false },
  );

  window.addEventListener("blur", () => {
    drag = null;
  });

  window.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    selectedType = null;
    demolishMode = false;
    hud.setTool(null, false);
    renderer.setTool(null, false);
    hud.closeWar();
  });
}

async function boot() {
  let gpu;
  try {
    gpu = await initWebGPU(canvas, (info) => {
      rendering = false;
      showUnsupported(
        `The GPU device was lost (${info.reason ?? "unknown"}). Reload the page.`,
        "The WebGPU device was lost",
      );
    });
  } catch (error) {
    console.error(error);
    showUnsupported(
      error?.message ?? String(error),
      error instanceof WebGPUUnavailable
        ? "WebGPU is not available in this browser"
        : "Could not start WebGPU",
    );
    return;
  }

  api = new CarbonApi(getSessionId());

  let initial;
  try {
    initial = await api.fetchState();
  } catch (error) {
    console.error(error);
    showStartupError(
      `${error.message} Start the server with ".venv/bin/python run.py" and reload this page.`,
    );
    return;
  }

  try {
    renderer = await SceneRenderer.create({
      canvas,
      device: gpu.device,
      context: gpu.context,
      format: gpu.format,
      catalog: initial.catalog,
    });
  } catch (error) {
    console.error(error);
    showUnsupported(
      `The 3D renderer could not start: ${error.message}`,
      "Could not start the 3D view",
    );
    return;
  }

  const width = initial.meta.grid.width;
  const height = initial.meta.grid.height;
  camera = new OrbitCamera({
    target: [width / 2, 0, height / 2],
    distance: 32,
    bounds: { width, height },
  });

  hud = new Hud({
    catalog: initial.catalog,
    categories: initial.categories,
    meta: initial.meta,
    onCommand: runCommand,
    onSelect: selectBuilding,
    onDemolish: toggleDemolish,
    onSave: saveGame,
    onLoad: loadGame,
  });
  hud.setConnection(true);
  hud.setTool(null, false);
  renderer.setTool(null, false);

  applyState(initial.state);
  loading.hidden = true;
  attachInput();

  api.stream({
    onState: applyState,
    onOpen: () => hud.setConnection(true),
    onError: () => hud.setConnection(false),
  });

  window.addEventListener("beforeunload", () => api.close());

  let previous = performance.now();
  const frame = (now) => {
    if (!rendering) return;
    const dt = Math.min(0.1, (now - previous) / 1000);
    previous = now;
    try {
      renderer.render(camera, now / 1000, dt);
    } catch (error) {
      console.error(error);
      rendering = false;
      showUnsupported(
        `Rendering stopped: ${error.message}`,
        "Could not render the city",
      );
      return;
    }
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

boot().catch((error) => {
  console.error(error);
  showStartupError(error?.message ?? String(error));
});
