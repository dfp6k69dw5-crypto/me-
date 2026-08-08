import {FlowerGenome} from './flower-genome.js';

const BASES='ACGT';
const clamp=(x,a=0,b=1)=>x<a?a:x>b?b:x;
const lerp=(a,b,t)=>a+(b-a)*t;
function hashString(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}h^=h>>>16;h=Math.imul(h,0x7feb352d);h^=h>>>15;return(h^h>>>16)>>>0;}
function rng32(seed){let a=seed>>>0;return()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
function baseNum(c){return c==='A'?0:c==='C'?1:c==='G'?2:3;}

// These are synthetic, sequence-addressable regulatory proxies inspired by
// well-studied flowering-plant pathways (ABC(E) organ identity, CYC/TCP symmetry,
// auxin/polarity, growth, epidermal and pigment networks). They are not literal
// copies of any species' genes. Each slider edits bases at an assigned locus;
// overlapping windows deliberately create pleiotropy.
export const CONTROL_GROUPS=[
  {name:'Organ identity & symmetry',controls:[
    ['aIdentity','A-class identity (AP1/AP2 proxy)'],['bIdentity','B-class identity (AP3/PI proxy)'],['cIdentity','C-class identity (AG proxy)'],['eIdentity','E-class / SEP proxy'],
    ['petaloidy','Petaloid organ identity'],['staminoidy','Staminoid organ identity'],['bilateral','CYC/TCP bilateral symmetry'],['dorsoventral','Dorsal–ventral contrast']
  ]},
  {name:'Petal architecture',controls:[
    ['petalNumber','Petal initiation number'],['whorlNumber','Whorl proliferation'],['petalFusion','Petal fusion'],['tubeDepth','Corolla tube depth'],
    ['lipIdentity','Labellum / lip identity'],['spurGrowth','Nectar-spur growth'],['petalAspect','Petal length : width'],['petalOverlap','Petal overlap']
  ]},
  {name:'Growth mechanics',controls:[
    ['auxinTransport','Auxin transport / PIN proxy'],['polarityStrength','Tissue polarity strength'],['parallelGrowth','Growth parallel to polarity'],['perpGrowth','Growth perpendicular to polarity'],
    ['marginGrowth','Marginal growth'],['distalGrowth','Distal growth'],['basalGrowth','Basal growth'],['growthDuration','Developmental growth duration']
  ]},
  {name:'Curvature & edge',controls:[
    ['cupCurvature','Cup curvature'],['reflex','Petal reflexing'],['twist','Petal twist'],['ruffle','Margin ruffling'],
    ['serration','Margin serration'],['fringe','Fringed edge'],['thickness','Petal thickness'],['epidermalCones','MIXTA-like epidermal cones']
  ]},
  {name:'Pigment pathways',controls:[
    ['anthocyanin','Anthocyanin pathway'],['carotenoid','Carotenoid pathway'],['chlorophyll','Chlorophyll retention'],['pigmentSaturation','Pigment saturation'],
    ['pigmentLightness','Pigment lightness'],['bicolor','Bicolor separation'],['veinPigment','Vein pigmentation'],['centerPigment','Center / throat pigmentation']
  ]},
  {name:'Pattern formation',controls:[
    ['spots','Spot formation'],['stripes','Stripe formation'],['speckles','Speckling'],['throatBlotch','Throat blotch'],
    ['marginBand','Margin band'],['pigmentGradient','Pigment gradient'],['venationDensity','Visible venation'],['patternScale','Pattern spatial scale']
  ]},
  {name:'Reproductive organs',controls:[
    ['stamenNumber','Stamen number'],['stamenLength','Stamen length'],['antherSize','Anther size'],['filamentSpread','Filament spread'],
    ['styleLength','Style length'],['stigmaSize','Stigma size'],['pollenDisplay','Pollen display'],['centerOpenness','Center openness']
  ]},
  {name:'Inflorescence & support',controls:[
    ['solitaryCluster','Solitary ↔ clustered'],['compositeDisk','Composite disk tendency'],['branching','Inflorescence branching'],['clusterDensity','Cluster density'],
    ['pedicelLength','Pedicel length'],['bractSize','Bract / sepal size'],['leafBroadness','Leaf broadness'],['leafLobing','Leaf lobing']
  ]},
  {name:'Developmental variation',controls:[
    ['heterochrony','Developmental timing shift'],['developmentalNoise','Developmental noise'],['asymmetry','Developmental asymmetry'],['organScale','Overall organ scale'],
    ['depth','Three-dimensional depth'],['phyllotaxis','Phyllotactic offset'],['stability','Canalization / stability'],['plasticity','Developmental plasticity']
  ]}
].map((group,gi)=>({name:group.name,controls:group.controls.map((x,ci)=>({key:x[0],label:x[1],index:gi*8+ci}))}));

export const CONTROL_DEFS=CONTROL_GROUPS.flatMap(g=>g.controls);
export const CONTROL_COUNT=CONTROL_DEFS.length;

function locusFor(def){
  const i=def.index,h=hashString(def.key);
  const gene=(i*7+(h&31))%FlowerGenome.GENES;
  const width=28;
  const room=FlowerGenome.BASES_PER_GENE-width-8;
  const local=4+((i*47+((h>>>8)&255))%Math.max(1,room));
  return {start:gene*FlowerGenome.BASES_PER_GENE+local,width,gene};
}

export function readControl(genome,key){
  const def=CONTROL_DEFS.find(d=>d.key===key);if(!def)throw new Error(`Unknown control ${key}`);
  const {start,width}=locusFor(def),S=genome.sequence;let s=0,w=0;
  for(let i=0;i<width;i++){
    const wt=.72+.28*Math.cos((i+1)*1.61803398875+(def.index+1)*.37);
    s+=baseNum(S[(start+i)%S.length])*wt;w+=3*wt;
  }
  return clamp(s/Math.max(1e-9,w));
}

export function readAllControls(genome){
  const o={};for(const d of CONTROL_DEFS)o[d.key]=readControl(genome,d.key);return o;
}

export function steerControl(parent,key,target,seed=Date.now()){
  target=clamp(Number(target));
  const def=CONTROL_DEFS.find(d=>d.key===key);if(!def)throw new Error(`Unknown control ${key}`);
  const {start,width}=locusFor(def),a=parent.sequence.split(''),rng=rng32((seed^parent.digest^hashString(key))>>>0);
  let changed=0;
  for(let i=0;i<width;i++){
    const wobble=(rng()-.5)*.34 + .08*Math.sin((i+1)*2.399963);
    const desired=clamp(target+wobble,0,1)*3;
    let rank=Math.floor(desired);if(rng()<desired-rank)rank++;rank=Math.max(0,Math.min(3,rank));
    const pos=(start+i)%a.length,b=BASES[rank];if(a[pos]!==b){a[pos]=b;changed++;}
  }
  const child=new FlowerGenome({seed:parent.seed,sequence:a.join(''),mutationCount:parent.mutationCount+changed});
  child.lastMutation={changed,steered:key,target,locus:locusFor(def)};return child;
}

export function randomizeControlGroup(parent,groupName,amount=.8,seed=Date.now()){
  const group=CONTROL_GROUPS.find(g=>g.name===groupName);if(!group)throw new Error(`Unknown group ${groupName}`);
  let g=parent;const rng=rng32((seed^parent.digest^hashString(groupName))>>>0);
  for(const d of group.controls){
    const old=readControl(g,d.key),target=clamp(lerp(old,rng(),amount));g=steerControl(g,d.key,target,(rng()*0xffffffff)>>>0);
  }
  return g;
}

export function derivePhenotype(genome){
  const c=readAllControls(genome),t=genome.traits;
  return {
    controls:c,
    organIdentity:{a:c.aIdentity,b:c.bIdentity,c:c.cIdentity,e:c.eIdentity,petaloidy:c.petaloidy,staminoidy:c.staminoidy},
    bilateral:clamp(.58*c.bilateral+.24*Math.abs(t.bilateral)*3+.18*c.dorsoventral),
    petalCount:Math.max(3,Math.round(lerp(3,48,c.petalNumber)*lerp(.72,1.28,(t.petalCount-4)/9))),
    whorls:Math.max(1,Math.round(lerp(1,8,c.whorlNumber))),
    fusion:clamp(.75*c.petalFusion+.25*c.tubeDepth),tube:clamp(.62*c.tubeDepth+.38*c.petalFusion),lip:clamp(.72*c.lipIdentity+.28*c.bilateral),spur:c.spurGrowth,
    aspect:lerp(.42,2.2,clamp(.62*c.petalAspect+.38*((t.petalAspect-.72)/.64))),overlap:clamp(.65*c.petalOverlap+.35*t.overlap),
    polarity:clamp(.72*c.polarityStrength+.28*(1-Math.abs(t.sideBias))),kpar:lerp(.58,1.72,c.parallelGrowth),kper:lerp(.58,1.72,c.perpGrowth),
    margin:lerp(-.28,.82,c.marginGrowth)+t.marginBoost*.28,distal:lerp(-.28,.72,c.distalGrowth)+t.distalBias*.22,basal:lerp(-.24,.55,c.basalGrowth),growthDuration:lerp(.72,1.95,c.growthDuration)*lerp(.85,1.15,t.growthTime/1.8),
    cup:lerp(-.35,.95,c.cupCurvature),reflex:lerp(-.22,.95,c.reflex),twist:lerp(-.75,.75,c.twist),ruffle:c.ruffle,serration:c.serration,fringe:c.fringe,thickness:lerp(.18,1,c.thickness),epidermalCones:c.epidermalCones,
    anthocyanin:c.anthocyanin,carotenoid:c.carotenoid,chlorophyll:c.chlorophyll,saturation:clamp(.58*c.pigmentSaturation+.42*t.saturation),lightness:clamp(.58*c.pigmentLightness+.42*t.lightness),bicolor:c.bicolor,veinPigment:c.veinPigment,centerPigment:c.centerPigment,
    spots:clamp(.64*c.spots+.36*t.spotStrength),stripes:clamp(.64*c.stripes+.36*t.stripeStrength),speckles:c.speckles,throatBlotch:c.throatBlotch,marginBand:c.marginBand,gradient:c.pigmentGradient,venation:clamp(.62*c.venationDensity+.38*t.veinContrast),patternScale:lerp(3,34,c.patternScale),
    stamenCount:Math.max(0,Math.round(lerp(2,70,c.stamenNumber)*lerp(.7,1.3,t.stamenCount/22))),stamenLength:lerp(.16,.68,c.stamenLength),antherSize:lerp(.012,.075,c.antherSize),filamentSpread:c.filamentSpread,styleLength:lerp(.12,.72,c.styleLength),stigmaSize:lerp(.012,.08,c.stigmaSize),pollenDisplay:c.pollenDisplay,centerOpenness:c.centerOpenness,
    cluster:c.solitaryCluster,composite:c.compositeDisk,branching:c.branching,clusterDensity:c.clusterDensity,pedicelLength:c.pedicelLength,bractSize:c.bractSize,leafBroadness:c.leafBroadness,leafLobing:c.leafLobing,
    heterochrony:c.heterochrony,noise:clamp(.62*c.developmentalNoise+.38*(t.developmentalNoise/.055)),asymmetry:clamp(.64*c.asymmetry+.36*(t.asymmetry/.06)),scale:lerp(.72,1.35,c.organScale)*t.petalScale,depth:clamp(.66*c.depth+.34*t.depth),phyllotaxis:c.phyllotaxis,stability:c.stability,plasticity:c.plasticity
  };
}

export function controlMetadata(key){const d=CONTROL_DEFS.find(x=>x.key===key);return d?{...d,...locusFor(d)}:null;}
