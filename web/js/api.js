const SESSION_KEY = "carbon-city-session";

function randomId() {
  if (globalThis.crypto?.randomUUID) {
    return crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function getSessionId() {
  try {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing && /^[A-Za-z0-9_-]{6,64}$/.test(existing)) {
      return existing;
    }
    const id = randomId();
    localStorage.setItem(SESSION_KEY, id);
    return id;
  } catch {
    // Private browsing can block localStorage. The in-memory id still works
    // for this tab.
    return randomId();
  }
}

export class CarbonApi {
  constructor(sessionId = getSessionId()) {
    this.sessionId = sessionId;
    this.source = null;
  }

  async _post(path, payload) {
    let response;
    try {
      response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session: this.sessionId, ...payload }),
      });
    } catch {
      throw new Error("Could not reach the game server.");
    }

    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`The server returned an invalid response (${response.status}).`);
    }
    if (!response.ok || !data.ok) {
      throw new Error(data.error || `Request failed (${response.status}).`);
    }
    return data;
  }

  async fetchState() {
    let response;
    try {
      response = await fetch(
        `/api/state?session=${encodeURIComponent(this.sessionId)}`,
      );
    } catch {
      throw new Error("Could not reach the game server.");
    }
    const data = await response.json().catch(() => null);
    if (!response.ok || !data?.ok) {
      throw new Error(data?.error || `Could not load the city (${response.status}).`);
    }
    return data;
  }

  async command(type, payload = {}) {
    return this._post("/api/command", { type, ...payload });
  }

  async save() {
    return this._post("/api/save", {});
  }

  async load() {
    return this._post("/api/load", {});
  }

  stream({ onState, onOpen, onError }) {
    this.source = new EventSource(
      `/api/stream?session=${encodeURIComponent(this.sessionId)}`,
    );
    this.source.addEventListener("state", (event) => {
      try {
        onState(JSON.parse(event.data));
      } catch (error) {
        console.error("Bad state event", error);
      }
    });
    this.source.addEventListener("open", () => onOpen?.());
    this.source.addEventListener("error", () => onError?.());
  }

  close() {
    this.source?.close();
    this.source = null;
  }
}
