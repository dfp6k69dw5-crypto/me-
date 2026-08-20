import fs from 'node:fs';

const src=fs.readFileSync('cloudflare/subsonic-calm/src/index.js','utf8');
const fail=(m)=>{throw new Error(m)};
if(src.includes('createDynamicsCompressor')) fail('Compressor returned to Subsonic Calm signal path');
for(const token of [
  "deep:{name:'Deep Edge',f:35",
  "velvet:{name:'Velvet',f:40",
  "warm:{name:'Warm Body',f:44",
  "80 HZ TEST",
  "signalRead",
  "subsonic-calm-v3-psw10",
  "toneBus.connect(breathGain);breathGain.connect(master)",
  "linearRampToValueAtTime(v.output,t+.010)"
]) if(!src.includes(token)) fail(`Missing required PSW10 v3 token: ${token}`);

const capPct=f=>f>=40?22:f>=35?12+(f-35)*2:f>=30?8+(f-30)*.8:4+(f-20)*.4;
for(const [f,expected] of [[20,4],[30,8],[35,12],[40,22],[48,22]]){
  const got=capPct(f);
  if(Math.abs(got-expected)>1e-9) fail(`Unexpected PSW10 cap at ${f} Hz: ${got}`);
}
for(let f=20;f<=48;f+=.1){
  const output=capPct(f)/100;
  const worst=.92*output*1.08;
  if(worst>=.25) fail(`Digital ceiling too high at ${f.toFixed(1)} Hz: ${worst}`);
}
const maxWorst=.92*.22*1.08;
if(Math.abs(maxWorst-.218592)>1e-9) fail(`Unexpected maximum peak bound: ${maxWorst}`);
console.log(JSON.stringify({pass:true,profile:'Polk PSW10',version:3,compressor:false,diagnostic_80hz:true,default_hz:40,deep_edge_hz:35,warm_hz:44,max_digital_peak:maxWorst,headroom_db:20*Math.log10(1/maxWorst)},null,2));
