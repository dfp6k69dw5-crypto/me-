import fs from 'node:fs';
import path from 'node:path';

const MOD = 1000003n;
const MARKETS = ['ES=F','NQ=F','GC=F','CL=F','BTC-USD','ETH-USD'];
const clamp = (x,a,b) => Math.max(a,Math.min(b,x));

function alex(seed){
  let x = BigInt(Math.abs(Math.trunc(seed))) % MOD;
  for(let i=1n;i<=1000n;i++){
    const tri = i*(i+1n)/2n;
    x = (x + i*x*x + x*tri) % MOD;
  }
  return Math.sqrt(Number(x));
}

async function wikiRecent(){
  const now = new Date();
  const before = new Date(now.getTime()-30000);
  const u = new URL('https://en.wikipedia.org/w/api.php');
  u.searchParams.set('action','query');
  u.searchParams.set('format','json');
  u.searchParams.set('list','recentchanges');
  u.searchParams.set('rcprop','timestamp|sizes|flags|loginfo');
  u.searchParams.set('rclimit','500');
  u.searchParams.set('rcstart',now.toISOString());
  u.searchParams.set('rcend',before.toISOString());
  u.searchParams.set('rcdir','older');
  const r = await fetch(u,{headers:{accept:'application/json','user-agent':'FastOracleRecorder/1.0'}});
  if(!r.ok) throw new Error(`wiki ${r.status}`);
  const j = await r.json();
  return j?.query?.recentchanges || [];
}

function buildOracle(e){
  if(!Array.isArray(e) || e.length < 8) throw new Error('not enough Wikimedia events');
  const n=e.length, rate=n*2;
  const bot=e.filter(v=>v.bot).length/n;
  const minor=e.filter(v=>v.minor).length/n;
  const newShare=e.filter(v=>v.type==='new').length/n;
  const logShare=e.filter(v=>v.type==='log').length/n;
  const meanBytes=e.reduce((s,v)=>s+Math.abs(Number(v.newlen||0)-Number(v.oldlen||0)),0)/n;
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

async function yahoo(symbol){
  const u = new URL(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}`);
  u.searchParams.set('interval','1m');
  u.searchParams.set('range','1d');
  u.searchParams.set('includePrePost','true');
  const r=await fetch(u,{headers:{accept:'application/json','user-agent':'Mozilla/5.0 FastOracleRecorder/1.0'}});
  if(!r.ok) throw new Error(`${symbol} ${r.status}`);
  const j=await r.json();
  const c=j?.chart?.result?.[0], times=c?.timestamp||[], closes=c?.indicators?.quote?.[0]?.close||[];
  for(let i=Math.min(times.length,closes.length)-1;i>=0;i--){
    if(Number.isFinite(Number(times[i]))&&Number.isFinite(Number(closes[i]))) return {price:Number(closes[i]),marketTs:Number(times[i])};
  }
  const p=Number(c?.meta?.regularMarketPrice);
  return Number.isFinite(p)?{price:p,marketTs:null}:null;
}

const at=new Date();
const oracle=buildOracle(await wikiRecent());
const results=await Promise.allSettled(MARKETS.map(async s=>[s,await yahoo(s)]));
const markets={};
results.forEach((v,i)=>{markets[MARKETS[i]]=v.status==='fulfilled'?v.value[1]:{error:String(v.reason?.message||v.reason)}});
const record={at:at.toISOString(),model:'nonmarket-wikimedia-r-v1',oracle,markets};
const day=at.toISOString().slice(0,10);
const dir=path.join('data','fast-oracle');
fs.mkdirSync(dir,{recursive:true});
fs.appendFileSync(path.join(dir,`${day}.jsonl`),JSON.stringify(record)+'\n');
console.log(JSON.stringify({at:record.at,r:record.oracle.r,markets:record.markets},null,2));
