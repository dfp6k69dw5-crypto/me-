const TAU=Math.PI*2;
const clamp=(x,a=0,b=1)=>x<a?a:x>b?b:x;
const lerp=(a,b,t)=>a+(b-a)*t;
function rand(seed){let x=seed>>>0;x^=x<<13;x^=x>>>17;x^=x<<5;return(x>>>0)/4294967296;}
function mix(...xs){let h=2166136261;for(const x0 of xs){let x=x0>>>0;for(let k=0;k<4;k++){h^=(x>>>(k*8))&255;h=Math.imul(h,16777619)}}return(h^(h>>>16))>>>0;}
function smooth(x){x=clamp(x);return x*x*(3-2*x)}
function unitHash(genome,i,salt=0){return rand(mix(genome.geneHash[i%genome.geneHash.length],genome.digest,i,salt));}

const TYPES=['rose','lily','tulip','daisy','sunflower','orchid','iris','bell'];
// Familiar flowers are reference points, not templates. Every genome gets a
// continuous coordinate formed by blending all eight anchors, then dozens of
// extra loci perturb the result. This prevents the enormous sequence space from
// collapsing into eight canned drawings.
const ARCH={
  rose:{radial:.96,bilateral:.05,rays:.28,rings:.98,inner:.78,disk:.05,tube:.12,lip:.02,fall:.12,upright:.28,overlap:.96,stamen:.25},
  lily:{radial:.92,bilateral:.06,rays:.25,rings:.23,inner:.18,disk:.03,tube:.10,lip:.02,fall:.18,upright:.18,overlap:.38,stamen:.88},
  tulip:{radial:.95,bilateral:.04,rays:.23,rings:.30,inner:.30,disk:.02,tube:.62,lip:.01,fall:.10,upright:.82,overlap:.72,stamen:.55},
  daisy:{radial:1,bilateral:.01,rays:.94,rings:.08,inner:.03,disk:.72,tube:.02,lip:0,fall:.02,upright:.05,overlap:.12,stamen:.18},
  sunflower:{radial:1,bilateral:.01,rays:1,rings:.10,inner:.02,disk:1,tube:.03,lip:0,fall:.02,upright:.04,overlap:.10,stamen:.08},
  orchid:{radial:.24,bilateral:.98,rays:.16,rings:.18,inner:.38,disk:.04,tube:.08,lip:1,fall:.38,upright:.20,overlap:.42,stamen:.12},
  iris:{radial:.58,bilateral:.46,rays:.20,rings:.35,inner:.32,disk:.02,tube:.06,lip:.24,fall:.96,upright:.18,overlap:.36,stamen:.35},
  bell:{radial:.90,bilateral:.08,rays:.20,rings:.18,inner:.16,disk:.04,tube:1,lip:.02,fall:.12,upright:.88,overlap:.82,stamen:.50}
};

function architectureWeights(genome){
  const raw=[];let sum=0;
  for(let i=0;i<TYPES.length;i++){
    const a=unitHash(genome,3+i*3,0x101),b=unitHash(genome,11+i*5,0x202),c=unitHash(genome,19+i*7,0x303);
    const z=(a*.48+b*.32+c*.20);
    const w=Math.exp((z-.5)*4.2);raw.push(w);sum+=w;
  }
  return raw.map(v=>v/sum);
}
function morphProfile(genome){
  const w=architectureWeights(genome),p={};
  for(const key of Object.keys(ARCH.rose)){
    let v=0;for(let i=0;i<TYPES.length;i++)v+=w[i]*ARCH[TYPES[i]][key];p[key]=v;
  }
  const t=genome.traits;
  p.rays=clamp(p.rays*.72+(t.petalCount-4)/9*.28);
  p.rings=clamp(p.rings*.78+(t.whorls-1)*.22);
  p.bilateral=clamp(p.bilateral*.72+Math.abs(t.bilateral)*1.55+.10*unitHash(genome,6,0x44));
  p.overlap=clamp(p.overlap*.72+t.overlap*.28);
  p.fall=clamp(p.fall*.80+Math.abs(t.sideBias)*.55);
  p.upright=clamp(p.upright*.78+.22*(1-clamp(Math.abs(t.curlCue))));
  p.disk=clamp(p.disk*.82+t.centerDark*.18);
  p.stamen=clamp(p.stamen*.74+clamp(t.stamenCount/22)*.26);
  p.lip=clamp(p.lip*.84+p.bilateral*.11+unitHash(genome,23,0x55)*.05);
  p.tube=clamp(p.tube*.84+t.overlap*.08+unitHash(genome,25,0x66)*.08);
  p.petalLong=clamp(.28+.50*t.petalAspect+.22*unitHash(genome,4,0x71),.15,1.25);
  p.petalWide=clamp(1.18-.52*t.petalAspect+.18*unitHash(genome,8,0x72),.26,1.20);
  p.ripple=clamp(.08+.54*unitHash(genome,14,0x73)+.30*t.marginBoost,.01,.92);
  p.twist=clamp(.05+.60*unitHash(genome,18,0x74)+.25*Math.abs(t.curlCue),0,.96);
  p.depth=clamp(.18+.48*unitHash(genome,21,0x75)+.30*t.depth,.05,.95);
  p.centerScale=clamp(.08+.30*p.disk+.10*unitHash(genome,30,0x76),.05,.46);
  p.count=Math.max(3,Math.round(lerp(5,42,p.rays)*lerp(.82,1.18,unitHash(genome,7,0x77))));
  p.layers=Math.max(1,Math.round(lerp(1,8,p.rings)*lerp(.85,1.15,unitHash(genome,15,0x78))));
  p.innerScale=clamp(.18+.66*p.inner+.12*unitHash(genome,26,0x79),.12,.92);
  p.weights=w;
  return p;
}

export function classifyFlower(genome){
  const w=architectureWeights(genome);let best=0;for(let i=1;i<w.length;i++)if(w[i]>w[best])best=i;return TYPES[best];
}
export function describeFlower(genome){
  const w=architectureWeights(genome);const ids=w.map((v,i)=>[v,i]).sort((a,b)=>b[0]-a[0]);
  const a=TYPES[ids[0][1]],b=TYPES[ids[1][1]],ratio=ids[1][0]/Math.max(1e-9,ids[0][0]);
  return ratio>.68?`${a} × ${b}`:ratio>.42?`${a} / ${b}`:a;
}

function petal(ctx,p,cx,cy,R,a,sx=1,sy=1,depth=.5,seed=1,alpha=1,tilt=0){
  const img=p.petal.canvas,ax=p.petal.anchorX,ay=p.petal.anchorY,native=p.petal.tipSpan||Math.max(1,ay),s=R/native;
  ctx.save();ctx.translate(cx,cy);ctx.rotate(a);const shear=(rand(mix(seed,71))-.5)*.12+tilt*.10;ctx.transform(1,0,shear,1,0,0);ctx.scale(sx,sy);ctx.globalAlpha=alpha;
  ctx.shadowColor=`rgba(0,0,0,${.20+depth*.34})`;ctx.shadowBlur=R*(.035+.065*depth);ctx.shadowOffsetY=R*(.018+.025*depth);
  ctx.scale(s,s);ctx.drawImage(img,-ax,-ay);ctx.restore();
}
function stamens(ctx,cx,cy,R,t,seed,count,spread=1){
  ctx.save();ctx.translate(cx,cy);for(let i=0;i<count;i++){const q=rand(mix(seed,i,4)),a=i*TAU/count+(q-.5)*.23,len=R*t.stamenLength*(.58+.48*rand(mix(seed,i,7)))*spread;ctx.save();ctx.rotate(a);ctx.strokeStyle='rgba(236,213,151,.70)';ctx.lineWidth=Math.max(1,R*.0075);ctx.beginPath();ctx.moveTo(0,0);ctx.quadraticCurveTo(R*.025,-len*.45,0,-len);ctx.stroke();ctx.fillStyle='rgba(223,170,69,.94)';ctx.shadowColor='rgba(0,0,0,.38)';ctx.shadowBlur=3;ctx.beginPath();ctx.ellipse(0,-len,R*.025,R*.012,.25,0,TAU);ctx.fill();ctx.restore()}ctx.restore();
}
function disk(ctx,cx,cy,R,seed,strength){
  const radius=R*lerp(.08,.34,strength),g=ctx.createRadialGradient(cx-radius*.24,cy-radius*.28,0,cx,cy,radius);g.addColorStop(0,`rgba(144,104,43,${.72+.2*strength})`);g.addColorStop(.58,'rgba(80,57,28,.94)');g.addColorStop(1,'rgba(27,20,13,.98)');ctx.fillStyle=g;ctx.shadowColor='rgba(0,0,0,.5)';ctx.shadowBlur=R*.05;ctx.beginPath();ctx.arc(cx,cy,radius,0,TAU);ctx.fill();
  const n=Math.round(lerp(35,430,strength)),ga=Math.PI*(3-Math.sqrt(5));for(let i=0;i<n;i++){const r=radius*Math.sqrt(i/n)*.94,a=i*ga,rr=R*lerp(.004,.008,strength)*(0.72+rand(mix(seed,i))*0.55);ctx.fillStyle=i%4?'rgba(54,38,20,.83)':'rgba(167,123,48,.82)';ctx.beginPath();ctx.ellipse(cx+Math.cos(a)*r,cy+Math.sin(a)*r,rr,rr*.7,a,0,TAU);ctx.fill()}
}
function sepals(ctx,cx,cy,R,seed,n=5){ctx.save();ctx.translate(cx,cy);for(let i=0;i<n;i++){const a=i*TAU/n+.2;ctx.save();ctx.rotate(a);ctx.fillStyle='rgba(55,88,51,.55)';ctx.beginPath();ctx.moveTo(0,0);ctx.quadraticCurveTo(R*.08,-R*.22,R*.035,-R*.50);ctx.quadraticCurveTo(-R*.08,-R*.24,0,0);ctx.fill();ctx.restore()}ctx.restore()}

function drawMorph(ctx,p,cx,cy,R,m,seed){
  const t=p.genome.traits;
  sepals(ctx,cx,cy,R,seed,Math.round(lerp(4,7,unitHash(p.genome,29,0x81))));
  const bilateral=m.bilateral;
  const layers=m.layers;
  for(let l=0;l<layers;l++){
    const q=layers===1?0:l/(layers-1),inner=Math.pow(1-q,lerp(.55,1.7,m.inner)),ringR=R*lerp(m.innerScale,1,inner),baseN=Math.max(3,Math.round(m.count*lerp(.52,1,q))),offset=(l&1)*Math.PI/baseN;
    for(let i=0;i<baseN;i++){
      let a=i*TAU/baseN+offset;
      const axis=Math.cos(a),side=Math.sin(a);
      const bilateralSuppress=lerp(1,Math.pow(Math.abs(axis),.42),bilateral*.78);
      if(rand(mix(seed,l,i,0x99))>bilateralSuppress*.92+.08)continue;
      const jitter=(rand(mix(seed,l,i,0x91))-.5)*lerp(.025,.20,t.radialJitter/.075);
      a+=jitter;
      const front=(Math.sin(a)+1)*.5;
      const lower=Math.max(0,Math.sin(a));
      const upper=Math.max(0,-Math.sin(a));
      let sx=m.petalWide*lerp(.72,1.22,rand(mix(seed,l,i,0x92)));
      let sy=m.petalLong*lerp(.88,1.18,rand(mix(seed,l,i,0x93)));
      sx*=lerp(1,.72,q*m.overlap);sy*=lerp(1,.80,q*m.overlap);
      sy*=1+m.fall*lower*.30-m.upright*upper*.12;
      sx*=1+bilateral*Math.abs(side)*.20;
      const ripple=(rand(mix(seed,l,i,0x94))-.5)*m.ripple;
      const twist=(rand(mix(seed,l,i,0x95))-.5)*m.twist;
      const alpha=clamp(.87+.12*front-.05*q,.72,1);
      petal(ctx,p,cx,cy,ringR,a,sx,sy,front*m.depth+q*.25,seed+l*1000+i,alpha,ripple+twist);
    }
  }
  if(m.lip>.18){
    const strength=smooth((m.lip-.18)/.82),lipR=R*lerp(.42,.70,strength);
    petal(ctx,p,cx,cy+R*.018,lipR,Math.PI/2,lerp(.9,1.55,strength),lerp(.58,.84,strength),.92,seed+0x771,1,.12);
  }
  if(m.tube>.22){const s=smooth((m.tube-.22)/.78),rx=R*lerp(.10,.30,s),ry=R*lerp(.07,.22,s),g=ctx.createRadialGradient(cx-R*.05,cy-R*.04,0,cx,cy,rx);g.addColorStop(0,`rgba(255,245,230,${.08+.12*s})`);g.addColorStop(.65,`rgba(32,20,25,${.10+.18*s})`);g.addColorStop(1,'rgba(10,8,12,.42)');ctx.fillStyle=g;ctx.beginPath();ctx.ellipse(cx,cy,rx,ry,0,0,TAU);ctx.fill()}
  if(m.disk>.10)disk(ctx,cx,cy,R,seed,m.disk);
  const st=Math.max(0,Math.round(lerp(0,t.stamenCount,m.stamen)));if(st>0)stamens(ctx,cx,cy,R,t,seed,st,lerp(.72,1.04,1-m.tube));
}

export function drawPhotorealFlower(ctx,p,{width,height,dpr=1}={}){
  const W=width||innerWidth,H=height||innerHeight,t=p.genome.traits,seed=p.genome.digest,m=morphProfile(p.genome);
  const usableH=Math.max(260,H-122),cx=W*.5,cy=Math.min(H*.47,usableH*.5+35),R=Math.min(W*.46,usableH*.43)*clamp(t.petalScale,.78,1.28);
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.fillStyle='#090b0d';ctx.fillRect(0,0,W,H);
  const bg=ctx.createRadialGradient(W*.46,H*.34,0,W*.5,H*.52,Math.max(W,H)*.8);bg.addColorStop(0,'#2a3030');bg.addColorStop(.34,'#151a1b');bg.addColorStop(1,'#050708');ctx.fillStyle=bg;ctx.fillRect(0,0,W,H);
  ctx.globalAlpha=.04;for(let i=0;i<170;i++){const x=rand(mix(seed,i,1))*W,y=rand(mix(seed,i,2))*H,r=.35+rand(mix(seed,i,3))*1.25;ctx.fillStyle=i&1?'#fff':'#000';ctx.beginPath();ctx.arc(x,y,r,0,TAU);ctx.fill()}ctx.globalAlpha=1;
  ctx.save();ctx.translate(0,R*.015);drawMorph(ctx,p,cx,cy,R,m,seed);ctx.restore();
  const vg=ctx.createRadialGradient(cx,cy,Math.min(W,H)*.24,cx,cy,Math.max(W,H)*.74);vg.addColorStop(0,'rgba(0,0,0,0)');vg.addColorStop(1,'rgba(0,0,0,.64)');ctx.fillStyle=vg;ctx.fillRect(0,0,W,H);
  return describeFlower(p.genome);
}
