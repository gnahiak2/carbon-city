struct Uniforms {
  view_proj: mat4x4<f32>,
  camera_pos: vec4<f32>,
  sun_dir: vec4<f32>,
};

@group(0) @binding(0) var<uniform> uniforms: Uniforms;

struct VertexOut {
  @builtin(position) clip_position: vec4<f32>,
  @location(0) normal: vec3<f32>,
  @location(1) color: vec4<f32>,
  @location(2) glow: f32,
  @location(3) world_pos: vec3<f32>,
};

@vertex
fn vs_main(
  @location(0) position: vec3<f32>,
  @location(1) normal: vec3<f32>,
  @location(3) offset: vec3<f32>,
  @location(4) scale: vec3<f32>,
  @location(5) color: vec4<f32>,
  @location(6) glow: f32,
) -> VertexOut {
  var out: VertexOut;
  let world = offset + position * scale;
  out.clip_position = uniforms.view_proj * vec4<f32>(world, 1.0);
  out.normal = normal;
  out.color = color;
  out.glow = glow;
  out.world_pos = world;
  return out;
}

@fragment
fn fs_main(in: VertexOut) -> @location(0) vec4<f32> {
  let n = normalize(in.normal);
  let sun = normalize(uniforms.sun_dir.xyz);
  let ndl = max(dot(n, sun), 0.0);

  let sky_ambient = vec3<f32>(0.22, 0.27, 0.35);
  let ground_ambient = vec3<f32>(0.09, 0.085, 0.08);
  let ambient = mix(ground_ambient, sky_ambient, n.y * 0.5 + 0.5);
  let sun_color = vec3<f32>(1.0, 0.9, 0.72);

  var rgb = in.color.rgb * (ambient + sun_color * ndl * 0.9);

  // A soft cool rim keeps box edges readable against the sky.
  let view_dir = normalize(uniforms.camera_pos.xyz - in.world_pos);
  let rim = pow(1.0 - max(dot(n, view_dir), 0.0), 3.0) * 0.1;
  rgb += vec3<f32>(0.46, 0.68, 0.84) * rim;

  let dist = length(in.world_pos.xz - uniforms.camera_pos.xz);
  let fog = clamp((dist - 24.0) / 46.0, 0.0, 0.7);
  rgb = mix(rgb, vec3<f32>(0.06, 0.12, 0.16), fog);

  rgb += in.color.rgb * in.glow * 0.9;

  return vec4<f32>(rgb, in.color.a);
}

struct SkyOut {
  @builtin(position) clip_position: vec4<f32>,
  @location(0) uv: vec2<f32>,
};

@vertex
fn vs_sky(@builtin(vertex_index) vertex_index: u32) -> SkyOut {
  var positions = array<vec2<f32>, 3>(
    vec2<f32>(-1.0, -1.0),
    vec2<f32>(3.0, -1.0),
    vec2<f32>(-1.0, 3.0),
  );
  let p = positions[vertex_index];
  var out: SkyOut;
  out.clip_position = vec4<f32>(p, 0.999, 1.0);
  out.uv = p * 0.5 + vec2<f32>(0.5, 0.5);
  return out;
}

@fragment
fn fs_sky(in: SkyOut) -> @location(0) vec4<f32> {
  let horizon = vec3<f32>(0.08, 0.18, 0.24);
  let zenith = vec3<f32>(0.008, 0.02, 0.04);
  let t = clamp(in.uv.y, 0.0, 1.0);
  var color = mix(horizon, zenith, smoothstep(0.0, 0.95, t));

  let sun_uv = vec2<f32>(0.62, 0.82);
  let d = distance(in.uv, sun_uv);
  let glow = pow(clamp(1.0 - d * 1.7, 0.0, 1.0), 3.0);
  color += vec3<f32>(1.0, 0.62, 0.3) * glow * 0.26;
  let disc = pow(clamp(1.0 - d * 16.0, 0.0, 1.0), 3.0) * 0.35;
  color += vec3<f32>(1.0, 0.84, 0.58) * disc;

  return vec4<f32>(color, 1.0);
}
