import fs from 'node:fs';
import path from 'node:path';

const MOD = 1000003n;
const MARKETS = ['ES=F','NQ=F','GC=F','CL=F','BTC-USD','ETH-USD'];
const STREAM = 'https://stream.wikimedia.org/v2/stream/recentchange';
const MARKET = 'https://room-live-mirror.dfp6k69dw5.workers.dev/api/market';
const clamp = (x,a,b) => Math.max(a,Math.min(b,x));
const SNAPSHOT_MS = 30000;
const MIN_INTERVAL_MS = 5*60*1000;
const HISTORY_DIR = path.join('room','oracle-history');
const LOCK_DIR = path.join('.room_model','fast-oracle-recorder.lock');

function alex(seed){
  let x = BigInt(Math.abs(Math.trunc(seed))) % MOD;
  for(let i=1n;i<=1000n;i++){
    const tri = i*(i+1n)/2n;
    x = (x + i*x*x + x*tri) % MOD;
  }
  return Math.sqrt(Number(x));
}

function buildOracle(e){
  if(!Array.isArray(e) || e.length < 8) throw new Error('not enough Wikimedia events');
  const n=e.length, rate=n*2;
  const bot=e.filter(v=>v.bot).length/n;
  const minor=e.filter(v=>v.minor).length/n;
  const newShare=e.filter(v=>v.type==='new').length/n;
  const logShare=e.filter(v=>v.type==='log').length/n;
  const meanBytes=e.reduce((s,v)=>s+Math.abs(v.bytes),0)/n;
  const factors=[
    clamp((rate-600)/900,-1,1),
    clamp((bot-.35)/.35,-1,1),
    clamp((minor-.2)/.25,-1,1),
    clamp((newShare-.08)/.12,-1,1),
    clamp((logShare-.08)/.12,-1,1),
    clamp((Math.log10(1+meanBytes)-2)/2,-1,1),
  ];
  let seed=17;
  factors.forEach((v,i)=>{seed=(seed+Math.round((v+1)*50000)*(i+11))%1000003});
  return {r:alex(seed),seed,factors,sourceCount:n,rate,bot,minor,newShare,logShare,meanBytes};
}

function latestRecordTime(){
  if(!fs.existsSync(HISTORY_DIR)) return NaN;
  const files=fs.readdirSync(HISTORY_DIR).filter(v=>/^\d{4}-\d{2}-\d{2}\.jsonl$/.test(v)).sort();
  if(!files.length) return NaN;
  const text=fs.readFileSync(path.join(HISTORY_DIR,files.at(-1)),'utf8').trim();
  if(!text) return NaN;
  try{return Date.parse(JSON.parse(text.split('\n').filter(Boolean).at(-1)).at||'')}catch{return NaN}
}

function acquireLock(){
  fs.mkdirSync('.room_model',{recursive:true});
  try{
    fs.mkdirSync(LOCK_DIR);
    fs.writeFileSync(path.join(LOCK_DIR,'pid'),String(process.pid));
    return true;
  }catch(e){
    if(e?.code!=='EEXIST') throw e;
    try{
      const pid=Number(fs.readFileSync(path.join(LOCK_DIR,'pid'),'utf8'));
      if(Number.isInteger(pid)&&pid>0){
        process.kill(pid,0);
        return false;
      }
    }catch{}
    fs.rmSync(LOCK_DIR,{recursive:true,force:true});
    fs.mkdirSync(LOCK_DIR);
    fs.writeFileSync(path.join(LOCK_DIR,'pid'),String(process.pid));
    return true;
  }
}

function releaseLock(){
  try{fs.rmSync(LOCK_DIR,{recursive:true,force:true})}catch{}
}

async function wikiStreamSample(ms=SNAPSHOT_MS){
  const ctl=new AbortController();
  const timer=setTimeout(()=>ctl.abort(),ms);
  const events=[];
  const sampleStart=new Date();
  try{
    const r=await fetch(STREAM,{
      headers:{accept:'text/event-stream','user-agent':'FastOracleRecorder/3.0'},
      signal:ctl.signal,
    });
    if(!r.ok) throw new Error(`wiki stream ${r.status}`);
    if(!r.body) throw new Error('wiki stream has no body');
    const reader=r.body.getReader();
    const dec=new TextDecoder();
    let buf='';
    while(true){
      let part;
      try{part=await reader.read()}catch(e){
        if(ctl.signal.aborted) break;
        throw e;
      }
      if(part.done) break;
      buf=(buf+dec.decode(part.value,{stream:true})).replace(/\r\n/g,'\n');
      let cut;
      while((cut=buf.indexOf('\n\n'))>=0){
        const block=buf.slice(0,cut); buf=buf.slice(cut+2);
        for(const line of block.split('\n')){
          if(!line.startsWith('data:')) continue;
          try{
            const j=JSON.parse(line.slice(5).trim());
            const oldLen=Number(j?.length?.old||0);
            const newLen=Number(j?.length?.new??oldLen);
            events.push({bot:!!j.bot,minor:!!j.minor,type:String(j.type||''),bytes:newLen-oldLen});
          }catch{}
        }
      }
      if(ctl.signal.aborted) break;
    }
  } finally {
    clearTimeout(timer);
    ctl.abort();
  }
  return {events,sampleStart:sampleStart.toISOString(),sampleEnd:new Date().toISOString()};
}

async function yahoo(symbol){
  const u = new URL(MARKET);
  u.searchParams.set('symbol',symbol);
  u.searchParams.set('interval','1m');
  u.searchParams.set('range','1d');
  u.searchParams.set('prepost','1');
  u.searchParams.set('fresh',Date.now().toString());
  const r=await fetch(u,{headers:{accept:'application/json'}});
  if(!r.ok) throw new Error(`${symbol} proxy ${r.status}`);
  const j=await r.json();
  const c=j?.payload?.chart?.result?.[0], times=c?.timestamp||[], closes=c?.indicators?.quote?.[0]?.close||[];
  for(let i=Math.min(times.length,closes.length)-1;i>=0;i--){
    if(Number.isFinite(Number(times[i]))&&Number.isFinite(Number(closes[i]))) return {price:Number(closes[i]),marketTs:Number(times[i])};
  }
  const p=Number(c?.meta?.regularMarketPrice);
  return Number.isFinite(p)?{price:p,marketTs:null}:null;
}

fs.mkdirSync(HISTORY_DIR,{recursive:true});
const lastAt=latestRecordTime();
const now=Date.now();
if(Number.isFinite(lastAt)&&now-lastAt<MIN_INTERVAL_MS){
  console.log(JSON.stringify({skipped:true,reason:'interval',ageMs:now-lastAt}));
  process.exit(0);
}
if(!acquireLock()){
  console.log(JSON.stringify({skipped:true,reason:'sampling-in-progress'}));
  process.exit(0);
}

try{
  const sample=await wikiStreamSample();
  const oracle=buildOracle(sample.events);
  const results=await Promise.allSettled(MARKETS.map(async s=>[s,await yahoo(s)]));
  const markets={};
  results.forEach((v,i)=>{markets[MARKETS[i]]=v.status==='fulfilled'?v.value[1]:{error:String(v.reason?.message||v.reason)}});
  const at=new Date();
  const record={
    at:at.toISOString(),
    sampleStart:sample.sampleStart,
    sampleEnd:sample.sampleEnd,
    model:'nonmarket-wikimedia-r-v3-global-stream-worker-market',
    oracle,
    markets,
  };
  const file=path.join(HISTORY_DIR,`${at.toISOString().slice(0,10)}.jsonl`);
  fs.appendFileSync(file,JSON.stringify(record)+'\n');
  console.log(JSON.stringify({at:record.at,sampleStart:record.sampleStart,sampleEnd:record.sampleEnd,r:record.oracle.r,events:sample.events.length,markets:record.markets},null,2));
} finally {
  releaseLock();
}
