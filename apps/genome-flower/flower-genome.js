/*
 * Flower Genome — sequence-to-development module for the Growth Canvas flower lab.
 * Vanilla ES module, zero dependencies.
 *
 * This is a compact artificial gene-regulatory system, not a database of real
 * botanical genes. Every nucleotide participates in decoding either regulatory,
 * protein, kinetic, organiser, morphology or rendering coefficients. Sequence
 * mutations therefore propagate through a high-dimensional developmental state
 * before GrowthCanvas sees kpar/kper growth fields.
 */

const BASES = 'ACGT';
const TAU = Math.PI * 2;
const clamp = (x,a=0,b=1)=>x<a?a:x>b?b:x;
const lerp = (a,b,t)=>a+(b-a)*t;

function mulberry32(seed){
  let a=seed>>>0;
  return ()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};
}
function hash32(str, seed=2166136261){
  let h=seed>>>0;
  for(let i=0;i<str.length;i++){h^=str.charCodeAt(i);h=Math.imul(h,16777619);}
  h^=h>>>16;h=Math.imul(h,0x7feb352d);h^=h>>>15;h=Math.imul(h,0x846ca68b);h^=h>>>16;
  return h>>>0;
}
function hashInts(...xs){
  let h=0x811c9dc5;
  for(const x0 of xs){let x=x0>>>0;for(let k=0;k<4;k++){h^=(x>>>(8*k))&255;h=Math.imul(h,16777619);}}
  h^=h>>>16;h=Math.imul(h,0x7feb352d);h^=h>>>15;return(h^h>>>16)>>>0;
}
function normalFrom(rng){
  let u=0,v=0; while(u<1e-12)u=rng(); while(v<1e-12)v=rng();
  return Math.sqrt(-2*Math.log(u))*Math.cos(TAU*v);
}
function baseNum(c){return c==='A'?0:c==='C'?1:c==='G'?2:3;}
function seqScalar(seq,start,len,salt=0){
  let sum=0,norm=0;
  const phase=((salt>>>0)%104729)*0.0000618034;
  for(let i=0;i<len;i++){
    const b=(baseNum(seq[(start+i)%seq.length])-1.5)/1.5;
    const w=Math.sin((i+1)*1.61803398875+phase)+0.55*Math.cos((i+1)*0.754877666+phase*1.7);
    sum+=b*w; norm+=w*w;
  }
  const z=sum/Math.sqrt(norm+1e-9);
  return 1/(1+Math.exp(-1.18*z));
}
function motifScore(seq,start,len,motif){
  let best=0; const m=motif.length;
  for(let i=0;i<=len-m;i++){
    let s=0; for(let j=0;j<m;j++) s += seq[(start+i+j)%seq.length]===motif[j] ? 1 : -0.36;
    if(s>best)best=s;
  }
  return clamp(best/m,0,1);
}
function codonValue(seq,start){
  return baseNum(seq[start%seq.length])*16+baseNum(seq[(start+1)%seq.length])*4+baseNum(seq[(start+2)%seq.length]);
}
function hueToRgb(h,s,l){
  h=((h%1)+1)%1;s=clamp(s);l=clamp(l);
  const f=(n)=>{const k=(n+h*12)%12;return l-s*Math.min(l,1-l)*Math.max(-1,Math.min(k-3,9-k,1));};
  return [f(0),f(8),f(4)];
}

export class FlowerGenome {
  static GENES = 32;
  static BASES_PER_GENE = 256;
  static LENGTH = FlowerGenome.GENES * FlowerGenome.BASES_PER_GENE;

  constructor({seed=12345, sequence=null, mutationCount=0}={}){
    this.seed=seed>>>0;
    this.mutationCount=mutationCount|0;
    this.sequence = sequence || FlowerGenome.randomSequence(this.seed);
    if(this.sequence.length!==FlowerGenome.LENGTH) throw new Error(`Genome requires ${FlowerGenome.LENGTH} bases`);
    this._decode();
  }
  static randomSequence(seed=12345){
    const rng=mulberry32(seed>>>0); let s='';
    for(let i=0;i<FlowerGenome.LENGTH;i++) s+=BASES[(rng()*4)|0];
    return s;
  }
  clone(){ return new FlowerGenome({seed:this.seed,sequence:this.sequence,mutationCount:this.mutationCount}); }
  mutate({rate=0.0015, substitutions=0, indelRate=0, seed=null}={}){
    const rng=mulberry32((seed ?? hashInts(this.seed,this.mutationCount+1,0x51f15e))>>>0);
    const a=this.sequence.split(''); let changed=0;
    for(let i=0;i<a.length;i++) if(rng()<rate){const old=baseNum(a[i]); a[i]=BASES[(old+1+((rng()*3)|0))&3]; changed++;}
    for(let n=0;n<substitutions;n++){const i=(rng()*a.length)|0,old=baseNum(a[i]);a[i]=BASES[(old+1+((rng()*3)|0))&3];changed++;}
    if(indelRate>0){
      for(let g=0;g<FlowerGenome.GENES;g++) if(rng()<indelRate){
        const off=g*FlowerGenome.BASES_PER_GENE,p=off+((rng()*(FlowerGenome.BASES_PER_GENE-8))|0),w=3+((rng()*6)|0),dir=rng()<0.5?-1:1,slice=a.slice(p,p+w);
        for(let k=0;k<w;k++) a[p+k]=slice[(k+dir+w)%w]; changed+=w;
      }
    }
    const child=new FlowerGenome({seed:this.seed,sequence:a.join(''),mutationCount:this.mutationCount+changed});
    child.lastMutation={changed,rate,substitutions,indelRate}; return child;
  }
  crossover(other,{seed=null}={}){
    if(!(other instanceof FlowerGenome))throw new Error('crossover requires FlowerGenome');
    const rng=mulberry32((seed??hashInts(this.seed,other.seed,this.mutationCount+other.mutationCount))>>>0),cuts=[0];
    for(let i=0;i<5;i++)cuts.push(1+((rng()*(FlowerGenome.LENGTH-2))|0)); cuts.push(FlowerGenome.LENGTH);cuts.sort((a,b)=>a-b);
    let s='',takeA=rng()<0.5; for(let i=0;i<cuts.length-1;i++){s+=(takeA?this.sequence:other.sequence).slice(cuts[i],cuts[i+1]);takeA=!takeA;}
    return new FlowerGenome({seed:this.seed,sequence:s,mutationCount:this.mutationCount+other.mutationCount});
  }
  _decode(){
    const G=FlowerGenome.GENES,B=FlowerGenome.BASES_PER_GENE,S=this.sequence;
    this.basal=new Float64Array(G);this.decay=new Float64Array(G);this.diffusion=new Float64Array(G);this.noise=new Float64Array(G);this.threshold=new Float64Array(G);this.motifs=new Array(G);this.output=new Float64Array(G*12);this.reg=new Float64Array(G*G);this.geneHash=new Uint32Array(G);
    for(let g=0;g<G;g++){
      const o=g*B;this.geneHash[g]=hash32(S.slice(o,o+B),hashInts(g,0x91e10da5));
      this.basal[g]=lerp(-1.6,1.15,seqScalar(S,o,48,g*17+1));this.decay[g]=lerp(0.035,0.28,seqScalar(S,o+48,32,g*17+2));this.diffusion[g]=lerp(0,0.22,Math.pow(seqScalar(S,o+80,32,g*17+3),2));this.noise[g]=lerp(0.002,0.08,seqScalar(S,o+112,24,g*17+4));this.threshold[g]=lerp(0.18,0.82,seqScalar(S,o+136,24,g*17+5));
      let motif='';for(let k=0;k<7;k++)motif+=BASES[codonValue(S,o+160+3*k)&3];this.motifs[g]=motif;
      for(let ch=0;ch<12;ch++){const q=seqScalar(S,o+181+(ch*5)%70,Math.min(24,B-((181+(ch*5)%70))),g*101+ch*13);this.output[g*12+ch]=2*q-1;}
    }
    for(let t=0;t<G;t++){const to=t*B;for(let s=0;s<G;s++){const match=motifScore(S,to,96,this.motifs[s]),mod=seqScalar(S,to,96,hashInts(t,s,0xabc)),sign=seqScalar(S,to+96,32,hashInts(s,t,0xdef))<0.48?-1:1,sparse=match<0.43?0:Math.pow((match-0.43)/0.57,1.35);this.reg[t*G+s]=sign*sparse*lerp(0.3,2.6,mod);}}
    const q=(i,s=0)=>seqScalar(S,(i*379+s*97)%S.length,Math.min(521,S.length),hashInts(i,s,0x47f10a)),hue=q(1),hue2=(hue+lerp(0.08,0.48,q(2)))%1;
    this.traits={petalCount:Math.round(lerp(4,13,q(3))),whorls:q(4)<0.22?2:1,petalScale:lerp(0.78,1.28,q(5)),petalAspect:lerp(0.72,1.36,q(6)),overlap:lerp(0.15,0.78,q(7)),radialJitter:lerp(0.005,0.075,q(8)),bilateral:lerp(-0.18,0.18,q(9)),baseNarrowing:lerp(0.72,1.24,q(10)),tipRoundness:lerp(0.65,1.3,q(11)),growthTime:lerp(0.9,1.8,q(12)),growthAmp:lerp(0.22,0.68,q(13)),anisotropy:lerp(0.05,0.62,q(14)),marginBoost:lerp(-0.18,0.58,q(15)),sideBias:lerp(-0.30,0.30,q(16)),distalBias:lerp(-0.25,0.45,q(17)),polarityStyle:q(18),organiserWidth:lerp(0.035,0.14,q(19)),hue,hue2,saturation:lerp(0.42,0.92,q(20)),lightness:lerp(0.34,0.68,q(21)),veinContrast:lerp(0.03,0.32,q(22)),spotStrength:lerp(0,0.65,q(23)),spotScale:lerp(5,28,q(24)),stripeStrength:lerp(0,0.55,q(25)),stripeFreq:lerp(2.5,13,q(26)),centerDark:lerp(0.05,0.58,q(27)),translucency:lerp(0.05,0.34,q(28)),sheen:lerp(0.05,0.5,q(29)),sepalHue:(lerp(0.25,0.42,q(30)))%1,stamenCount:Math.round(lerp(5,22,q(31))),stamenLength:lerp(0.22,0.55,q(32)),antherSize:lerp(0.025,0.065,q(33)),asymmetry:lerp(0.002,0.06,q(34)),developmentalNoise:lerp(0.003,0.055,q(35)),phase:TAU*q(36),curlCue:lerp(-0.5,0.5,q(37)),depth:lerp(0.12,0.48,q(38))};
    this.digest=hash32(S,0x47f10a);this.variableCount=G*G+G*(5+12)+39+FlowerGenome.LENGTH;
  }
  summary(){return {bases:this.sequence.length,genes:FlowerGenome.GENES,regulatoryWeights:FlowerGenome.GENES**2,decodedVariables:this.variableCount,mutations:this.mutationCount,digest:this.digest.toString(16).padStart(8,'0'),...this.traits};}
  develop({nu=31,nv=31,steps=22,seed=null}={}){
    const G=FlowerGenome.GENES,N=nu*nv,rng=mulberry32((seed??hashInts(this.digest,nu,nv,steps))>>>0);let x=new Float32Array(G*N),next=new Float32Array(G*N);const uCoord=new Float32Array(N),vCoord=new Float32Array(N);
    for(let i=0;i<nu;i++)for(let j=0;j<nv;j++){const p=i*nv+j,u=i/(nu-1),v=-1+2*j/(nv-1);uCoord[p]=u;vCoord[p]=v;for(let g=0;g<G;g++){const phase=((this.geneHash[g]>>>8)&65535)/65535*TAU,spatial=0.34*Math.sin(Math.PI*u*(1+(g%4)*0.35)+phase)+0.22*Math.cos(v*Math.PI*(1+(g%3))*0.5-phase);x[g*N+p]=clamp(1/(1+Math.exp(-(this.basal[g]+spatial))));}}
    const invDu2=(nu-1)*(nu-1),invDv2=0.25*(nv-1)*(nv-1),dt=0.18;
    const morph=(g,u,v)=>{const d0=Math.exp(-u*5.5),d1=Math.exp(-(1-u)*5.5),margin=Math.pow(Math.abs(v),2.4),mid=Math.exp(-v*v*5.5),h=this.geneHash[g];return((h&3)-1.5)*0.18*d0+(((h>>>2)&3)-1.5)*0.18*d1+(((h>>>4)&3)-1.5)*0.16*margin+(((h>>>6)&3)-1.5)*0.12*mid+(((h>>>8)&3)-1.5)*0.08*v;};
    for(let step=0;step<steps;step++){for(let g=0;g<G;g++){const go=g*N,D=this.diffusion[g],dec=this.decay[g],thr=this.threshold[g],noise=this.noise[g]*this.traits.developmentalNoise/0.055;for(let i=0;i<nu;i++)for(let j=0;j<nv;j++){const p=i*nv+j,idx=go+p,cur=x[idx];let z=this.basal[g]+morph(g,uCoord[p],vCoord[p]),ro=g*G;for(let s=0;s<G;s++)z+=this.reg[ro+s]*(x[s*N+p]-0.5)*0.22;const target=1/(1+Math.exp(-2.15*(z-thr+0.5)));let lap=0;if(D>0){const im=i?i-1:i,ip=i<nu-1?i+1:i,jm=j?j-1:j,jp=j<nv-1?j+1:j;lap=((x[go+ip*nv+j]-2*cur+x[go+im*nv+j])*invDu2+(x[go+i*nv+jp]-2*cur+x[go+i*nv+jm])*invDv2)*0.0012;}next[idx]=clamp(cur+dt*((target-cur)*0.72-dec*(cur-0.15)+D*lap)+normalFrom(rng)*noise*0.025);}}const tmp=x;x=next;next=tmp;}
    const channels=new Float32Array(12*N);for(let p=0;p<N;p++)for(let ch=0;ch<12;ch++){let z=0;for(let g=0;g<G;g++)z+=this.output[g*12+ch]*(x[g*N+p]-0.5);z/=Math.sqrt(G);channels[ch*N+p]=1/(1+Math.exp(-2.2*z));}return new DevelopmentMap(this,nu,nv,x,channels,uCoord,vCoord);
  }
  colorAt(u,v,dev){const t=this.traits,p0=dev.sampleChannel(4,u,v),p1=dev.sampleChannel(5,u,v),vein=dev.sampleChannel(6,u,v),pat=dev.sampleChannel(7,u,v),hue=(t.hue*(0.62+0.38*p0)+t.hue2*(0.38-0.25*p0)+0.035*Math.sin(t.phase+v*5+u*2))%1;let sat=clamp(t.saturation*(0.78+0.35*p1)),light=clamp(t.lightness*(0.72+0.45*p0));const stripes=Math.sin((v*0.5+0.5)*Math.PI*t.stripeFreq+u*5+t.phase)*0.5+0.5,spots=Math.sin((u*17+v*11)*t.spotScale*0.09+t.phase)*Math.sin((u*9-v*15)*t.spotScale*0.07-t.phase)*0.5+0.5,center=Math.exp(-u*5.2)*(1-v*v*0.25);light*=1-t.centerDark*center*0.55;light*=1-t.veinContrast*vein*Math.pow(Math.abs(Math.sin(v*Math.PI*5+u*7)),6);light*=1-t.stripeStrength*pat*stripes*0.28;light*=1-t.spotStrength*(1-pat)*spots*0.22;sat=clamp(sat+0.12*t.spotStrength*spots);return hueToRgb(hue,sat,light);}
}

export class DevelopmentMap {
  constructor(genome,nu,nv,genes,channels,uCoord,vCoord){this.genome=genome;this.nu=nu;this.nv=nv;this.N=nu*nv;this.genes=genes;this.channels=channels;this.uCoord=uCoord;this.vCoord=vCoord;}
  _sample(arr,plane,u,v){u=clamp(u);v=clamp((v+1)*0.5);const x=u*(this.nu-1),y=v*(this.nv-1),i=Math.min(this.nu-2,Math.max(0,Math.floor(x))),j=Math.min(this.nv-2,Math.max(0,Math.floor(y))),a=x-i,b=y-j,o=plane*this.N,p00=o+i*this.nv+j,p10=o+(i+1)*this.nv+j,p01=p00+1,p11=p10+1;return lerp(lerp(arr[p00],arr[p10],a),lerp(arr[p01],arr[p11],a),b);}
  sampleGene(g,u,v){return this._sample(this.genes,((g%FlowerGenome.GENES)+FlowerGenome.GENES)%FlowerGenome.GENES,u,v);}
  sampleChannel(ch,u,v){return this._sample(this.channels,((ch%12)+12)%12,u,v);}
  growthAt(u,v){const t=this.genome.traits,axial=this.sampleChannel(0,u,v),trans=this.sampleChannel(1,u,v),margin=this.sampleChannel(2,u,v),distal=this.sampleChannel(3,u,v),m=Math.pow(Math.abs(v),2.2),common=t.growthAmp*(0.58+0.52*axial+0.22*distal+t.marginBoost*m+t.distalBias*(u-0.5)+t.sideBias*v*0.35),an=t.anisotropy*(0.35+0.75*trans);return{kpar:Math.max(0.015,common*(1+an)),kper:Math.max(0.012,common*(1-an*0.68))};}
}

export function genomeDifference(a,b){if(!(a instanceof FlowerGenome)||!(b instanceof FlowerGenome))throw new Error('FlowerGenome required');let bases=0;for(let i=0;i<a.sequence.length;i++)if(a.sequence[i]!==b.sequence[i])bases++;let reg=0;for(let i=0;i<a.reg.length;i++)reg=Math.max(reg,Math.abs(a.reg[i]-b.reg[i]));let trait=0;for(const k of Object.keys(a.traits))if(typeof a.traits[k]==='number')trait=Math.max(trait,Math.abs(a.traits[k]-b.traits[k]));return{bases,maxRegulatoryChange:reg,maxTraitChange:trait,sameDigest:a.digest===b.digest};}
