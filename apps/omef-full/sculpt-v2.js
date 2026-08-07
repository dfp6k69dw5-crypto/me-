/* OMEF FULL v2 sculpt + dynamics patch. Injected inside the base IIFE. */
const sculpt={lens:'basin',lobes:.72,fold:.58,twist:.48,radial:.18,shear:0,aspect:1.0,phase:.72};
const dyn={coupling:1.0,higher:1.0,regimePersistence:.72,cycleSpeed:1.0,cyclePersistence:1.0,memory:1.0,accounting:.72};
const _pairRaw=()=>BASE_A.map(row=>row.slice());
const _triRaw=()=>TRIADS.map(t=>({...t}));
let PAIR_SOURCE=_pairRaw(), TRIAD_SOURCE=_triRaw();
const TS0=TSHORT.slice(), TL0=TLONG.slice(), RS0=RHOS.slice(), RL0=RHOL.slice(), FW0=FIBW.slice();

function applyDynamics(){
  BASE_A=PAIR_SOURCE.map(row=>row.map(w=>w*dyn.coupling));
  TRIADS=TRIAD_SOURCE.map(t=>({...t,w:t.w*dyn.higher}));
  for(let i=0;i<TSHORT.length;i++) TSHORT[i]=TS0[i]/dyn.cycleSpeed;
  for(let i=0;i<TLONG.length;i++) TLONG[i]=TL0[i]/dyn.cycleSpeed;
  for(let i=0;i<RHOS.length;i++) RHOS[i]=clamp(1-(1-RS0[i])*dyn.cyclePersistence,.72,.998);
  for(let i=0;i<RHOL.length;i++) RHOL[i]=clamp(1-(1-RL0[i])*dyn.cyclePersistence,.82,.999);
  for(let i=0;i<FIBW.length;i++) FIBW[i]=FW0[i]*dyn.memory;
}

regimeProb=function(U,prev,out,X){
  let r=U[0],m=U[1],d=U[2],p=U[3],f=U[4],l=U[5],pi=U[6],s=U[7],g=U[8],h=U[9];
  let scores=[1.2*g+.75*p+.65*l+.2*m-.65*s-.45*h+.12*X[0],1.05*pi+.65*r+.48*s+.4*h-.2*g+.1*X[1],1.15*s+.7*d+.8*h-.35*m-.45*g+.12*X[2],-.95*g-.75*p-.65*l+.8*h+.72*out[0]+.12*X[3]];
  let q=softmax(scores), keep=clamp(dyn.regimePersistence,.02,.985), fresh=1-keep;
  let mix=q.map((v,i)=>keep*prev[i]+fresh*v), den=mix.reduce((a,b)=>a+b,0)||1;
  return mix.map(v=>v/den);
};
correctAccounting=function(raw){
  let res=accountingResidual(raw),v=[0,0,-.15,.32,.18,0,-.08,-.11,.24,0],den=dot(v,v)+1e-6;
  let strength=clamp(dyn.accounting,0,1);
  let out=raw.map((x,i)=>clamp(x-res*v[i]/den*strength,-1.35,1.35));
  return {U:out,residual:accountingResidual(out),rawResidual:res};
};

function captureBase(){for(const r of records){r.__bx=r.x;r.__by=r.y;r.__bz=r.z;}}
function regimeVector(r){let q=[0,0,0];for(let j=0;j<4;j++){q[0]+=r.S[j]*RANCHOR[j][0];q[1]+=r.S[j]*RANCHOR[j][1];q[2]+=r.S[j]*RANCHOR[j][2];}return q;}
function sculptOne(r,i,N){
  let x=r.__bx??r.x,y=r.__by??r.y,z=r.__bz??r.z;
  const rv=regimeVector(r), stress=r.U[7]||0, growth=r.U[8]||0, hidden=r.U[9]||0, infl=r.U[6]||0;
  const p1=Math.atan2(r.Z[1]||0,r.Z[0]||1),p2=Math.atan2(r.Z[5]||0,r.Z[4]||1),p3=Math.atan2(r.Z[9]||0,r.Z[8]||1);
  const phase=p1+.55*p2+.32*p3, t=i/Math.max(1,N-1), conf=r.D[0]||0, spec=r.D[2]||0;
  x+=sculpt.lobes*1.65*rv[0]; y+=sculpt.lobes*1.65*rv[1]; z+=sculpt.lobes*1.2*rv[2];
  let rad=Math.hypot(x,y)+1e-6,ang=Math.atan2(y,x),warp=Math.exp(sculpt.radial*.72*Math.tanh(hidden+stress-growth+.3*infl));rad*=warp;x=rad*Math.cos(ang);y=rad*Math.sin(ang);
  const fg=sculpt.fold;
  x+=fg*.24*Math.sin(1.35*y-phase+2.2*infl)*(0.45+.2*Math.abs(y));
  y+=fg*.42*Math.sin(1.55*x+sculpt.phase*phase+2.5*hidden)*(0.48+.18*Math.abs(x));
  const ta=sculpt.twist*(1.05*z+.42*phase+.5*(r.mem||0))*2.2,ct=Math.cos(ta),st=Math.sin(ta);let xx=x*ct-y*st,yy=x*st+y*ct;x=xx;y=yy;
  x+=sculpt.shear*.72*y+.18*sculpt.shear*z;y+=sculpt.shear*.18*z;
  if(sculpt.lens==='ribbon'){
    const u=.72*x+.28*z, width=.20*y+.26*(stress-growth), wave=sculpt.phase*phase+TAU*t*1.7;
    x=u+.16*Math.sin(wave);y=width+.62*Math.sin(wave)*(0.38+.45*(1-conf));z=.3*z+.48*Math.cos(wave);
  }else if(sculpt.lens==='shell'){
    const rr=.72+.33*Math.tanh(rad)+.16*hidden+.10*(1-conf),theta=ang+sculpt.twist*phase+.45*rv[0],phi=.72*Math.tanh(z)+.34*phase+.30*rv[2];
    x=rr*Math.cos(theta)*Math.cos(phi);y=rr*Math.sin(theta)*Math.cos(phi);z=rr*Math.sin(phi);
  }else if(sculpt.lens==='knot'){
    const th=ang+sculpt.twist*(phase+.8*t*TAU),ph=1.4*phase+TAU*t*(1.2+.55*sculpt.phase),R=1.0+.18*Math.tanh(hidden-stress),tube=.24+.16*(1-spec)+.10*Math.abs(growth);
    x=(R+tube*Math.cos(ph))*Math.cos(2*th+.35*rv[0]);y=(R+tube*Math.cos(ph))*Math.sin(2*th+.35*rv[1]);z=tube*Math.sin(ph)+.22*z;
  }else if(sculpt.lens==='filament'){
    const u=.86*x+.22*z,ph=phase+TAU*t*(1.8+.8*sculpt.phase),amp=.18+.34*(1-conf)+.16*Math.abs(hidden);
    x=u;y=.18*y+amp*Math.sin(ph);z=.18*z+amp*Math.cos(ph);
  }else if(sculpt.lens==='membrane'){
    const q=.42*Math.sin(phase+2.1*x)+.28*Math.sin(2.3*y-hidden*3)+.18*rv[2];
    x=x+.35*q*sculpt.phase;y=y+.28*Math.sin(q*3+phase)*fg;z=.35*z+.65*q;
  }
  x*=sculpt.aspect;y/=Math.max(.28,sculpt.aspect);
  return [x,y,z];
}
function applySculpt(){
  if(!records.length)return;
  for(let i=0;i<records.length;i++){let r=records[i],p=sculptOne(r,i,records.length);r.x=p[0];r.y=p[1];r.z=p[2];}
  render();
}
function restoreBase(){for(const r of records){if(r.__bx!=null){r.x=r.__bx;r.y=r.__by;r.z=r.__bz;}}}
function resculpt(){restoreBase();applySculpt();}
function rebuildSculpt(){applyDynamics();rebuild();captureBase();applySculpt();runTests(false);}

const style=document.createElement('style');style.textContent=`
.sculptBox{background:linear-gradient(180deg,rgba(216,198,141,.055),transparent)}
.sculptBox select{width:100%;background:#171c24;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:9px}
.sculptBtns{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}.micro{font-size:11px;color:var(--muted);line-height:1.4;margin-top:8px}
`;
document.head.appendChild(style);
const organismSection=document.querySelector('.panel .section');
const sec=document.createElement('div');sec.className='section sculptBox';sec.innerHTML=`<h2>Sculpt the organism</h2>
<div class="row"><label>Topology lens</label><select id="shapeLens"><option value="basin">Regime basins</option><option value="ribbon">Phase ribbon</option><option value="shell">State shell</option><option value="knot">OMEF knot</option><option value="filament">Filament</option><option value="membrane">Interaction membrane</option></select><div class="value">MODE</div></div>
<div class="row"><label>Lobe force</label><input id="shapeLobes" type="range" min="0" max="200" value="72"><div class="value" id="shapeLobesV">72</div></div>
<div class="row"><label>Nonlinear fold</label><input id="shapeFold" type="range" min="0" max="200" value="58"><div class="value" id="shapeFoldV">58</div></div>
<div class="row"><label>State twist</label><input id="shapeTwist" type="range" min="0" max="200" value="48"><div class="value" id="shapeTwistV">48</div></div>
<div class="row"><label>Radial warp</label><input id="shapeRadial" type="range" min="-100" max="100" value="18"><div class="value" id="shapeRadialV">18</div></div>
<div class="row"><label>Shear</label><input id="shapeShear" type="range" min="-100" max="100" value="0"><div class="value" id="shapeShearV">0</div></div>
<div class="row"><label>Aspect</label><input id="shapeAspect" type="range" min="35" max="180" value="100"><div class="value" id="shapeAspectV">100</div></div>
<div class="row"><label>Phase gain</label><input id="shapePhase" type="range" min="0" max="200" value="72"><div class="value" id="shapePhaseV">72</div></div>
<div class="sculptBtns"><button id="shapeRandom">Wild shape</button><button id="shapeReset">Reset shape</button></div><div class="micro">These controls transform geometry with regime probabilities, organ state, golden-cycle phase, hidden strain, confidence and spectral state. They are not opacity controls.</div>`;
organismSection.insertAdjacentElement('afterend',sec);
const dynSec=document.createElement('div');dynSec.className='section';dynSec.innerHTML=`<h2>Change the mathematics</h2>
<div class="row"><label>Pair coupling</label><input id="dynCoupling" type="range" min="0" max="220" value="100"><div class="value" id="dynCouplingV">100</div></div>
<div class="row"><label>Higher-order</label><input id="dynHigher" type="range" min="0" max="260" value="100"><div class="value" id="dynHigherV">100</div></div>
<div class="row"><label>Regime memory</label><input id="dynRegime" type="range" min="5" max="98" value="72"><div class="value" id="dynRegimeV">72</div></div>
<div class="row"><label>Cycle speed</label><input id="dynCycle" type="range" min="35" max="240" value="100"><div class="value" id="dynCycleV">100</div></div>
<div class="row"><label>Cycle persistence</label><input id="dynPersist" type="range" min="45" max="160" value="100"><div class="value" id="dynPersistV">100</div></div>
<div class="row"><label>Fibonacci feedback</label><input id="dynMemory" type="range" min="0" max="260" value="100"><div class="value" id="dynMemoryV">100</div></div>
<div class="row"><label>Accounting pull</label><input id="dynAccounting" type="range" min="0" max="100" value="72"><div class="value" id="dynAccountingV">72</div></div>
<div class="micro">These rebuild the 123-D orbit. Pair and higher-order controls rescale OMEF interaction structure; cycle controls alter the paired golden oscillators; regime memory changes transition persistence; Fibonacci feedback changes hidden-strain memory; accounting pull changes projection back toward the constraint manifold.</div>`;
sec.insertAdjacentElement('afterend',dynSec);

function bindShape(id,key,scale=100){let el=document.getElementById(id),vo=document.getElementById(id+'V');el.addEventListener('input',()=>{sculpt[key]=+el.value/scale;vo.textContent=el.value;resculpt();});}
bindShape('shapeLobes','lobes');bindShape('shapeFold','fold');bindShape('shapeTwist','twist');bindShape('shapeRadial','radial');bindShape('shapeShear','shear');bindShape('shapeAspect','aspect');bindShape('shapePhase','phase');
document.getElementById('shapeLens').addEventListener('change',e=>{sculpt.lens=e.target.value;resculpt();});
let dynTimer=0;function dynChange(id,key,scale=100){let el=document.getElementById(id),vo=document.getElementById(id+'V');el.addEventListener('input',()=>{dyn[key]=+el.value/scale;vo.textContent=el.value;clearTimeout(dynTimer);dynTimer=setTimeout(rebuildSculpt,140);});}
dynChange('dynCoupling','coupling');dynChange('dynHigher','higher');dynChange('dynRegime','regimePersistence',100);dynChange('dynCycle','cycleSpeed');dynChange('dynPersist','cyclePersistence');dynChange('dynMemory','memory');dynChange('dynAccounting','accounting',100);

document.getElementById('shapeReset').onclick=()=>{Object.assign(sculpt,{lens:'basin',lobes:.72,fold:.58,twist:.48,radial:.18,shear:0,aspect:1,phase:.72});document.getElementById('shapeLens').value='basin';[['shapeLobes',72],['shapeFold',58],['shapeTwist',48],['shapeRadial',18],['shapeShear',0],['shapeAspect',100],['shapePhase',72]].forEach(([id,v])=>{document.getElementById(id).value=v;document.getElementById(id+'V').textContent=v;});resculpt();};
document.getElementById('shapeRandom').onclick=()=>{const lenses=['basin','ribbon','shell','knot','filament','membrane'];sculpt.lens=lenses[Math.floor(hash01(seed*41+records.length)*lenses.length)];sculpt.lobes=.15+1.65*hash01(seed*43+1);sculpt.fold=.15+1.65*hash01(seed*47+2);sculpt.twist=.1+1.8*hash01(seed*53+3);sculpt.radial=-.75+1.5*hash01(seed*59+4);sculpt.shear=-.65+1.3*hash01(seed*61+5);sculpt.aspect=.55+1.05*hash01(seed*67+6);sculpt.phase=.2+1.65*hash01(seed*71+7);document.getElementById('shapeLens').value=sculpt.lens;[['shapeLobes','lobes'],['shapeFold','fold'],['shapeTwist','twist'],['shapeRadial','radial'],['shapeShear','shear'],['shapeAspect','aspect'],['shapePhase','phase']].forEach(([id,k])=>{let v=Math.round(sculpt[k]*100);document.getElementById(id).value=v;document.getElementById(id+'V').textContent=v;});resculpt();};

const oldMut=document.getElementById('mutate');oldMut.onclick=()=>{seed=(seed+1)%997;BASE_A=makePair();TRIADS=makeTriads();PAIR_SOURCE=_pairRaw();TRIAD_SOURCE=_triRaw();applyDynamics();rebuild();captureBase();applySculpt();};
const oldReg=document.getElementById('regen');oldReg.onclick=()=>{rebuild();captureBase();applySculpt();};
['density','projection','regimeSpace'].forEach(id=>document.getElementById(id).addEventListener('input',()=>setTimeout(()=>{captureBase();applySculpt();},0)));
const detailHeading=[...document.querySelectorAll('.section h2')].find(h=>h.textContent==='Formula geometry');if(detailHeading)detailHeading.textContent='Detail layers (appearance only)';
const densityEl=document.getElementById('density');densityEl.min='1500';densityEl.max='32000';
if(!qs.has('fast')){params.density=7000;densityEl.value=7000;document.getElementById('densityV').textContent='7K';rebuild();}
captureBase();applyDynamics();applySculpt();
window.__OMEF_SCULPT__={sculpt,dyn,resculpt,rebuildSculpt,captureBase};
