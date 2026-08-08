import {FlowerGenome} from './flower-genome.js';

const BASES='ACGT';
const clamp=(x,a=0,b=1)=>x<a?a:x>b?b:x;
function rng32(seed){let a=seed>>>0;return()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
function hash(...xs){let h=2166136261;for(const x0 of xs){let x=x0>>>0;for(let k=0;k<4;k++){h^=(x>>>(k*8))&255;h=Math.imul(h,16777619)}}return(h^(h>>>16))>>>0;}
function altBase(old,rng,transitionBias){
  const transitions={A:'G',G:'A',C:'T',T:'C'};
  if(rng()<transitionBias)return transitions[old];
  let b=old;while(b===old||b===transitions[old])b=BASES[(rng()*4)|0];return b;
}
function revcomp(s){const c={A:'T',T:'A',C:'G',G:'C'};let o='';for(let i=s.length-1;i>=0;i--)o+=c[s[i]];return o;}

export const DEFAULT_SEQUENCE_PROFILE=Object.freeze({
  pressure:.22,
  cluster:.18,
  transition:.58,
  hotspot:.38,
  regulatory:.58,
  microIndel:.08,
  duplication:.05,
  inversion:.04,
  recombination:.06
});

export function normalizeProfile(p={}){const o={};for(const [k,v] of Object.entries(DEFAULT_SEQUENCE_PROFILE)){const n=Number(p[k]);o[k]=Number.isFinite(n)?clamp(n):v;}return o;}

export function mutateSequence(parent,profile={},big=false,seed=Date.now()){
  const p=normalizeProfile(profile),rng=rng32(hash(seed,parent.digest,parent.mutationCount,big?0xb16b00b5:0x51f15e));
  const a=parent.sequence.split(''),L=a.length,G=FlowerGenome.GENES,B=FlowerGenome.BASES_PER_GENE;
  const baseChanges=big?12:1;
  const n=Math.max(1,Math.min(big?850:180,Math.round(baseChanges+(big?260:60)*Math.pow(p.pressure,1.6))));
  const positions=[];
  function choosePos(){
    if(rng()<p.hotspot){
      const g=(rng()*G)|0;
      let local=(rng()*B)|0;
      if(rng()<p.regulatory)local=(rng()*Math.min(160,B))|0;
      return g*B+local;
    }
    return (rng()*L)|0;
  }
  for(let m=0;m<n;m++){
    const center=choosePos(),span=1+Math.round(p.cluster*p.cluster*(big?38:18));
    const reps=1+(rng()<p.cluster?((rng()*span)|0):0);
    for(let r=0;r<reps;r++)positions.push((center+((rng()*span)|0)-((span/2)|0)+L)%L);
  }
  let changed=0;
  for(const pos of positions){const old=a[pos],b=altBase(old,rng,p.transition);if(b!==old){a[pos]=b;changed++;}}

  // Length-preserving micro-indels: rotate a short local window.
  const indelOps=Math.round((big?14:4)*p.microIndel);
  for(let q=0;q<indelOps;q++){const s=choosePos(),w=3+((rng()*(big?18:9))|0),tmp=[];for(let k=0;k<w;k++)tmp.push(a[(s+k)%L]);const shift=1+((rng()*Math.max(1,w-1))|0);for(let k=0;k<w;k++){const i=(s+k)%L,b=tmp[(k+shift)%w];if(a[i]!==b)changed++;a[i]=b;}}

  const dupOps=Math.round((big?8:3)*p.duplication);
  for(let q=0;q<dupOps;q++){const w=8+((rng()*(big?96:40))|0),src=choosePos(),dst=choosePos(),buf=[];for(let k=0;k<w;k++)buf.push(a[(src+k)%L]);for(let k=0;k<w;k++){const i=(dst+k)%L,b=buf[k];if(a[i]!==b)changed++;a[i]=b;}}

  const invOps=Math.round((big?7:2)*p.inversion);
  for(let q=0;q<invOps;q++){const w=10+((rng()*(big?120:48))|0),s=choosePos(),buf=[];for(let k=0;k<w;k++)buf.push(a[(s+k)%L]);const rc=revcomp(buf.join(''));for(let k=0;k<w;k++){const i=(s+k)%L,b=rc[k];if(a[i]!==b)changed++;a[i]=b;}}

  if(rng()<p.recombination*(big?1:.35)){
    const donor=FlowerGenome.randomSequence(hash(seed,parent.digest,0xc0ffee));
    const cuts=2+((rng()*4)|0);for(let q=0;q<cuts;q++){const s=choosePos(),w=20+((rng()*(big?220:90))|0);for(let k=0;k<w;k++){const i=(s+k)%L,b=donor[(s+k)%L];if(a[i]!==b)changed++;a[i]=b;}}
  }

  const child=new FlowerGenome({seed:parent.seed,sequence:a.join(''),mutationCount:parent.mutationCount+changed});
  child.lastMutation={changed,profile:p,big};
  return child;
}
