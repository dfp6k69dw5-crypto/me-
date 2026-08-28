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
if (!html.includes('FAST ORACLE · MK IV')) fail('MK IV marker missing');
if (!html.includes('F₀(x)=x')) fail('Alex recurrence description missing');

const expectedStreams = ['market','btc','eth','sol','doge','ltc','link','avax','bch','xrp','pressure','wiki'];
for (const stream of expectedStreams) {
  if (!new RegExp(`\\b${stream}\\s*:`).test(html)) fail(`fast stream missing: ${stream}`);
}
const retiredStreams = ['aircraft:{','iss:{','wind:{','mag:{','k1m:{','xray:{','air:{','tide:{','buoy:{','river:{','aurora:{','quakes:{','weather:{','github:{'];
for (const token of retiredStreams) if (html.includes(token)) fail(`retired/flaky stream still configured: ${token}`);

const requiredSources = [
  'room-live-mirror.dfp6k69dw5.workers.dev/api/market',
  'ws-feed.exchange.coinbase.com',
  'BTC-USD','ETH-USD','SOL-USD','DOGE-USD','LTC-USD','LINK-USD','AVAX-USD','BCH-USD','XRP-USD',
  'stream.wikimedia.org/v2/stream/recentchange',
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
  'function pairStat',
  'function renderCorrelations',
  'setInterval(sampleSignals,5000)',
  'state.samples.length>180',
  "id=\"accuracy\"",
  "id=\"inverseAccuracy\"",
  "id=\"targetCorr\"",
  "id=\"allCorr\"",
  'for(let i=1n;i<=1000n;i++)',
  'cfg[k].stale',
];
for (const token of guards) if (!html.includes(token)) fail(`reliability/statistics guard missing: ${token}`);

const scripts = [];
for (const m of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)) if (m[1].trim()) scripts.push(m[1]);
if (!scripts.length) fail('no inline JavaScript');
for (const [i,code] of scripts.entries()) {
  try { new vm.Script(code, { filename: `${file}#${i+1}` }); }
  catch (e) { fail(`JavaScript parse error: ${e.message}`); }
}
if ((html.match(/<script\b/gi)||[]).length !== (html.match(/<\/script>/gi)||[]).length) fail('unbalanced script tags');
console.log(`Fast Oracle validation passed: ${expectedStreams.length} fast streams, rolling pairwise correlations, prediction accuracy, recurrence, settlement, and JS parse all present.`);
