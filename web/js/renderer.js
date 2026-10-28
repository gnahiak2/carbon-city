import {
  clamp,
  lerp,
  mixColor,
  multiply,
  perspective,
  lookAt,
} from "./math.js";

const INSTANCE_FLOATS = 11;
const INITIAL_INSTANCE_FLOATS = 16384;

const TERRAIN_COLORS = {
  g: [0.29, 0.48, 0.3],
  w: [0.14, 0.34, 0.52],
  r: [0.36, 0.35, 0.33],
  f: [0.18, 0.37, 0.21],
};

const TREE_COLORS = [
  [0.2, 0.52, 0.28],
  [0.24, 0.58, 0.3],
  [0.16, 0.45, 0.23],
];

const MISSILE_COLORS = {
  missile: [1.0, 0.82, 0.32],
  nuke: [1.0, 0.38, 0.22],
  enemy: [1.0, 0.25, 0.2],
};

function makeCube() {
  const faces = [
    {
      n: [1, 0, 0],
      c: [[0.5, -0.5, -0.5], [0.5, 0.5, -0.5], [0.5, 0.5, 0.5], [0.5, -0.5, 0.5]],
    },
    {
      n: [-1, 0, 0],
      c: [[-0.5, -0.5, 0.5], [-0.5, 0.5, 0.5], [-0.5, 0.5, -0.5], [-0.5, -0.5, -0.5]],
    },
    {
      n: [0, 1, 0],
      c: [[-0.5, 0.5, 0.5], [0.5, 0.5, 0.5], [0.5, 0.5, -0.5], [-0.5, 0.5, -0.5]],
    },
    {
      n: [0, -1, 0],
      c: [[-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, -0.5, 0.5], [-0.5, -0.5, 0.5]],
    },
    {
      n: [0, 0, 1],
      c: [[-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5]],
    },
    {
      n: [0, 0, -1],
      c: [[0.5, -0.5, -0.5], [-0.5, -0.5, -0.5], [-0.5, 0.5, -0.5], [0.5, 0.5, -0.5]],
    },
  ];

  const vertices = [];
  const indices = [];
  faces.forEach((face, faceIndex) => {
    for (const corner of face.c) {
      vertices.push(corner[0], corner[1], corner[2], ...face.n);
    }
    const base = faceIndex * 4;
    indices.push(base, base + 1, base + 2, base, base + 2, base + 3);
  });

  return {
    vertices: new Float32Array(vertices),
    indices: new Uint16Array(indices),
  };
}

export class SceneRenderer {
  static async create({ canvas, device, context, format, catalog }) {
    const shaderUrl = new URL("./shaders/scene.wgsl", import.meta.url);
    const response = await fetch(shaderUrl);
    if (!response.ok) {
      throw new Error(`Could not load shaders (${response.status}).`);
    }
    const code = await response.text();
    const module = device.createShaderModule({ code, label: "scene" });
    const info = await module.getCompilationInfo?.();
    const errors = info?.messages?.filter((message) => message.type === "error") ?? [];
    if (errors.length) {
      throw new Error(
        errors
          .map((message) => `${message.lineNum}:${message.linePos} ${message.message}`)
          .join("; "),
      );
    }
    return new SceneRenderer({
      canvas,
      device,
      context,
      format,
      catalog,
      module,
    });
  }

  constructor({ canvas, device, context, format, catalog, module }) {
    this.canvas = canvas;
    this.device = device;
    this.context = context;
    this.format = format;
    this.catalog = catalog;

    this.state = null;
    this.hover = null;
    this.selectedType = null;
    this.demolishMode = false;
    this.missileProgress = new Map();

    this.uniformData = new Float32Array(24);
    this.uniformBuffer = device.createBuffer({
      size: this.uniformData.byteLength,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });

    const cube = makeCube();
    this.vertexBuffer = device.createBuffer({
      size: cube.vertices.byteLength,
      usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
    });
    device.queue.writeBuffer(this.vertexBuffer, 0, cube.vertices);

    this.indexBuffer = device.createBuffer({
      size: cube.indices.byteLength,
      usage: GPUBufferUsage.INDEX | GPUBufferUsage.COPY_DST,
    });
    device.queue.writeBuffer(this.indexBuffer, 0, cube.indices);
    this.indexCount = cube.indices.length;

    this.instanceBuffer = null;
    this.instanceCapacity = 0;
    this._ensureInstanceBuffer(INITIAL_INSTANCE_FLOATS);

    this.pipeline = device.createRenderPipeline({
      label: "box-pipeline",
      layout: "auto",
      vertex: {
        module,
        entryPoint: "vs_main",
        buffers: [
          {
            arrayStride: 24,
            attributes: [
              { shaderLocation: 0, offset: 0, format: "float32x3" },
              { shaderLocation: 1, offset: 12, format: "float32x3" },
            ],
          },
          {
            arrayStride: INSTANCE_FLOATS * 4,
            stepMode: "instance",
            attributes: [
              { shaderLocation: 3, offset: 0, format: "float32x3" },
              { shaderLocation: 4, offset: 12, format: "float32x3" },
              { shaderLocation: 5, offset: 24, format: "float32x4" },
              { shaderLocation: 6, offset: 40, format: "float32" },
            ],
          },
        ],
      },
      fragment: {
        module,
        entryPoint: "fs_main",
        targets: [
          {
            format,
            blend: {
              color: {
                srcFactor: "src-alpha",
                dstFactor: "one-minus-src-alpha",
                operation: "add",
              },
              alpha: {
                srcFactor: "one",
                dstFactor: "one-minus-src-alpha",
                operation: "add",
              },
            },
          },
        ],
      },
      primitive: {
        topology: "triangle-list",
        cullMode: "back",
        frontFace: "ccw",
      },
      depthStencil: {
        format: "depth24plus",
        depthWriteEnabled: true,
        depthCompare: "less",
      },
    });

    this.bindGroup = device.createBindGroup({
      layout: this.pipeline.getBindGroupLayout(0),
      entries: [{ binding: 0, resource: { buffer: this.uniformBuffer } }],
    });

    // Full-screen sky gradient, drawn before the city with no depth writes.
    this.skyPipeline = device.createRenderPipeline({
      label: "sky-pipeline",
      layout: "auto",
      vertex: { module, entryPoint: "vs_sky" },
      fragment: {
        module,
        entryPoint: "fs_sky",
        targets: [{ format }],
      },
      primitive: { topology: "triangle-list" },
      depthStencil: {
        format: "depth24plus",
        depthWriteEnabled: false,
        depthCompare: "always",
      },
    });

    this.depthTexture = null;
    this._createDepthTexture();
  }

  _ensureInstanceBuffer(floats) {
    if (this.instanceBuffer && this.instanceCapacity >= floats) return;
    const capacity = Math.max(
      INITIAL_INSTANCE_FLOATS,
      Math.ceil(floats / 4096) * 4096,
    );
    this.instanceBuffer?.destroy();
    this.instanceBuffer = this.device.createBuffer({
      size: capacity * 4,
      usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
      label: "instances",
    });
    this.instanceCapacity = capacity;
  }

  _createDepthTexture() {
    const width = Math.max(1, this.canvas.width);
    const height = Math.max(1, this.canvas.height);
    this.depthTexture?.destroy();
    this.depthTexture = this.device.createTexture({
      size: [width, height],
      format: "depth24plus",
      usage: GPUTextureUsage.RENDER_ATTACHMENT,
      label: "depth",
    });
  }

  resize() {
    const dpr = Math.min(globalThis.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(this.canvas.clientWidth * dpr));
    const height = Math.max(1, Math.floor(this.canvas.clientHeight * dpr));
    if (this.canvas.width === width && this.canvas.height === height) return;
    this.canvas.width = width;
    this.canvas.height = height;
    this.context.configure({
      device: this.device,
      format: this.format,
      alphaMode: "opaque",
    });
    this._createDepthTexture();
  }

  setState(state) {
    this.state = state;
    const seen = new Set();
    for (const missile of state.missiles ?? []) {
      seen.add(missile.id);
      const entry = this.missileProgress.get(missile.id);
      if (!entry) {
        this.missileProgress.set(missile.id, {
          display: missile.progress,
          target: missile.progress,
        });
      } else {
        if (missile.progress < entry.target - 0.05) {
          entry.display = missile.progress;
        }
        entry.target = missile.progress;
      }
    }
    for (const id of this.missileProgress.keys()) {
      if (!seen.has(id)) this.missileProgress.delete(id);
    }
  }

  setHover(tile) {
    this.hover = tile;
  }

  setTool(type, demolish) {
    this.selectedType = type;
    this.demolishMode = demolish;
  }

  _updateMissiles(dt) {
    for (const entry of this.missileProgress.values()) {
      entry.display += (entry.target - entry.display) * Math.min(1, dt * 8);
      if (Math.abs(entry.target - entry.display) < 0.002) {
        entry.display = entry.target;
      }
    }
  }

  _buildInstances(time) {
    const state = this.state;
    const items = [];
    const push = (pos, size, color, alpha = 1, glow = 0) => {
      items.push(
        pos[0],
        pos[1],
        pos[2],
        size[0],
        size[1],
        size[2],
        color[0],
        color[1],
        color[2],
        alpha,
        glow,
      );
    };

    const rows = state.grid.terrain;
    const unlockedRows = state.grid.unlocked;
    const height = rows.length;
    const width = rows[0]?.length ?? 0;
    const buildings = new Map(
      state.buildings.map((building) => [
        `${building.x},${building.z}`,
        building,
      ]),
    );

    const hash = (x, z) => {
      const n = Math.sin(x * 127.1 + z * 311.7) * 43758.5453;
      return n - Math.floor(n);
    };
    const shade = (color, factor) => [
      color[0] * factor,
      color[1] * factor,
      color[2] * factor,
    ];

    const cx = width / 2;
    const cz = height / 2;

    // A dark sea and stacked plinth turn the grid into a small diorama
    // instead of a board floating in empty space.
    push([cx, -1.0, cz], [56, 0.3, 56], [0.03, 0.075, 0.11]);
    push([cx, -0.62, cz], [28.6, 0.42, 28.6], [0.04, 0.075, 0.08]);
    push([cx, -0.27, cz], [26.2, 0.34, 26.2], [0.075, 0.125, 0.095]);
    push([cx, -0.04, cz], [25.9, 0.1, 25.9], [0.08, 0.2, 0.22], 1, 0.03);

    const treeAt = (wx, wz, treeScale, dimmed = false) => {
      const h = hash(wx * 3.1, wz * 5.7);
      const canopy = TREE_COLORS[Math.floor(h * TREE_COLORS.length) % TREE_COLORS.length];
      const tint = dimmed ? 0.5 : 1;
      const trunkH = (0.32 + h * 0.12) * treeScale;
      push(
        [wx, 0.108, wz],
        [0.66 * treeScale, 0.012, 0.66 * treeScale],
        [0.01, 0.02, 0.015],
        dimmed ? 0.12 : 0.2,
      );
      push(
        [wx, 0.1 + trunkH / 2, wz],
        [0.1 * treeScale, trunkH, 0.1 * treeScale],
        dimmed ? [0.16, 0.13, 0.1] : [0.3, 0.21, 0.14],
      );
      push(
        [wx, 0.1 + 0.4 * treeScale, wz],
        [0.58 * treeScale, 0.5 * treeScale, 0.58 * treeScale],
        shade(canopy, tint),
      );
      push(
        [wx, 0.1 + 0.72 * treeScale, wz],
        [0.36 * treeScale, 0.38 * treeScale, 0.36 * treeScale],
        shade(canopy, tint * 1.12),
      );
    };

    for (let z = 0; z < height; z += 1) {
      const row = rows[z];
      const unlockedRow = unlockedRows[z] ?? "";
      for (let x = 0; x < width; x += 1) {
        const tile = row[x];
        const unlocked = unlockedRow[x] === "1";
        const baseColor = TERRAIN_COLORS[tile] ?? TERRAIN_COLORS.g;
        const variation = hash(x, z);
        const patch =
          0.97 +
          Math.sin(x * 0.41 + z * 0.23) * 0.03 +
          Math.cos(x * 0.19 - z * 0.37) * 0.03;
        let color = unlocked
          ? shade(baseColor, (0.93 + variation * 0.14) * patch)
          : mixColor(shade(baseColor, 0.6), [0.055, 0.09, 0.12], 0.48);
        let glow = 0;
        if (tile === "w") {
          const wave = Math.sin(time * 1.2 + x * 0.7 + z * 0.5);
          color = unlocked
            ? shade(baseColor, (0.94 + wave * 0.07) * patch)
            : mixColor(shade(baseColor, 0.5), [0.04, 0.07, 0.1], 0.5);
          glow = Math.max(0, wave) * 0.045;
        }
        let tileHeight = 0.1;
        if (tile === "w") tileHeight = 0.06;
        if (tile === "r") tileHeight = 0.26;
        push(
          [x + 0.5, tileHeight / 2, z + 0.5],
          [0.97, tileHeight, 0.97],
          color,
          1,
          glow,
        );

        if (tile === "g" && unlocked && hash(x + 9, z + 3) > 0.82) {
          const gx = x + 0.2 + hash(x + 4, z + 1) * 0.6;
          const gz = z + 0.2 + hash(x + 6, z + 2) * 0.6;
          push(
            [gx, 0.14, gz],
            [0.06, 0.08, 0.06],
            [0.31, 0.52, 0.3],
          );
        }

        if (tile === "r") {
          const rockTint = unlocked ? 1 : 0.5;
          push(
            [x + 0.38, 0.3, z + 0.42],
            [0.32, 0.16 + variation * 0.1, 0.28],
            shade(baseColor, 0.85 * rockTint),
          );
          push(
            [x + 0.66, 0.35, z + 0.63],
            [0.2, 0.28, 0.2],
            shade(baseColor, 1.08 * rockTint),
          );
        }

        if (tile === "f" && !buildings.has(`${x},${z}`)) {
          treeAt(
            x + 0.5,
            z + 0.5,
            0.82 + hash(x + 2, z + 4) * 0.35,
            !unlocked,
          );
        }
      }
    }

    for (const building of state.buildings) {
      const stats = this.catalog[building.type];
      if (!stats) continue;
      const seed = hash(building.x + 7, building.z + 13);
      const color = shade(
        stats.color ?? [0.8, 0.8, 0.8],
        0.94 + seed * 0.12,
      );
      const boxHeight = stats.height ?? 1;
      const footprint =
        building.type === "road" ? 0.96 : building.type === "park" ? 0.82 : 0.72;
      const px = building.x + 0.5;
      const pz = building.z + 0.5;

      if (building.type === "road") {
        push([px, 0.1 + boxHeight / 2, pz], [footprint, boxHeight, footprint], color);
        const vertical =
          buildings.get(`${building.x},${building.z - 1}`)?.type === "road" ||
          buildings.get(`${building.x},${building.z + 1}`)?.type === "road";
        const horizontal =
          buildings.get(`${building.x - 1},${building.z}`)?.type === "road" ||
          buildings.get(`${building.x + 1},${building.z}`)?.type === "road";
        if (vertical && !horizontal) {
          push([px, 0.166, pz], [0.06, 0.012, 0.56], [0.9, 0.86, 0.65], 1, 0.12);
        } else if (!vertical && horizontal) {
          push([px, 0.166, pz], [0.56, 0.012, 0.06], [0.9, 0.86, 0.65], 1, 0.12);
        } else {
          push([px, 0.166, pz], [0.12, 0.012, 0.12], [0.9, 0.86, 0.65], 1, 0.12);
        }
        continue;
      }

      push(
        [px, 0.109, pz],
        [footprint + 0.22, 0.012, footprint + 0.22],
        [0.008, 0.014, 0.012],
        0.3,
      );
      push(
        [px, 0.13, pz],
        [footprint + 0.08, 0.06, footprint + 0.08],
        shade(color, 0.6),
      );
      push(
        [px, 0.1 + boxHeight / 2, pz],
        [footprint, boxHeight, footprint],
        color,
      );

      if (boxHeight >= 1.5 && building.type !== "wind_turbine") {
        push(
          [px, 0.1 + boxHeight + 0.07, pz],
          [footprint * 0.46, 0.14, footprint * 0.46],
          mixColor(color, [1, 1, 1], 0.28),
        );
      }

      if (boxHeight >= 1.8 && building.type !== "wind_turbine") {
        push(
          [px, 0.1 + boxHeight + 0.28, pz],
          [0.03, 0.4, 0.03],
          [0.75, 0.8, 0.85],
        );
        push(
          [px, 0.1 + boxHeight + 0.5, pz],
          [0.08, 0.08, 0.08],
          [1, 0.35, 0.3],
          1,
          0.8,
        );
      }

      if (building.type === "house") {
        push(
          [px, 0.1 + boxHeight + 0.04, pz],
          [footprint * 0.9, 0.08, footprint * 0.9],
          shade(color, 0.72),
        );
        push(
          [px + 0.18, 0.1 + boxHeight + 0.15, pz - 0.12],
          [0.07, 0.16, 0.07],
          [0.35, 0.27, 0.22],
        );
      }

      if (building.type === "shop") {
        push(
          [px, 0.1 + boxHeight + 0.08, pz],
          [footprint * 0.78, 0.05, 0.1],
          [1, 0.85, 0.45],
          1,
          0.3,
        );
      }

      if (building.type === "park") {
        treeAt(px - 0.18, pz + 0.15, 0.56);
        treeAt(px + 0.2, pz - 0.13, 0.47);
      }

      if (building.type === "solar_plant") {
        push(
          [px - 0.16, 0.1 + boxHeight + 0.05, pz - 0.12],
          [0.5, 0.05, 0.32],
          [0.1, 0.18, 0.32],
          1,
          0.05,
        );
        push(
          [px + 0.18, 0.1 + boxHeight + 0.05, pz + 0.15],
          [0.42, 0.05, 0.28],
          [0.12, 0.22, 0.4],
          1,
          0.05,
        );
      }

      if (building.type === "wind_turbine") {
        const top = 0.1 + boxHeight;
        push([px, top + 0.06, pz], [1.25, 0.06, 0.08], [0.9, 0.96, 1], 1, 0.12);
        push([px, top + 0.06, pz], [0.08, 0.06, 1.25], [0.9, 0.96, 1], 1, 0.12);
        push([px, top + 0.06, pz], [0.16, 0.16, 0.16], [0.75, 0.8, 0.85]);
      }

      if (building.type === "coal_plant" || building.type === "gas_plant") {
        const chimneyH = building.type === "coal_plant" ? 0.9 : 0.65;
        push(
          [px + 0.16, 0.1 + boxHeight + chimneyH / 2, pz - 0.13],
          [0.17, chimneyH, 0.17],
          [0.22, 0.22, 0.24],
        );
        for (let i = 0; i < 2; i += 1) {
          const t = (time * 0.3 + i * 0.5 + seed) % 1;
          const s = 0.22 + t * 0.5;
          push(
            [
              px + 0.16 + Math.sin(t * 6 + i) * 0.06,
              0.1 + boxHeight + chimneyH + t * 0.8,
              pz - 0.13,
            ],
            [s, 0.22, s],
            [0.34, 0.36, 0.38],
            0.2 * (1 - t),
          );
        }
      }

      if (building.type === "factory") {
        const chimneyH = 0.6;
        push(
          [px - 0.2, 0.1 + boxHeight + chimneyH / 2, pz + 0.14],
          [0.14, chimneyH, 0.14],
          [0.25, 0.23, 0.22],
        );
        const t = (time * 0.32 + seed) % 1;
        push(
          [px - 0.2, 0.1 + boxHeight + chimneyH + t * 0.6, pz + 0.14],
          [0.2 + t * 0.4, 0.18, 0.2 + t * 0.4],
          [0.36, 0.37, 0.38],
          0.18 * (1 - t),
        );
      }

      if (building.type === "nuclear_plant") {
        push(
          [px, 0.1 + boxHeight + 0.1, pz],
          [0.3, 0.2, 0.3],
          [0.3, 0.55, 0.42],
          1,
          0.1,
        );
        push(
          [px, 0.1 + boxHeight + 0.28, pz],
          [0.08, 0.08, 0.08],
          [0.7, 1, 0.85],
          1,
          0.7,
        );
      }

      if (building.type === "missile_silo") {
        push(
          [px, 0.1 + boxHeight + 0.03, pz],
          [0.52, 0.06, 0.52],
          [0.18, 0.18, 0.2],
        );
        push(
          [px, 0.1 + boxHeight + 0.16, pz],
          [0.07, 0.07, 0.07],
          [1, 0.3, 0.25],
          1,
          0.9,
        );
      }
    }

    for (const fallout of state.fallout ?? []) {
      const pulse =
        0.55 + 0.35 * Math.sin(time * 5 + fallout.x * 1.7 + fallout.z * 0.9);
      const tile = rows[fallout.z]?.[fallout.x];
      const ground = tile === "w" ? 0.06 : tile === "r" ? 0.26 : 0.1;
      push(
        [fallout.x + 0.5, ground + 0.005, fallout.z + 0.5],
        [0.9, 0.01, 0.9],
        [0.015, 0.03, 0.015],
        0.4,
      );
      push(
        [fallout.x + 0.5, ground + 0.04, fallout.z + 0.5],
        [0.64, 0.08, 0.64],
        [0.35, 0.95, 0.32],
        0.92,
        pulse,
      );
      for (const [dx, dz] of [[0.22, 0.18], [-0.2, -0.24]]) {
        push(
          [fallout.x + 0.5 + dx, ground + 0.05, fallout.z + 0.5 + dz],
          [0.2, 0.1, 0.2],
          [0.4, 1, 0.35],
          0.85,
          pulse * 0.8,
        );
      }
    }

    (state.civs ?? []).forEach((civ) => {
      const target = civ.target ?? { x: 2, z: height / 2 };
      const health = civ.max_health
        ? clamp(civ.health / civ.max_health, 0, 1)
        : 1;
      const scale = civ.defeated ? 0.28 : 0.55 + health * 0.32;
      const brightness = civ.defeated ? 0.32 : 1;
      push(
        [target.x, 0.108, target.z],
        [3.0, 0.012, 2.6],
        [0.01, 0.02, 0.02],
        civ.defeated ? 0.18 : 0.28,
      );
      const layout = [
        [0, 0, 1.35, 1.6, 1.0],
        [1.2, 0.2, 0.95, 1.0, 0.92],
        [-1.15, 0.35, 1.0, 1.2, 0.95],
        [0.2, 1.2, 0.85, 0.8, 0.9],
        [-0.55, -1.0, 0.9, 0.65, 0.88],
        [1.4, 1.05, 0.65, 0.5, 0.84],
      ];
      for (const [dx, dz, w, h, tone] of layout) {
        push(
          [target.x + dx, 0.1 + (h * scale) / 2, target.z + dz],
          [w, h * scale, w],
          shade(civ.color, brightness * tone),
          1,
          civ.defeated ? 0 : 0.12,
        );
      }
      if (!civ.defeated) {
        push(
          [target.x, 0.1 + 1.6 * scale + 0.1, target.z],
          [0.07, 0.07, 0.07],
          [1, 0.98, 0.8],
          1,
          1.0,
        );
      }
    });

    for (const missile of state.missiles ?? []) {
      const entry = this.missileProgress.get(missile.id);
      const t = clamp(entry?.display ?? missile.progress, 0, 1);
      const color = MISSILE_COLORS[missile.kind] ?? MISSILE_COLORS.missile;
      const size =
        missile.kind === "nuke"
          ? [0.36, 0.88, 0.36]
          : missile.kind === "enemy"
            ? [0.24, 0.68, 0.24]
            : [0.22, 0.76, 0.22];

      for (let trail = 2; trail >= 1; trail -= 1) {
        const tt = Math.max(0, t - trail * 0.03);
        push(
          [
            lerp(missile.x, missile.tx, tt),
            0.1 + 1.4 + Math.sin(Math.PI * tt) * 5.5,
            lerp(missile.z, missile.tz, tt),
          ],
          [size[0] * 0.6, size[1] * 0.7, size[2] * 0.6],
          color,
          0.4,
          0.55,
        );
      }

      push(
        [
          lerp(missile.x, missile.tx, t),
          0.1 + 1.4 + Math.sin(Math.PI * t) * 5.5,
          lerp(missile.z, missile.tz, t),
        ],
        size,
        color,
        1,
        1.25,
      );
    }

    if (this.hover) {
      const { x, z } = this.hover;
      const pulse = 0.72 + 0.28 * Math.sin(time * 7);
      const markerColor = this.demolishMode ? [1, 0.32, 0.32] : [1, 0.9, 0.4];
      push(
        [x + 0.5, 0.13, z + 0.5],
        [1.02, 0.03, 1.02],
        markerColor,
        0.9,
        pulse,
      );
      for (const [dx, dz] of [
        [-0.44, -0.44],
        [0.44, -0.44],
        [-0.44, 0.44],
        [0.44, 0.44],
      ]) {
        push(
          [x + 0.5 + dx, 0.22, z + 0.5 + dz],
          [0.07, 0.24, 0.07],
          markerColor,
          0.95,
          pulse,
        );
      }

      if (this.selectedType && !this.demolishMode) {
        const stats = this.catalog[this.selectedType];
        const tile = rows[z]?.[x];
        const unlocked = unlockedRows[z]?.[x] === "1";
        const occupied = buildings.has(`${x},${z}`);
        if (
          stats &&
          unlocked &&
          !occupied &&
          (tile === "g" || tile === "f")
        ) {
          const boxHeight = stats.height ?? 1;
          push(
            [x + 0.5, 0.1 + boxHeight / 2, z + 0.5],
            [0.72, boxHeight, 0.72],
            stats.color ?? [1, 1, 1],
            0.38,
            0.18,
          );
        }
      }
    }

    return new Float32Array(items);
  }

  render(camera, time, dt) {
    this.resize();
    if (!this.state) return;
    if (this.canvas.width <= 1 || this.canvas.height <= 1) return;

    this._updateMissiles(dt);

    const aspect = this.canvas.width / this.canvas.height;
    const { matrix, eye } = camera.viewProjection(aspect);
    this.uniformData.set(matrix, 0);
    this.uniformData[16] = eye[0];
    this.uniformData[17] = eye[1];
    this.uniformData[18] = eye[2];
    this.uniformData[19] = 1;
    this.uniformData[20] = 0.45;
    this.uniformData[21] = 0.85;
    this.uniformData[22] = 0.3;
    this.uniformData[23] = 0;
    this.device.queue.writeBuffer(this.uniformBuffer, 0, this.uniformData);

    const instances = this._buildInstances(time);
    this._ensureInstanceBuffer(instances.length);
    this.device.queue.writeBuffer(this.instanceBuffer, 0, instances);
    const instanceCount = instances.length / INSTANCE_FLOATS;

    const encoder = this.device.createCommandEncoder();
    const pass = encoder.beginRenderPass({
      colorAttachments: [
        {
          view: this.context.getCurrentTexture().createView(),
          clearValue: { r: 0.027, g: 0.055, b: 0.085, a: 1 },
          loadOp: "clear",
          storeOp: "store",
        },
      ],
      depthStencilAttachment: {
        view: this.depthTexture.createView(),
        depthClearValue: 1,
        depthLoadOp: "clear",
        depthStoreOp: "store",
      },
    });

    pass.setPipeline(this.skyPipeline);
    pass.draw(3);

    if (instanceCount > 0) {
      pass.setPipeline(this.pipeline);
      pass.setBindGroup(0, this.bindGroup);
      pass.setVertexBuffer(0, this.vertexBuffer);
      pass.setVertexBuffer(1, this.instanceBuffer);
      pass.setIndexBuffer(this.indexBuffer, "uint16");
      pass.drawIndexed(this.indexCount, instanceCount);
    }
    pass.end();
    this.device.queue.submit([encoder.finish()]);
  }
}
