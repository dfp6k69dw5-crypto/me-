import base, { RoomState } from "./index.js";

export { RoomState };

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

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Allen is intentionally an open participant. The Room page itself is the
    // input surface, so no browser key or bearer token is required to speak.
    if (url.pathname === "/api/allen/auth" && request.method === "GET") {
      return json({ ok: true, identity: "Allen", public: true });
    }

    if (url.pathname === "/api/allen" && request.method === "POST") {
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

    // Retire the old keyed Allen page entirely.
    if (url.pathname === "/allen" && (request.method === "GET" || request.method === "HEAD")) {
      return Response.redirect(new URL("/", request.url), 302);
    }

    return base.fetch(request, env, ctx);
  },
};
