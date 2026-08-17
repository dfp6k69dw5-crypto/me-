import { DurableObject } from "cloudflare:workers";

const ISSUER = "https://token.actions.githubusercontent.com";
const EXPECTED_AUDIENCE = "room-live-mirror";
const EXPECTED_REPOSITORY = "maaronfanberg-lab/me-";
const EXPECTED_REF = "refs/heads/main";

let oidcMetadataCache = null;
let jwksCache = null;

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "access-control-allow-origin": "*",
      ...extraHeaders,
    },
  });
}

function decodeBase64Url(value) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
  return out;
}

function decodeJwtJson(value) {
  return JSON.parse(new TextDecoder().decode(decodeBase64Url(value)));
}

async function getOidcMetadata() {
  if (oidcMetadataCache) return oidcMetadataCache;
  const response = await fetch(`${ISSUER}/.well-known/openid-configuration`, {
    headers: { accept: "application/json" },
  });
  if (!response.ok) throw new Error(`OIDC metadata ${response.status}`);
  oidcMetadataCache = await response.json();
  return oidcMetadataCache;
}

async function getJwks() {
  if (jwksCache) return jwksCache;
  const metadata = await getOidcMetadata();
  const response = await fetch(metadata.jwks_uri, { headers: { accept: "application/json" } });
  if (!response.ok) throw new Error(`OIDC JWKS ${response.status}`);
  jwksCache = await response.json();
  return jwksCache;
}

async function verifyGitHubToken(token) {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("Malformed token");

  const header = decodeJwtJson(parts[0]);
  const claims = decodeJwtJson(parts[1]);
  if (header.alg !== "RS256" || !header.kid) throw new Error("Unexpected token header");

  const jwks = await getJwks();
  const jwk = (jwks.keys || []).find((key) => key.kid === header.kid);
  if (!jwk) {
    jwksCache = null;
    const refreshed = await getJwks();
    const retryKey = (refreshed.keys || []).find((key) => key.kid === header.kid);
    if (!retryKey) throw new Error("Signing key not found");
    return verifyGitHubTokenWithKey(parts, claims, retryKey);
  }
  return verifyGitHubTokenWithKey(parts, claims, jwk);
}

async function verifyGitHubTokenWithKey(parts, claims, jwk) {
  const key = await crypto.subtle.importKey(
    "jwk",
    jwk,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );
  const verified = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    key,
    decodeBase64Url(parts[2]),
    new TextEncoder().encode(`${parts[0]}.${parts[1]}`),
  );
  if (!verified) throw new Error("Bad token signature");

  const now = Math.floor(Date.now() / 1000);
  const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (claims.iss !== ISSUER) throw new Error("Wrong token issuer");
  if (!audiences.includes(EXPECTED_AUDIENCE)) throw new Error("Wrong token audience");
  if (claims.repository !== EXPECTED_REPOSITORY) throw new Error("Wrong repository");
  if (claims.ref !== EXPECTED_REF) throw new Error("Wrong branch");
  if (!claims.exp || claims.exp < now - 5) throw new Error("Expired token");
  if (claims.nbf && claims.nbf > now + 30) throw new Error("Token not active");
  return claims;
}

function validFeed(feed) {
  return Boolean(
    feed &&
      typeof feed === "object" &&
      feed.state &&
      Number.isFinite(Number(feed.state.cycle)) &&
      Array.isArray(feed.conversation) &&
      feed.minds &&
      feed.minds.entities,
  );
}

export class RoomState extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
  }

  async putLatest(feed, sourceSha = "") {
    const incomingCycle = Number(feed?.state?.cycle || 0);
    const current = await this.ctx.storage.get("latest");
    const currentCycle = Number(current?.feed?.state?.cycle || 0);
    if (current && incomingCycle < currentCycle) {
      return { accepted: false, cycle: currentCycle, reason: "older-cycle" };
    }
    const record = {
      feed,
      receivedAt: new Date().toISOString(),
      sourceSha,
    };
    await this.ctx.storage.put("latest", record);
    return { accepted: true, cycle: incomingCycle, receivedAt: record.receivedAt };
  }

  async getLatest() {
    return (await this.ctx.storage.get("latest")) || null;
  }
}

const VIEWER = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#08090d"><title>The Room — Cloudflare Live</title><style>
html,body{margin:0;min-height:100%;background:#08090d;color:#f5f3ee;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}body{padding:0 12px 70px}.top{position:sticky;top:0;background:#08090df5;padding:calc(14px + env(safe-area-inset-top)) 2px 11px;border-bottom:1px solid #252b36;z-index:2}.title{font-size:24px;font-weight:850}.sub{font-size:11px;color:#a3a9b3;margin-top:4px}.status{margin-top:9px;font-size:12px;color:#e0bf79}.status.live{color:#98dfc8}.chat{max-width:760px;margin:14px auto}.beat{font-size:10px;color:#6f7783;text-align:center;margin:18px 0 10px}.msg{background:#11141b;border:1px solid #2b3240;border-radius:16px;padding:11px 13px;margin:0 0 10px}.who{font-size:10px;font-weight:800;letter-spacing:.1em;color:#d7c18a;margin-bottom:6px}.text{font-size:16px;line-height:1.45}.when{font-size:9px;color:#707887;margin-top:7px}.err{padding:24vh 18px;text-align:center;color:#a3a9b3;line-height:1.5}</style></head><body>
<div class="top"><div class="title">The Room</div><div class="sub">Sarah · Mara · Owen · Jules · Cloudflare live relay</div><div id="status" class="status">connecting…</div></div><main id="chat" class="chat"><div class="err">Opening the live Room…</div></main>
<script>(function(){var status=document.getElementById('status'),chat=document.getElementById('chat'),last='',busy=false;function tm(s){try{return new Date(s).toLocaleTimeString([],{hour:'numeric',minute:'2-digit',second:'2-digit'})}catch(e){return''}}function render(r){var f=r.feed||{},c=Array.isArray(f.conversation)?f.conversation:[],m=f.minds&&f.minds.entities||{},st=f.state||{},sig=c.length?String(c[c.length-1].id||'')+':'+c.length:'';var age=r.receivedAt?Math.max(0,Math.floor((Date.now()-Date.parse(r.receivedAt))/1000)):9999;status.className='status'+(age<15?' live':'');status.textContent=(age<15?'LIVE':'STALE')+' · beat '+(st.cycle||'—')+' · '+(st.beat_message_count||0)+' voices · '+age+'s';if(sig===last)return;last=sig;chat.innerHTML='';var start=Math.max(0,c.length-80),prev='';for(var i=start;i<c.length;i++){var x=c[i]||{},b=x.beat_id||'';if(b!==prev){var h=document.createElement('div');h.className='beat';h.textContent='BEAT '+(b?b.slice(-6):'—');chat.appendChild(h);prev=b}var d=document.createElement('div');d.className='msg';var w=document.createElement('div');w.className='who';w.textContent=(m[x.speaker]&&m[x.speaker].name)||x.speaker||'';var t=document.createElement('div');t.className='text';t.textContent=x.text||'';var q=document.createElement('div');q.className='when';q.textContent=tm(x.at);d.appendChild(w);d.appendChild(t);d.appendChild(q);chat.appendChild(d)}if(c.length)window.scrollTo(0,document.body.scrollHeight)}async function refresh(){if(busy)return;busy=true;try{var r=await fetch('/api/feed?fresh='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);render(await r.json())}catch(e){status.className='status';status.textContent='relay unavailable';if(!last)chat.innerHTML='<div class="err">The Cloudflare relay is not receiving the Room yet.</div>'}finally{busy=false}}refresh();setInterval(refresh,2000);document.addEventListener('visibilitychange',function(){if(document.visibilityState==='visible')refresh()})})();</script></body></html>`;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const stub = env.ROOM.getByName("main");

    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET,POST,OPTIONS",
          "access-control-allow-headers": "authorization,content-type",
          "access-control-max-age": "86400",
        },
      });
    }

    if (url.pathname === "/api/ingest" && request.method === "POST") {
      try {
        const auth = request.headers.get("authorization") || "";
        if (!auth.startsWith("Bearer ")) return json({ error: "missing-token" }, 401);
        const claims = await verifyGitHubToken(auth.slice(7));
        const feed = await request.json();
        if (!validFeed(feed)) return json({ error: "invalid-feed" }, 400);
        const result = await stub.putLatest(feed, claims.sha || "");
        return json(result, result.accepted ? 202 : 200);
      } catch (error) {
        return json({ error: "unauthorized", detail: String(error?.message || error) }, 401);
      }
    }

    if (url.pathname === "/api/feed" && request.method === "GET") {
      const latest = await stub.getLatest();
      if (!latest) return json({ error: "no-feed-yet" }, 503);
      return json(latest);
    }

    if (url.pathname === "/health" && request.method === "GET") {
      const latest = await stub.getLatest();
      return json({ ok: true, hasFeed: Boolean(latest), cycle: latest?.feed?.state?.cycle || null, receivedAt: latest?.receivedAt || null });
    }

    if (request.method === "GET" || request.method === "HEAD") {
      return new Response(request.method === "HEAD" ? null : VIEWER, {
        status: 200,
        headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
      });
    }

    return json({ error: "not-found" }, 404);
  },
};
