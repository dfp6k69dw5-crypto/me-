import { DurableObject } from "cloudflare:workers";
import base, { RoomState } from "./open-allen.js";

export { RoomState };

const MOD = 1000003n;
const KEEP = 2880;
const MARKETS = ["ES=F", "NQ=F", "GC=F", "CL=F", "BTC-USD", "ETH-USD"];

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

function clamp(x, a, b) {
  return Math.max(a, Math.min(b, x));
}

function alex(seed) {
  let x = BigInt(Math.abs(Math.trunc(seed))) % MOD;
  for (let i = 1n; i <= 1000n; i += 1n) {
    const tri = (i * (i + 1n)) / 2n;
    x = (x + i * x * x + x * tri) % MOD;
  }
  return Math.sqrt(Number(x));
}

function buildOracle(recent) {
  if (!Array.isArray(recent) || recent.length < 8) return null;
  const n = recent.length;
  const rate = n * 2;
  const bot = recent.filter((v) => v.bot).length / n;
  const minor = recent.filter((v) => v.minor).length / n;
  const newShare = recent.filter((v) => v.type === "new").length / n;
  const logShare = recent.filter((v) => v.type === "log").length / n;
  const meanBytes = recent.reduce((s, v) => s + Math.abs(Number(v.newlen || 0) - Number(v.oldlen || 0)), 0) / n;
  const factors = [
    clamp((rate - 600) / 900, -1, 1),
    clamp((bot - 0.35) / 0.35, -1, 1),
    clamp((minor - 0.2) / 0.25, -1, 1),
    clamp((newShare - 0.08) / 0.12, -1, 1),
    clamp((logShare - 0.08) / 0.12, -1, 1),
    clamp((Math.log10(1 + meanBytes) - 2) / 2, -1, 1),
  ];
  let seed = 17;
  factors.forEach((v, i) => {
    seed = (seed + Math.round((v + 1) * 50000) * (i + 11)) % 1000003;
  });
  return { r: alex(seed), seed, factors, sourceCount: n, rate, bot, minor, newShare, logShare, meanBytes };
}

async function wikimediaRecent() {
  const now = new Date();
  const before = new Date(now.getTime() - 30000);
  const u = new URL("https://en.wikipedia.org/w/api.php");
  u.searchParams.set("action", "query");
  u.searchParams.set("format", "json");
  u.searchParams.set("list", "recentchanges");
  u.searchParams.set("rcprop", "timestamp|sizes|flags|loginfo");
  u.searchParams.set("rclimit", "500");
  u.searchParams.set("rcstart", now.toISOString());
  u.searchParams.set("rcend", before.toISOString());
  u.searchParams.set("rcdir", "older");
  u.searchParams.set("origin", "*");
  const r = await fetch(u.toString(), { headers: { accept: "application/json", "user-agent": "FastOracleLogger/1.0" } });
  if (!r.ok) throw new Error(`wiki ${r.status}`);
  const j = await r.json();
  return (j?.query?.recentchanges || []).map((v) => ({
    type: String(v.type || ""),
    bot: Boolean(v.bot),
    minor: Boolean(v.minor),
    oldlen: Number(v.oldlen || 0),
    newlen: Number(v.newlen || v.oldlen || 0),
  }));
}

async function yahoo(symbol) {
  const u = new URL(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}`);
  u.searchParams.set("interval", "1m");
  u.searchParams.set("range", "1d");
  u.searchParams.set("includePrePost", "true");
  const r = await fetch(u.toString(), {
    headers: { accept: "application/json", "user-agent": "Mozilla/5.0 FastOracleLogger/1.0" },
    cf: { cacheTtl: 0, cacheEverything: false },
  });
  if (!r.ok) throw new Error(`${symbol} ${r.status}`);
  const j = await r.json();
  const c = j?.chart?.result?.[0];
  const times = c?.timestamp || [];
  const closes = c?.indicators?.quote?.[0]?.close || [];
  for (let i = Math.min(times.length, closes.length) - 1; i >= 0; i -= 1) {
    if (Number.isFinite(Number(times[i])) && Number.isFinite(Number(closes[i]))) {
      return { price: Number(closes[i]), marketTs: Number(times[i]) };
    }
  }
  const p = Number(c?.meta?.regularMarketPrice);
  return Number.isFinite(p) ? { price: p, marketTs: null } : null;
}

async function snapshot() {
  const recent = await wikimediaRecent();
  const oracle = buildOracle(recent);
  if (!oracle) throw new Error("not-enough-wikimedia-events");
  const settled = await Promise.allSettled(MARKETS.map(async (symbol) => [symbol, await yahoo(symbol)]));
  const markets = {};
  settled.forEach((v, i) => {
    const symbol = MARKETS[i];
    markets[symbol] = v.status === "fulfilled" ? v.value[1] : { error: String(v.reason?.message || v.reason) };
  });
  return {
    at: new Date().toISOString(),
    model: "nonmarket-wikimedia-r-v1",
    oracle,
    markets,
  };
}

export class OracleState extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
  }

  async append(record) {
    const at = Date.parse(record?.at || "");
    if (!Number.isFinite(at) || !Number.isFinite(Number(record?.oracle?.r))) return { accepted: false, reason: "invalid-record" };
    const key = `oracle:${String(at).padStart(13, "0")}:${crypto.randomUUID()}`;
    await this.ctx.storage.put(key, record);
    const all = await this.ctx.storage.list({ prefix: "oracle:", reverse: true });
    if (all.size > KEEP) {
      const keys = Array.from(all.keys()).slice(KEEP);
      if (keys.length) await this.ctx.storage.delete(keys);
    }
    return { accepted: true, at: record.at };
  }

  async history(limit = 1000) {
    const safe = Math.max(1, Math.min(2880, Number(limit) || 1000));
    const rows = await this.ctx.storage.list({ prefix: "oracle:", reverse: true, limit: safe });
    return { records: Array.from(rows.values()).reverse(), count: rows.size };
  }
}

async function capture(env) {
  const record = await snapshot();
  const stub = env.ORACLE.getByName("main");
  return { record, stored: await stub.append(record) };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/api/oracle-log" && request.method === "GET") {
      const limit = url.searchParams.get("limit") || "1000";
      return json(await env.ORACLE.getByName("main").history(limit));
    }
    if (url.pathname === "/api/oracle-capture" && request.method === "POST") {
      try {
        return json(await capture(env), 202);
      } catch (error) {
        return json({ error: "capture-failed", detail: String(error?.message || error) }, 502);
      }
    }
    return base.fetch(request, env, ctx);
  },

  async scheduled(controller, env, ctx) {
    ctx.waitUntil(capture(env).catch((error) => console.error("oracle capture failed", error)));
  },
};
