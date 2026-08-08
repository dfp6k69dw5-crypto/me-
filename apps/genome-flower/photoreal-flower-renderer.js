const TAU=Math.PI*2;
const clamp=(x,a=0,b=1)=>x<a?a:x>b?b:x;
function rand(seed){let x=seed>>>0;x^=x<<13;x^=x>>>17;x^=x<<5;return(x>>>0)/4294967296;}
function mix(...xs){let h=2166136261;for(const x0 of xs){let x=x0>>>0;for(let k=0;k<4;k++){h^=(x>>>(k*8))&255;h=Math.imul(h,16777619)}}return(h^(h>>>16))>>>0;}

export function classifyFlower(genome){
  const t=genome.traits;
  const scores={
    rose:(t.whorls-1)*3.0+t.overlap*2.4+(1-t.petalAspect)*.7+t.petalCount*.05,
    lily:(1-Math.abs(t.petalCount-6)/8)*1.5+(t.petalAspect>.98?1.0:.25)+t.stamenLength*1.8+(1-t.overlap)*.7,
    tulip:(1-Math.abs(t.petalCount-6)/8)*1.7+(1-t.petalAspect)*1.2+t.overlap*1.4+(1-t.stamenLength)*.45,
    daisy:t.petalCount*.11+(1-t.centerDark)*.5+(1-t.overlap)*.55,
    sunflower:t.petalCount*.10+t.centerDark*1.45+t.spotStrength*.65+t.stamenCount*.025,
    orchid:Math.abs(t.bilateral)*5.0+t.asymmetry*10+(1-Math.abs(t.petalCount-5)/9)*.75+t.sheen*.5,
    iris:Math.abs(t.sideBias)*2.2+Math.abs(t.curlCue)*1.1+t.veinContrast*1.5+(1-Math.abs(t.petalCount-6)/8)*.55,
    bell:t.overlap*1.5+(1-t.petalAspect)*.95+(1-t.stamenLength)*.55+(t.petalCount<7?.55:0)
  };
  let best='daisy',v=-Infinity;for(const [k,s] of Object.entries(scores))if(s>v){v=s;best=k;}
  // A slow-changing genomic tie breaker keeps nearby phenotypes related while
  // allowing regulatory mutations to cross between architectures.
  const second=Object.entries(scores).sort((a,b)=>b[1]-a[1])[1];
  if(second&&Math.abs(v-second[1])<.12){const code=(genome.geneHash[3]^genome.geneHash[11]^genome.geneHash[19])>>>0;if((code&3)===0)best=second[0];}
  return best;
}

function petal(ctx,p,cx,cy,R,a,sx=1,sy=1,depth=.5,seed=1,flip=false,alpha=1){
  const img=p.petal.canvas,ax=p.petal.anchorX,ay=p.petal.anchorY,native=p.petal.tipSpan||Math.max(1,ay),s=R/native;
  ctx.save();ctx.translate(cx,cy);ctx.rotate(a);const shear=(rand(mix(seed,71))-.5)*.11;ctx.transform(flip?-1:1,0,shear,1,0,0);ctx.scale(sx,sy);ctx.globalAlpha=alpha;
  ctx.shadowColor=`rgba(0,0,0,${.24+depth*.28})`;ctx.shadowBlur=R*(.045+.05*depth);ctx.shadowOffsetY=R*.026;
  ctx.scale(s,s);ctx.drawImage(img,-ax,-ay);ctx.restore();
}
function petalTint(ctx,p,cx,cy,R,a,sx,sy,color,alpha=.16){
  const img=p.petal.canvas,ax=p.petal.anchorX,ay=p.petal.anchorY,native=p.petal.tipSpan||Math.max(1,ay),s=R/native;
  ctx.save();ctx.translate(cx,cy);ctx.rotate(a);ctx.scale(sx,sy);ctx.scale(s,s);ctx.globalCompositeOperation='source-atop';ctx.globalAlpha=alpha;ctx.fillStyle=color;ctx.drawImage(img,-ax,-ay);ctx.fillRect(-ax,-ay,img.width,img.height);ctx.restore();
}
function stamens(ctx,cx,cy,R,t,seed,count=t.stamenCount,spread=.54){
  ctx.save();ctx.translate(cx,cy);
  for(let i=0;i<count;i++){const a=i*TAU/count+(rand(mix(seed,i,4))-.5)*.18,len=R*t.stamenLength*(.78+.26*rand(mix(seed,i,7)));ctx.save();ctx.rotate(a);ctx.strokeStyle='rgba(235,211,146,.72)';ctx.lineWidth=Math.max(1,R*.009);ctx.beginPath();ctx.moveTo(0,0);ctx.quadraticCurveTo(R*.04,-len*.45,Math.sin(i)*R*.015,-len);ctx.stroke();ctx.fillStyle='rgba(224,171,70,.96)';ctx.shadowColor='rgba(0,0,0,.35)';ctx.shadowBlur=3;ctx.beginPath();ctx.ellipse(0,-len,R*.03,R*.014,.25,0,TAU);ctx.fill();ctx.restore();}
  ctx.restore();
}
function disk(ctx,cx,cy,R,seed,sun=false){
  const radius=R*(sun?.31:.24);const g=ctx.createRadialGradient(cx-radius*.3,cy-radius*.35,0,cx,cy,radius);g.addColorStop(0,sun?'#6f5226':'#d5b34f');g.addColorStop(.55,sun?'#4b351d':'#b89536');g.addColorStop(1,'#241b12');ctx.fillStyle=g;ctx.shadowColor='rgba(0,0,0,.45)';ctx.shadowBlur=R*.05;ctx.beginPath();ctx.arc(cx,cy,radius,0,TAU);ctx.fill();
  const n=sun?420:190,ga=Math.PI*(3-Math.sqrt(5));for(let i=0;i<n;i++){const r=radius*Math.sqrt(i/n)*.93,a=i*ga,rr=R*(sun?.008:.006)*(0.7+rand(mix(seed,i))*0.6);ctx.fillStyle=sun?(i%3?'rgba(32,23,13,.82)':'rgba(125,91,39,.82)'):(i%3?'rgba(107,74,27,.78)':'rgba(230,191,71,.72)');ctx.beginPath();ctx.ellipse(cx+Math.cos(a)*r,cy+Math.sin(a)*r,rr,rr*.72,a,0,TAU);ctx.fill();}
}
function rose(ctx,p,cx,cy,R,t,seed){
  const layers=5+(t.whorls-1)*2;for(let l=0;l<layers;l++){const q=l/(layers-1),n=Math.round(7+q*3),r=R*(1-q*.68),offset=(l&1)*Math.PI/n;for(let i=0;i<n;i++){const a=i*TAU/n+offset+(rand(mix(seed,l,i))-.5)*.08;petal(ctx,p,cx,cy,r,a,1.08-q*.22,.94-q*.05,q,seed+l*100+i,false,.96);}}
  const g=ctx.createRadialGradient(cx-R*.04,cy-R*.04,0,cx,cy,R*.15);g.addColorStop(0,'rgba(255,234,205,.36)');g.addColorStop(1,'rgba(70,30,20,.34)');ctx.fillStyle=g;ctx.beginPath();ctx.arc(cx,cy,R*.13,0,TAU);ctx.fill();
}
function lily(ctx,p,cx,cy,R,t,seed){
  for(let i=0;i<3;i++)petal(ctx,p,cx,cy,R*1.02,i*TAU/3,1.05,1.12,.25,seed+i);
  for(let i=0;i<3;i++)petal(ctx,p,cx,cy,R*.92,i*TAU/3+Math.PI/3,.86,1.04,.58,seed+20+i);
  stamens(ctx,cx,cy,R,t,seed,6,.6);
}
function tulip(ctx,p,cx,cy,R,t,seed){
  for(let i=0;i<3;i++)petal(ctx,p,cx,cy,R*.93,i*TAU/3+.08,1.28,.98,.32,seed+i,false,.94);
  for(let i=0;i<3;i++)petal(ctx,p,cx,cy,R*.82,i*TAU/3+Math.PI/3,1.12,.92,.7,seed+30+i,false,.98);
  const g=ctx.createRadialGradient(cx,cy,0,cx,cy,R*.22);g.addColorStop(0,'rgba(28,19,10,.45)');g.addColorStop(1,'rgba(28,19,10,0)');ctx.fillStyle=g;ctx.beginPath();ctx.arc(cx,cy,R*.22,0,TAU);ctx.fill();
}
function daisy(ctx,p,cx,cy,R,t,seed,sun=false){
  const n=sun?34:Math.max(18,Math.round(22+t.petalCount*1.2));for(let i=0;i<n;i++){const a=i*TAU/n+(rand(mix(seed,i))-.5)*.035;petal(ctx,p,cx,cy,R*(sun?.72:.82),a,sun?.42:.32,1.0,.35,seed+i,false,.96);}disk(ctx,cx,cy,R,seed,sun);
}
function orchid(ctx,p,cx,cy,R,t,seed){
  petal(ctx,p,cx,cy,R*.96,-Math.PI/2,1.05,1.02,.2,seed+1);petal(ctx,p,cx,cy,R*.88,Math.PI/6,.78,.95,.34,seed+2);petal(ctx,p,cx,cy,R*.88,5*Math.PI/6,.78,.95,.34,seed+3);petal(ctx,p,cx,cy,R*.72,-Math.PI/6,.58,.82,.55,seed+4);petal(ctx,p,cx,cy,R*.72,7*Math.PI/6,.58,.82,.55,seed+5);
  petal(ctx,p,cx,cy+R*.025,R*.63,Math.PI/2,1.42,.78,.88,seed+6,false,1);petalTint(ctx,p,cx,cy+R*.025,R*.63,Math.PI/2,1.42,.78,'rgba(255,235,210,1)',.18);
  ctx.fillStyle='rgba(238,215,166,.92)';ctx.shadowColor='rgba(0,0,0,.4)';ctx.shadowBlur=5;ctx.beginPath();ctx.ellipse(cx,cy-R*.015,R*.055,R*.12,0,0,TAU);ctx.fill();
}
function iris(ctx,p,cx,cy,R,t,seed){
  for(let i=0;i<3;i++){const a=i*TAU/3;petal(ctx,p,cx,cy,R*.93,a,1.0,.82,.25,seed+i);}
  for(let i=0;i<3;i++){const a=i*TAU/3+Math.PI/3;petal(ctx,p,cx,cy,R*.78,a,.8,.94,.72,seed+20+i);}
  ctx.strokeStyle='rgba(241,195,66,.75)';ctx.lineWidth=Math.max(1,R*.02);for(let i=0;i<3;i++){const a=i*TAU/3+Math.PI/3;ctx.beginPath();ctx.moveTo(cx,cy);ctx.lineTo(cx+Math.cos(a)*R*.42,cy+Math.sin(a)*R*.42);ctx.stroke();}
}
function bell(ctx,p,cx,cy,R,t,seed){
  const n=5;for(let i=0;i<n;i++){const a=i*TAU/n;petal(ctx,p,cx,cy,R*.72,a,1.15,.82,.45,seed+i,false,.91);}const g=ctx.createRadialGradient(cx-R*.08,cy-R*.08,R*.02,cx,cy,R*.34);g.addColorStop(0,'rgba(255,255,255,.18)');g.addColorStop(.6,'rgba(30,20,30,.18)');g.addColorStop(1,'rgba(10,8,12,.5)');ctx.fillStyle=g;ctx.beginPath();ctx.ellipse(cx,cy,R*.28,R*.20,0,0,TAU);ctx.fill();stamens(ctx,cx,cy,R*.72,t,seed,5,.35);
}

export function drawPhotorealFlower(ctx,p,{width,height,dpr=1}={}){
  const W=width||innerWidth,H=height||innerHeight,t=p.genome.traits,seed=p.genome.digest,type=classifyFlower(p.genome);
  const usableH=Math.max(260,H-122),cx=W*.5,cy=Math.min(H*.47,usableH*.5+35),R=Math.min(W*.46,usableH*.43)*clamp(t.petalScale,.78,1.28);
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.fillStyle='#090b0d';ctx.fillRect(0,0,W,H);
  const bg=ctx.createRadialGradient(W*.48,H*.38,0,W*.5,H*.52,Math.max(W,H)*.78);bg.addColorStop(0,'#252b2d');bg.addColorStop(.36,'#121719');bg.addColorStop(1,'#050708');ctx.fillStyle=bg;ctx.fillRect(0,0,W,H);
  // faint photographic grain
  ctx.globalAlpha=.045;for(let i=0;i<140;i++){const x=rand(mix(seed,i,1))*W,y=rand(mix(seed,i,2))*H,r=.4+rand(mix(seed,i,3))*1.4;ctx.fillStyle=i&1?'#fff':'#000';ctx.beginPath();ctx.arc(x,y,r,0,TAU);ctx.fill();}ctx.globalAlpha=1;
  ctx.save();ctx.translate(0,R*.015);
  if(type==='rose')rose(ctx,p,cx,cy,R,t,seed);else if(type==='lily')lily(ctx,p,cx,cy,R,t,seed);else if(type==='tulip')tulip(ctx,p,cx,cy,R,t,seed);else if(type==='sunflower')daisy(ctx,p,cx,cy,R,t,seed,true);else if(type==='orchid')orchid(ctx,p,cx,cy,R,t,seed);else if(type==='iris')iris(ctx,p,cx,cy,R,t,seed);else if(type==='bell')bell(ctx,p,cx,cy,R,t,seed);else daisy(ctx,p,cx,cy,R,t,seed,false);
  ctx.restore();
  const vg=ctx.createRadialGradient(cx,cy,Math.min(W,H)*.25,cx,cy,Math.max(W,H)*.73);vg.addColorStop(0,'rgba(0,0,0,0)');vg.addColorStop(1,'rgba(0,0,0,.62)');ctx.fillStyle=vg;ctx.fillRect(0,0,W,H);
  return type;
}
