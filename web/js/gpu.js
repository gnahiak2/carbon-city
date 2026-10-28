export class WebGPUUnavailable extends Error {}

export async function initWebGPU(canvas, onDeviceLost) {
  if (!navigator.gpu) {
    throw new WebGPUUnavailable(
      "navigator.gpu is missing. This browser does not expose WebGPU.",
    );
  }

  let adapter = null;
  try {
    adapter = await navigator.gpu.requestAdapter({
      powerPreference: "high-performance",
    });
  } catch (error) {
    throw new WebGPUUnavailable(
      `Could not request a GPU adapter: ${error?.message ?? error}`,
    );
  }

  if (!adapter) {
    throw new WebGPUUnavailable(
      "No compatible GPU adapter was found. Hardware acceleration may be off.",
    );
  }

  let device;
  try {
    device = await adapter.requestDevice();
  } catch (error) {
    throw new WebGPUUnavailable(
      `Could not create a GPU device: ${error?.message ?? error}`,
    );
  }

  const context = canvas.getContext("webgpu");
  if (!context) {
    throw new WebGPUUnavailable("The canvas could not create a WebGPU context.");
  }

  const format = navigator.gpu.getPreferredCanvasFormat();
  context.configure({ device, format, alphaMode: "opaque" });

  if (onDeviceLost) {
    device.lost.then((info) => onDeviceLost(info));
  }

  return { device, context, format };
}
