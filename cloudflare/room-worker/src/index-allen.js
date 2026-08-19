import baseWorker from "./index.js";
export { RoomState } from "./index.js";

const ALLEN_KEY_SHA256 = "e53d0db863593fc618b4b764f70b31a5b9652931d8f8f7838a24cbd8cf87aa4d";
const MAX_TURN = 700;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "access-control-allow-origin": "*",
    },
  });
}

function bearer(request) {
  const value = request.headers.get("authorization") || "";
  return value.startsWith("Bearer ") ? value.slice(7) : "";
}

async function sha256Hex(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(value)));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function constantTimeHexEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function allenAuthorized(request, env) {
  const token = bearer(request);
  if (!token) return false;
  const expected = String(env.ROOM_ALLEN_KEY || "");
  if (expected && token === expected) return true;
  return constantTimeHexEqual(await sha256Hex(token), ALLEN_KEY_SHA256);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/api/allen/auth" && request.method === "GET") {
      if (!(await allenAuthorized(request, env))) return json({ error: "unauthorized" }, 401);
      return json({ ok: true, identity: "Allen" });
    }

    if (url.pathname === "/api/allen" && request.method === "POST") {
      if (!(await allenAuthorized(request, env))) return json({ error: "unauthorized" }, 401);
      try {
        const body = await request.json();
        const text = String(body?.text || "").trim();
        if (!text) return json({ error: "empty-turn" }, 400);
        if (text.length > MAX_TURN) return json({ error: "turn-too-long", max: MAX_TURN }, 400);
        const stub = env.ROOM.getByName("main");
        const result = await stub.enqueueAllen(text);
        return json(result, result.accepted ? 202 : 429);
      } catch (error) {
        return json({ error: "invalid-request", detail: String(error?.message || error) }, 400);
      }
    }

    return baseWorker.fetch(request, env, ctx);
  },
};
