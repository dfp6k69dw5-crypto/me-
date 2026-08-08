import {derivePhenotype} from './genetic-control-engine.js';

const TAU=Math.PI*2;
const clamp=(x,a=0,b=1)=>x<a?a:x>b?b:x;
const lerp=(a,b,t)=>a+(b-a)*t;
const smooth=x=>{x=clamp(x);return x*x*(3-2*x)};
function mix(...xs){let h=2166136261;for(const x0 of xs){let x=x0>>>0;for(let k=0;k<4;k++){h^=(x>>>(k*8))&255;h=Math.imul(h,16777619)}}return(h^(h>>>16))>>>0;}
function rand(seed){let x=seed>>>0;x^=x<<13;x^=x>>>17;x^=x<<5;return(x>>>0)/4294967296;}
function unitHash(genome,i,salt=0){return rand(mix(genome.geneHash[i%genome.geneHash.length],genome.digest,i,salt));}

const TYPES=['rose','peony','lily','tulip','poppy','magnolia','daisy','sunflower','dahlia','zinnia','orchid','iris','bell','snapdragon','hibiscus','narcissus'];
const ARCH={
 rose:{radial:.98,rays:.20,rings:1,inner:.92,disk:.01,tube:.06,lip:.01,fall:.08,upright:.28,overlap:.98,stamen:.12,cluster:.08},
 peony:{radial:.97,rays:.25,rings:.94,inner:.82,disk:.03,tube:.03,lip:.01,fall:.12,upright:.20,overlap:.92,stamen:.30,cluster:.08},
 lily:{radial:.94,rays:.24,rings:.15,inner:.10,disk:.01,tube:.05,lip:.01,fall:.22,upright:.12,overlap:.28,stamen:.95,cluster:.12},
 tulip:{radial:.97,rays:.18,rings:.20,inner:.18,disk:.01,tube:.70,lip:.01,fall:.04,upright:.92,overlap:.78,stamen:.56,cluster:.10},
 poppy:{radial:.98,rays:.27,rings:.12,inner:.08,disk:.12,tube:.05,lip:.01,fall:.04,upright:.50,overlap:.44,stamen:.92,cluster:.10},
 magnolia:{radial:.98,rays:.22,rings:.24,inner:.20,disk:.03,tube:.25,lip:.01,fall:.05,upright:.74,overlap:.62,stamen:.54,cluster:.05},
 daisy:{radial:1,rays:.98,rings:.05,inner:.02,disk:.74,tube:.01,lip:0,fall:.01,upright:.04,overlap:.08,stamen:.06,cluster:.20},
 sunflower:{radial:1,rays:1,rings:.06,inner:.01,disk:1,tube:.01,lip:0,fall:.01,upright:.02,overlap:.05,stamen:.03,cluster:.12},
 dahlia:{radial:1,rays:.84,rings:.86,inner:.62,disk:.08,tube:.16,lip:0,fall:.04,upright:.18,overlap:.76,stamen:.08,cluster:.10},
 zinnia:{radial:1,rays:.82,rings:.52,inner:.32,disk:.28,tube:.10,lip:0,fall:.04,upright:.16,overlap:.48,stamen:.10,cluster:.12},
 orchid:{radial:.20,rays:.13,rings:.12,inner:.26,disk:.02,tube:.05,lip:1,fall:.42,upright:.22,overlap:.36,stamen:.08,cluster:.10},
 iris:{radial:.48,rays:.16,rings:.24,inner:.24,disk:.01,tube:.03,lip:.26,fall:1,upright:.20,overlap:.30,stamen:.20,cluster:.08},
 bell:{radial:.92,rays:.14,rings:.10,inner:.08,disk:.02,tube:1,lip:.02,fall:.05,upright:.96,overlap:.86,stamen:.46,cluster:.16},
 snapdragon:{radial:.12,rays:.10,rings:.12,inner:.18,disk:.01,tube:.68,lip:.88,fall:.24,upright:.58,overlap:.64,stamen:.16,cluster:.72},
 hibiscus:{radial:.96,rays:.26,rings:.10,inner:.06,disk:.03,tube:.10,lip:.01,fall:.05,upright:.38,overlap:.34,stamen:1,cluster:.08},
 narcissus:{radial:.97,rays:.24,rings:.10,inner:.06,disk:.02,tube:.74,lip:.02,fall:.05,upright:.54,overlap:.26,stamen:.52,cluster:.16}
};

function architectureWeights(genome){
 const raw=[];let sum=0;
 for(let i=0;i<TYPES.length;i++){
   const a=unitHash(genome,2+i*5,0x991),b=unitHash(genome,7+i*7,0x551),c=unitHash(genome,13+i*11,0x331);
   const z=.48*a+.31*b+.21*c,w=Math.exp((z-.5)*4.5);raw.push(w);sum+=w;
 }
 return raw.map(x=>x/sum);
}
function morphProfile(genome,gx){
 const w=architectureWeights(genome),m={};
 for(const key of Object.keys(ARCH.rose)){let v=0;for(let i=0;i<TYPES.length;i++)v+=w[i]*ARCH[TYPES[i]][key];m[key]=v;}
 m.radial=clamp(m.radial*(1-gx.bilateral*.65));m.rays=clamp(.64*m.rays+.36*clamp((gx.petalCount-3)/40));
 m.rings=clamp(.55*m.rings+.45*clamp((gx.whorls-1)/7));m.tube=clamp(.45*m.tube+.55*gx.tube);m.lip=clamp(.45*m.lip+.55*gx.lip);m.overlap=clamp(.52*m.overlap+.48*gx.overlap);
 m.fall=clamp(.56*m.fall+.22*clamp(gx.reflex)+.22*gx.bilateral);m.upright=clamp(.6*m.upright+.4*clamp(.5+gx.cup*.45));m.stamen=clamp(.55*m.stamen+.45*gx.centerOpenness);m.cluster=clamp(.45*m.cluster+.55*gx.cluster);
 m.petalLong=clamp(.38+.58*gx.aspect,.32,1.72);m.petalWide=clamp(1.28-.33*gx.aspect,.35,1.2);m.ripple=clamp(.08+.70*gx.ruffle+.12*gx.serration);m.twist=clamp(Math.abs(gx.twist));m.depth=clamp(.20+.75*gx.depth);
 m.count=Math.max(3,Math.min(64,Math.round(lerp(5,gx.petalCount,m.rays))));m.layers=Math.max(1,Math.min(9,Math.round(lerp(1,gx.whorls,m.rings))));m.innerScale=clamp(.12+.68*m.inner,.10,.88);m.weights=w;return m;
}

export function classifyFlower(genome){const w=architectureWeights(genome);let best=0;for(let i=1;i<w.length;i++)if(w[i]>w[best])best=i;return TYPES[best];}
export function describeFlower(genome){const w=architectureWeights(genome),ids=w.map((v,i)=>[v,i]).sort((a,b)=>b[0]-a[0]),a=TYPES[ids[0][1]],b=TYPES[ids[1][1]],r=ids[1][0]/Math.max(1e-9,ids[0][0]);return r>.72?`${a} × ${b}`:r>.46?`${a} / ${b}`:a;}

function drawBokeh(ctx,W,H,seed){
 const g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,'#263b2e');g.addColorStop(.52,'#14241c');g.addColorStop(1,'#0a110e');ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
 for(let i=0;i<54;i++){const x=rand(mix(seed,i,1))*W,y=rand(mix(seed,i,2))*H*.92,r=lerp(8,62,Math.pow(rand(mix(seed,i,3)),1.8)),q=rand(mix(seed,i,4));ctx.fillStyle=q>.76?`rgba(244,233,187,${.018+.055*q})`:`rgba(${35+(q*25|0)},${82+(q*65|0)},${49+(q*34|0)},${.025+.09*q})`;ctx.beginPath();ctx.arc(x,y,r,0,TAU);ctx.fill();}
 const sun=ctx.createRadialGradient(W*.24,H*.08,0,W*.24,H*.08,Math.max(W,H)*.7);sun.addColorStop(0,'rgba(255,246,220,.13)');sun.addColorStop(.35,'rgba(255,245,220,.035)');sun.addColorStop(1,'rgba(0,0,0,0)');ctx.fillStyle=sun;ctx.fillRect(0,0,W,H);
}
function leaf(ctx,x,y,L,a,broad,lobing,alpha=.55){ctx.save();ctx.translate(x,y);ctx.rotate(a);ctx.globalAlpha=alpha;const g=ctx.createLinearGradient(0,0,L,0);g.addColorStop(0,'#163522');g.addColorStop(.55,'#2f6540');g.addColorStop(1,'#183824');ctx.fillStyle=g;ctx.beginPath();ctx.moveTo(0,0);for(let i=1;i<=8;i++){const u=i/8,w=Math.sin(Math.PI*u)*L*(.12+.12*broad)*(1-.25*lobing*Math.sin(i*Math.PI));ctx.lineTo(u*L,-w);}ctx.lineTo(L,0);for(let i=7;i>=1;i--){const u=i/8,w=Math.sin(Math.PI*u)*L*(.12+.12*broad)*(1-.25*lobing*Math.sin(i*Math.PI));ctx.lineTo(u*L,w);}ctx.closePath();ctx.fill();ctx.strokeStyle='rgba(175,215,170,.16)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(L,0);ctx.stroke();ctx.restore();}
function supportPlant(ctx,W,H,cx,cy,R,gx,seed){
 const stemX=cx+R*(rand(mix(seed,70))-.5)*.12;ctx.save();ctx.strokeStyle='rgba(61,111,70,.78)';ctx.lineWidth=Math.max(3,R*.022);ctx.lineCap='round';ctx.beginPath();ctx.moveTo(stemX,H+10);ctx.bezierCurveTo(stemX-R*.12,H*.76,stemX+R*.08,cy+R*.52,cx,cy+R*.10);ctx.stroke();ctx.restore();
 const n=4+Math.round(gx.branching*4);for(let i=0;i<n;i++){const y=lerp(H*.94,cy+R*.46,i/Math.max(1,n-1)),side=i%2?-1:1,x=stemX+side*R*.04;leaf(ctx,x,y,R*lerp(.34,.62,rand(mix(seed,i,74))),side*lerp(.25,.72,rand(mix(seed,i,75)))-Math.PI*(side<0?1:0),gx.leafBroadness,gx.leafLobing,.34+.25*rand(mix(seed,i,76)));}
}
function petal(ctx,p,cx,cy,R,a,sx,sy,depth,seed,alpha=1,tilt=0){
 const img=p.petal.canvas,ax=p.petal.anchorX,ay=p.petal.anchorY,native=p.petal.tipSpan||Math.max(1,ay),s=R/native;
 ctx.save();ctx.translate(cx,cy);ctx.rotate(a);const shear=(rand(mix(seed,71))-.5)*.10+tilt*.12;ctx.transform(1,0,shear,1,0,0);ctx.scale(sx,sy);ctx.globalAlpha=alpha;ctx.shadowColor=`rgba(0,0,0,${.18+depth*.34})`;ctx.shadowBlur=R*(.025+.065*depth);ctx.shadowOffsetY=R*(.012+.025*depth);ctx.scale(s,s);ctx.drawImage(img,-ax,-ay);ctx.restore();
 if(depth>.32){ctx.save();ctx.translate(cx,cy);ctx.rotate(a);ctx.globalCompositeOperation='screen';ctx.globalAlpha=.025+.055*depth;ctx.scale(sx*s*1.006,sy*s*1.006);ctx.drawImage(img,-ax,-ay);ctx.restore();}
}
function sepals(ctx,cx,cy,R,seed,gx){ctx.save();ctx.translate(cx,cy);const n=4+Math.round(gx.bractSize*4);for(let i=0;i<n;i++){ctx.save();ctx.rotate(i*TAU/n+.17);ctx.fillStyle='rgba(49,92,54,.52)';ctx.beginPath();ctx.moveTo(0,0);ctx.quadraticCurveTo(R*.10,-R*.21,R*.04,-R*lerp(.28,.60,gx.bractSize));ctx.quadraticCurveTo(-R*.09,-R*.24,0,0);ctx.fill();ctx.restore()}ctx.restore();}
function stamens(ctx,cx,cy,R,gx,seed,count,spread=1){ctx.save();ctx.translate(cx,cy);for(let i=0;i<count;i++){const q=rand(mix(seed,i,4)),a=i*TAU/count+(q-.5)*lerp(.08,.48,gx.filamentSpread),len=R*gx.stamenLength*(.70+.48*rand(mix(seed,i,7)))*spread;ctx.save();ctx.rotate(a);ctx.strokeStyle=`rgba(239,218,164,${.46+.42*gx.pollenDisplay})`;ctx.lineWidth=Math.max(.7,R*.0055);ctx.beginPath();ctx.moveTo(0,0);ctx.quadraticCurveTo(R*.018,-len*.45,0,-len);ctx.stroke();ctx.fillStyle=`rgba(211,148,43,${.62+.34*gx.pollenDisplay})`;ctx.shadowColor='rgba(0,0,0,.30)';ctx.shadowBlur=2;ctx.beginPath();ctx.ellipse(0,-len,R*gx.antherSize,R*gx.antherSize*.45,.25,0,TAU);ctx.fill();ctx.restore()}ctx.restore();}
function style(ctx,cx,cy,R,gx){ctx.save();ctx.translate(cx,cy);ctx.strokeStyle='rgba(224,220,174,.82)';ctx.lineWidth=Math.max(1,R*.009);ctx.beginPath();ctx.moveTo(0,R*.03);ctx.quadraticCurveTo(R*.02,-R*gx.styleLength*.48,0,-R*gx.styleLength);ctx.stroke();ctx.fillStyle='rgba(202,205,145,.9)';ctx.beginPath();ctx.arc(0,-R*gx.styleLength,R*gx.stigmaSize,0,TAU);ctx.fill();ctx.restore();}
function disk(ctx,cx,cy,R,seed,strength,gx){const radius=R*lerp(.07,.34,strength),g=ctx.createRadialGradient(cx-radius*.22,cy-radius*.25,0,cx,cy,radius);g.addColorStop(0,'rgba(172,130,53,.94)');g.addColorStop(.52,'rgba(81,55,26,.98)');g.addColorStop(1,'rgba(28,20,14,.99)');ctx.fillStyle=g;ctx.beginPath();ctx.arc(cx,cy,radius,0,TAU);ctx.fill();const n=Math.round(lerp(45,520,strength)),ga=Math.PI*(3-Math.sqrt(5));for(let i=0;i<n;i++){const r=radius*Math.sqrt(i/n)*.95,a=i*ga,rr=R*lerp(.003,.0075,strength);ctx.fillStyle=i%5?'rgba(55,37,19,.78)':`rgba(205,153,53,${.55+.3*gx.pollenDisplay})`;ctx.beginPath();ctx.ellipse(cx+Math.cos(a)*r,cy+Math.sin(a)*r,rr,rr*.72,a,0,TAU);ctx.fill();}}

function drawHead(ctx,p,cx,cy,R,m,gx,seed,scale=1){
 R*=scale;sepals(ctx,cx,cy,R,seed,gx);
 const items=[];
 for(let l=0;l<m.layers;l++){
  const q=m.layers===1?0:l/(m.layers-1),inner=Math.pow(1-q,lerp(.58,1.55,m.inner)),ringR=R*lerp(m.innerScale,1,inner),baseN=Math.max(3,Math.round(m.count*lerp(.48,1,q))),offset=(l&1)*Math.PI/baseN;
  for(let i=0;i<baseN;i++){
   let a=i*TAU/baseN+offset+(gx.phyllotaxis-.5)*.18*q;const axis=Math.cos(a),side=Math.sin(a);const keep=lerp(1,Math.pow(Math.abs(axis),.38),gx.bilateral*.82);if(rand(mix(seed,l,i,0x99))>keep*.92+.08)continue;
   a+=(rand(mix(seed,l,i,0x91))-.5)*lerp(.01,.18,gx.noise);const front=(Math.sin(a)+1)*.5,lower=Math.max(0,Math.sin(a)),upper=Math.max(0,-Math.sin(a));let sx=m.petalWide*lerp(.82,1.18,rand(mix(seed,l,i,0x92))),sy=m.petalLong*lerp(.88,1.14,rand(mix(seed,l,i,0x93)));sx*=lerp(1,.72,q*m.overlap);sy*=lerp(1,.82,q*m.overlap);sy*=1+m.fall*lower*.30-m.upright*upper*.10;sx*=1+gx.bilateral*Math.abs(side)*.18;const tilt=(rand(mix(seed,l,i,0x94))-.5)*m.ripple+(rand(mix(seed,l,i,0x95))-.5)*m.twist+gx.twist*.10;items.push({a,sx,sy,ringR,front,q,tilt,id:l*100+i});
  }
 }
 items.sort((A,B)=>(A.front+A.q*.18)-(B.front+B.q*.18));
 for(const z of items)petal(ctx,p,cx,cy,z.ringR,z.a,z.sx,z.sy,z.front*m.depth+z.q*.20,seed+z.id,clamp(.84+.14*z.front-.04*z.q),z.tilt);
 if(m.lip>.20){const s=smooth((m.lip-.20)/.8);petal(ctx,p,cx,cy+R*.025,R*lerp(.38,.67,s),Math.PI/2,lerp(.95,1.62,s),lerp(.55,.88,s),.94,seed+0x771,1,.14);}
 if(m.tube>.22){const s=smooth((m.tube-.22)/.78),rx=R*lerp(.07,.30,s),ry=R*lerp(.05,.20,s),g=ctx.createRadialGradient(cx-R*.04,cy-R*.05,0,cx,cy,rx);g.addColorStop(0,`rgba(250,242,220,${.05+.09*s})`);g.addColorStop(.66,`rgba(45,25,26,${.08+.18*s})`);g.addColorStop(1,'rgba(13,9,10,.46)');ctx.fillStyle=g;ctx.beginPath();ctx.ellipse(cx,cy,rx,ry,0,0,TAU);ctx.fill();}
 const diskStrength=clamp(.58*m.disk+.42*gx.composite);if(diskStrength>.12)disk(ctx,cx,cy,R,seed,diskStrength,gx);
 const st=Math.max(0,Math.min(90,Math.round(gx.stamenCount*m.stamen)));if(st)stamens(ctx,cx,cy,R,gx,seed,st,lerp(.72,1.05,1-m.tube));if(gx.centerOpenness>.20)style(ctx,cx,cy,R,gx);
}

export function drawPhotorealFlower(ctx,p,{width,height,dpr=1}={}){
 const W=width||innerWidth,H=height||innerHeight,gx=p.genetics||derivePhenotype(p.genome),m=morphProfile(p.genome,gx),seed=p.genome.digest,usableH=Math.max(260,H-126),cx=W*.5,cy=Math.min(H*.45,usableH*.48+38),R=Math.min(W*.44,usableH*.39)*gx.scale;
 ctx.setTransform(dpr,0,0,dpr,0,0);drawBokeh(ctx,W,H,seed);supportPlant(ctx,W,H,cx,cy,R,gx,seed);
 const clusterStrength=smooth((Math.max(m.cluster,gx.cluster)-.48)/.52);
 if(clusterStrength>.18){
   const n=Math.max(3,Math.min(12,Math.round(lerp(3,12,gx.clusterDensity)*clusterStrength))),spread=R*lerp(.28,.78,gx.branching),heads=[];
   for(let i=0;i<n;i++){const a=i*2.399963+rand(mix(seed,i,88))*.25,r=spread*Math.sqrt((i+.4)/n),x=cx+Math.cos(a)*r,y=cy+Math.sin(a)*r*.58,sc=lerp(.26,.48,rand(mix(seed,i,89)))*lerp(.82,1.18,1-i/n);heads.push({x,y,sc,z:y});}
   heads.sort((a,b)=>a.z-b.z);for(let i=0;i<heads.length;i++){const h=heads[i];drawHead(ctx,p,h.x,h.y,R,m,gx,seed+i*739,h.sc);}
 }else drawHead(ctx,p,cx,cy,R,m,gx,seed,1);
 const vign=ctx.createRadialGradient(W*.5,H*.42,Math.min(W,H)*.24,W*.5,H*.46,Math.max(W,H)*.78);vign.addColorStop(0,'rgba(0,0,0,0)');vign.addColorStop(1,'rgba(0,0,0,.42)');ctx.fillStyle=vign;ctx.fillRect(0,0,W,H);
 ctx.globalAlpha=.035;for(let i=0;i<115;i++){ctx.fillStyle=i&1?'#fff':'#000';ctx.beginPath();ctx.arc(rand(mix(seed,i,311))*W,rand(mix(seed,i,312))*H,.3+rand(mix(seed,i,313))*.9,0,TAU);ctx.fill()}ctx.globalAlpha=1;
 return describeFlower(p.genome);
}
