import fs from 'node:fs';
import vm from 'node:vm';

const file = 'apps/live-earth-oracle.html';
const html = fs.readFileSync(file, 'utf8');

function fail(message) {
  console.error(`Fast Oracle validation failed: ${message}`);
  process.exit(1);
}

if (!html.includes('<title>The Fast Nonsense Predictor</title>')) fail('fast predictor title missing');
if (!html.includes('Experiment, not investment advice.')) fail('experiment disclaimer missing');
if (!html.includes('FAST ORACLE · MK IX')) fail('MK IX marker missing');
if (!html.includes('50% PHYSICAL WORLD + 50% HUMAN ACTIVITY')) fail('50/50 composite R label missing');
if (!html.includes('exactly four square roots')) fail('fixed-four-root description missing');
if (!html.includes('recomputes R on every edit event')) fail('per-edit R recompute statement missing');
if (!html.includes('no market, crypto, futures, or order-pressure data enters R'.toUpperCase()) && !html.includes('NO market, crypto, futures, or order-pressure data enters R')) fail('market-exclusion statement missing');

const expectedStreams = ['market','btc','eth','sol','doge','ltc','link','avax','bch','xrp','pressure','wiki','quake','kp','hn'];
for (const stream of expectedStreams) {
  if (!new RegExp(`\\b${stream}\\s*:`).test(html)) fail(`stream missing: ${stream}`);
}

const requiredSources = [
  'room-live-mirror.dfp6k69dw5.workers.dev/api/market',
  'ws-feed.exchange.coinbase.com',
  'stream.wikimedia.org/v2/stream/recentchange',
  'earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson',
  'services.swpc.noaa.gov/products/noaa-planetary-k-index.json',
  'hacker-news.firebaseio.com/v0/maxitem.json',
  'BTC-USD','ETH-USD','SOL-USD','DOGE-USD','LTC-USD','LINK-USD','AVAX-USD','BCH-USD','XRP-USD',
];
for (const source of requiredSources) if (!html.includes(source)) fail(`source missing: ${source}`);

const guards = [
  'AbortController',
  "document.visibilityState==='visible'",
  'setTimeout(crypto,3500)',
  'localStorage.setItem',
  'function pearsonPairs',
  'function settle',
  'function issuePrediction',
  'function sampleSignals',
  'function rStat',
  'function renderCorrelations',
  'function bucketScores',
  "meanLive(['quake','kp'])",
  "meanLive(['wiki','hn'])",
  '(physical+human)/2',
  'FIXED_ROOTS=4',
  'for(let i=1n;i<=1000n;i++)',
  'setInterval(sampleSignals,5000)',
  'state.samples.length>180',
  "id=\"accuracy\"",
  "id=\"inverseAccuracy\"",
  "id=\"rCorr\"",
  'rInput:true',
  'cfg[k].stale',
  'Math.tanh((rate-600)/900)',
  "setCard('wiki',rate+' / min','global Wikimedia activity · every event',factor,rate)",
];
for (const token of guards) if (!html.includes(token)) fail(`reliability/statistics guard missing: ${token}`);

if (html.includes('clamp((rate-600)/900,-1,1)')) fail('old saturating Wikimedia normalization returned');
if (html.includes('id="targetCorr"') || html.includes('id="allCorr"')) fail('old pairwise correlation panels returned');
if (html.includes('TAME_LIMIT')) fail('adaptive R ceiling returned');

const scripts = [];
for (const m of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)) if (m[1].trim()) scripts.push(m[1]);
if (!scripts.length) fail('no inline JavaScript');
for (const [i,code] of scripts.entries()) {
  try { new vm.Script(code, { filename: `${file}#${i+1}` }); }
  catch (e) { fail(`JavaScript parse error: ${e.message}`); }
}
if ((html.match(/<script\b/gi)||[]).length !== (html.match(/<\/script>/gi)||[]).length) fail('unbalanced script tags');
console.log(`Fast Oracle validation passed: ${expectedStreams.length} streams, event-driven Wikimedia R, 50/50 composite R, fixed four roots, R-only correlations, prediction settlement, and JavaScript parse all present.`);
