import {
  add,
  clamp,
  cross,
  lookAt,
  multiply,
  normalize,
  perspective,
  scale,
  sub,
} from "./math.js";

const GROUND_Y = 0.1;

export class OrbitCamera {
  constructor(options = {}) {
    this.target = options.target ? [...options.target] : [12, 0, 12];
    this.distance = options.distance ?? 32;
    this.yaw = options.yaw ?? 0.65;
    this.pitch = options.pitch ?? 0.55;
    this.fov = options.fov ?? Math.PI / 4;
    this.bounds = options.bounds ?? { width: 24, height: 24 };
  }

  setBounds(width, height) {
    this.bounds = { width, height };
    this.target[0] = clamp(this.target[0], 0, width);
    this.target[2] = clamp(this.target[2], 0, height);
  }

  eye() {
    const cp = Math.cos(this.pitch);
    return [
      this.target[0] + Math.sin(this.yaw) * cp * this.distance,
      this.target[1] + Math.sin(this.pitch) * this.distance,
      this.target[2] + Math.cos(this.yaw) * cp * this.distance,
    ];
  }

  orbit(dx, dy) {
    this.yaw -= dx * 0.006;
    this.pitch = clamp(this.pitch + dy * 0.004, 0.18, 1.35);
  }

  zoom(deltaY) {
    this.distance = clamp(
      this.distance * Math.exp(deltaY * 0.0012),
      8,
      70,
    );
  }

  pan(dx, dy) {
    const eye = this.eye();
    const flatForward = normalize([
      this.target[0] - eye[0],
      0,
      this.target[2] - eye[2],
    ]);
    const right = normalize(cross(flatForward, [0, 1, 0]));
    const factor = this.distance * 0.0018;
    this.target[0] -= right[0] * dx * factor;
    this.target[2] -= right[2] * dx * factor;
    this.target[0] += flatForward[0] * dy * factor;
    this.target[2] += flatForward[2] * dy * factor;
    this.target[0] = clamp(this.target[0], 0, this.bounds.width);
    this.target[2] = clamp(this.target[2], 0, this.bounds.height);
  }

  viewProjection(aspect) {
    const view = lookAt(this.eye(), this.target, [0, 1, 0]);
    const projection = perspective(this.fov, aspect, 0.1, 250);
    return { matrix: multiply(projection, view), eye: this.eye() };
  }

  /** Ray-cast the mouse into the ground plane and return a map tile. */
  pickTile(px, py, viewWidth, viewHeight) {
    if (viewWidth <= 0 || viewHeight <= 0) return null;
    const eye = this.eye();
    const forward = normalize(sub(this.target, eye));
    const right = normalize(cross(forward, [0, 1, 0]));
    const up = cross(right, forward);

    const aspect = viewWidth / viewHeight;
    const ndcX = (px / viewWidth) * 2 - 1;
    const ndcY = 1 - (py / viewHeight) * 2;
    const tan = Math.tan(this.fov / 2);
    const direction = normalize(
      add(
        forward,
        add(scale(right, ndcX * tan * aspect), scale(up, ndcY * tan)),
      ),
    );

    if (direction[1] >= -0.0001) return null;
    const t = (GROUND_Y - eye[1]) / direction[1];
    if (t <= 0) return null;

    const worldX = eye[0] + direction[0] * t;
    const worldZ = eye[2] + direction[2] * t;
    const x = Math.floor(worldX);
    const z = Math.floor(worldZ);
    if (
      x < 0 ||
      z < 0 ||
      x >= this.bounds.width ||
      z >= this.bounds.height
    ) {
      return null;
    }
    return { x, z, worldX, worldZ };
  }
}
