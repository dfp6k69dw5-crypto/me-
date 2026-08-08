(function(){'use strict';
/* Species v2: species are architectural genomes, not merely slider presets. */
var SPECIES={
 pairLattice:{label:'Pair Lattice',note:'Sparse pair-network lattice; triads recede.',pair:225,triad:28,market:175,shadow:70,regime:42,golden:42,fib:58,learning:118,stability:112,accounting:66,projection:14,arch:'lattice',proj:'pair',phase:.17},
 triadicBloom:{label:'Triadic Bloom',note:'Three-way q_ijk topology folds the orbit into triadic sheets.',pair:72,triad:285,market:82,shadow:92,regime:78,golden:142,fib:88,learning:112,stability:78,accounting:54,projection:73,arch:'triad',proj:'triad',phase:1.31},
 shadowDouble:{label:'Shadow Double',note:'Delayed counterfactual state is unfolded against the present state.',pair:94,triad:102,market:76,shadow:235,regime:58,golden:108,fib:154,learning:88,stability:92,accounting:46,projection:96,arch:'shadow',proj:'shadow',phase:2.27},
 spectralKnife:{label:'Spectral Knife',note:'Projection follows a near-spectral edge and derivative-like mode.',pair:218,triad:228,market:188,shadow:142,regime:118,golden:88,fib:82,learning:188,stability:24,accounting:28,projection:11,arch:'spectral',proj:'spectral',phase:3.07},
 accountingCage:{label:'Accounting Cage',note:'Accounting residual coordinates become the visible geometry.',pair:126,triad:118,market:96,shadow:102,regime:84,golden:82,fib:92,learning:74,stability:148,accounting:155,projection:56,arch:'account',proj:'account',phase:.83},
 regimeGlass:{label:'Regime Glass',note:'Four regime probabilities directly bend the visible state.',pair:62,triad:34,market:88,shadow:58,regime:232,golden:118,fib:68,learning:48,stability:174,accounting:128,projection:31,arch:'regime',proj:'regime',phase:1.77},
 fibonacciCoil:{label:'Fibonacci Coil',note:'Multiple Fibonacci-separated delays form the projection.',pair:98,triad:106,market:102,shadow:142,regime:58,golden:138,fib:255,learning:72,stability:106,accounting:68,projection:64,arch:'fib',proj:'fib',phase:2.91},
 goldenCage:{label:'Golden Cage',note:'Short/long golden oscillator pairs become the principal coordinates.',pair:58,triad:42,market:62,shadow:48,regime:38,golden:258,fib:102,learning:38,stability:158,accounting:148,projection:88,arch:'golden',proj:'golden',phase:.39},
 learningScar:{label:'Learning Scar',note:'Adaptive theta field is exposed as a moving coordinate.',pair:162,triad:172,market:122,shadow:168,regime:82,golden:72,fib:88,learning:238,stability:82,accounting:62,projection:43,arch:'learning',proj:'learning',phase:2.13},
 marketTide:{label:'Market Tide',note:'Rolling 60-step W^M transport defines the visible manifold.',pair:112,triad:82,market:235,shadow:78,regime:126,golden:74,fib:62,learning:92,stability:106,accounting:72,projection:77,arch:'market',proj:'market',phase:1.09},
 lowRankVeil:{label:'Low-Rank Veil',note:'A low-rank delay embedding exposes thin recurrent sheets.',pair:34,triad:22,market:38,shadow:82,regime:28,golden:198,fib:196,learning:22,stability:186,accounting:92,projection:7,arch:'lowrank',proj:'delay',phase:2.59},
 observerEcho:{label:'Observer Echo',note:'Observer state L is projected against its delayed echo.',pair:76,triad:72,market:54,shadow:222,regime:48,golden:98,fib:188,learning:126,stability:118,accounting:78,projection:51,arch:'observer',proj:'observer',phase:.61},
 creditFracture:{label:'Credit Fracture',note:'Stress regime, market pressure and triads form a fractured map.',pair:156,triad:214,market:205,shadow:172,regime:206,golden:64,fib:126,learning:152,stability:58,accounting:48,projection:84,arch:'fracture',proj:'fracture',phase:2.43},
 inflationHalo:{label:'Inflation Halo',note:'Rate-stress regime braided directly with golden phase.',pair:102,triad:86,market:148,shadow:96,regime:218,golden:205,fib:78,learning:82,stability:116,accounting:84,projection:24,arch:'inflation',proj:'halo',phase:1.47},
 recessionFold:{label:'Recession Fold',note:'Long delays and recession probability create an asymmetric fold.',pair:126,triad:136,market:168,shadow:194,regime:198,golden:52,fib:224,learning:94,stability:91,accounting:72,projection:67,arch:'recession',proj:'recession',phase:3.31},
 covarianceFog:{label:'Covariance Fog',note:'Rolling covariance coordinates replace the common organ projection.',pair:132,triad:152,market:194,shadow:188,regime:112,golden:126,fib:132,learning:144,stability:44,accounting:52,projection:39,arch:'covariance',proj:'covariance',phase:.97},
 rotationKnot:{label:'Five-Rotation Knot',note:'Five internal 2-D rotation blocks are braided into the output.',pair:208,triad:116,market:94,shadow:114,regime:72,golden:122,fib:74,learning:228,stability:76,accounting:58,projection:19,arch:'rotation',proj:'rotation',phase:2.01},
 counterBloom:{label:'Counterfactual Bloom',note:'Shadow, triad and golden coordinates are cross-coupled in projection.',pair:118,triad:244,market:108,shadow:226,regime:104,golden:224,fib:146,learning:132,stability:66,accounting:44,projection:91,arch:'counter',proj:'counter',phase:3.73}
};
var ids=['pair','triad','market','shadow','regime','golden','fib','learning','stability','accounting','projection'];
var grid=document.getElementById('presets'),render=document.getElementById('render'),reset=document.getElementById('reset');if(!grid||!render||!reset)return;
var currentCustom=null,oldReset=reset.onclick;
function clearActive(){grid.querySelectorAll('button').forEach(function(b){b.classList.remove('active')})}
function H(s,lag,i){var slot=(s.head-lag+60)%60;return s.hist[slot*10+i]}
function project(g,s,base){var x=base[0],y=base[1],p=g.phase||0,a,b,c,d,i,row,t1=0,t2=0;
 switch(g.proj){
 case'pair':for(i=0;i<10;i++){row=i*10;t1+=s.pairCoeff[row+((i+3)%10)]*s.U[(i+3)%10];t2+=s.pairCoeff[row+((i+7)%10)]*s.U[(i+7)%10]}x=5*t1+1.1*(H(s,8,0)-H(s,21,5));y=5*t2+1.1*(H(s,13,7)-H(s,34,2));break;
 case'triad':a=s.U[0]*s.U[3]*s.U[7];b=s.U[1]*s.U[5]*s.U[8];c=s.U[2]*s.U[4]*s.U[9];x=3.8*(a-b)+.8*s.cycle[2];y=3.8*(c+a)+.8*s.cycle[6];break;
 case'shadow':x=1.7*(s.U[0]-H(s,13,0))+.9*(s.shadowVec[3]-s.shadowVec[7]);y=1.7*(s.U[6]-H(s,21,6))+.9*(s.shadowVec[1]+s.shadowVec[8]);break;
 case'spectral':x=2.2*(s.U[0]-s.prevU[0])+1.4*s.deltaSpec+.7*(s.U[7]-s.U[2]);y=2.2*(s.U[5]-s.prevU[5])-.9*s.deltaSpec+.7*(s.U[8]-s.U[3]);break;
 case'account':a=s.corrected[2]-s.corrected[3]+s.corrected[4]-s.corrected[8];b=s.corrected[0]-s.corrected[1]+s.corrected[6]-s.corrected[7];x=1.8*a+.5*s.U[9];y=1.8*b-.5*s.U[4];break;
 case'regime':x=2.4*(s.alpha[0]-s.alpha[3])+.8*(s.U[8]-s.U[7]);y=2.4*(s.alpha[1]-s.alpha[2])+.8*(s.U[6]+s.U[2]);break;
 case'fib':x=1.5*(H(s,1,9)-H(s,8,9))+1.0*(H(s,13,0)-H(s,21,3));y=1.5*(H(s,3,9)-H(s,13,9))+1.0*(H(s,8,7)-H(s,34,1));break;
 case'golden':x=1.6*(s.zS[0]+s.zL[6]-s.zS[10])+.45*s.U[0];y=1.6*(s.zL[2]-s.zS[8]+s.zL[14])+.45*s.U[7];break;
 case'learning':for(i=0;i<10;i++){t1+=s.theta[i*10+((i+1)%10)];t2+=s.theta[i*10+((i+4)%10)]}x=1.7*t1+.7*s.U[2];y=1.7*t2+.7*s.U[8];break;
 case'market':for(i=0;i<10;i++){t1+=s.marketPressure[i]*Math.sin(i+p);t2+=s.marketPressure[i]*Math.cos(i*1.7+p)}x=1.8*t1+.5*H(s,13,3);y=1.8*t2+.5*H(s,21,7);break;
 case'delay':x=1.25*(H(s,1,0)-H(s,13,4))+1.1*(H(s,21,8)-H(s,34,2));y=1.25*(H(s,3,7)-H(s,21,1))+1.1*(H(s,13,5)-H(s,34,9));break;
 case'observer':x=2.1*s.L[1]-1.4*s.L[6]+.8*(H(s,8,1)-H(s,21,6));y=2.1*s.L[7]+1.2*s.L[3]+.8*(H(s,13,7)-H(s,34,3));break;
 case'fracture':x=1.4*(s.marketPressure[7]-s.marketPressure[2])+2*(s.alpha[2]-s.alpha[0])+1.3*s.U[2]*s.U[7];y=1.4*(s.marketPressure[6]+s.marketPressure[8])+2*(s.alpha[3]-s.alpha[1])-1.3*s.U[3]*s.U[8];break;
 case'halo':x=1.8*(s.zS[4]+s.zL[4])+.9*(s.alpha[1]-s.alpha[3]);y=1.8*(s.zS[5]+s.zL[5])+.9*(s.U[6]-s.U[8]);break;
 case'recession':x=1.8*(H(s,34,8)-s.U[8])+1.2*(s.alpha[3]-s.alpha[0])+.7*s.shadowVec[2];y=1.8*(H(s,21,3)-s.U[3])+1.2*(s.alpha[3]-s.alpha[1])+.7*s.shadowVec[7];break;
 case'covariance':x=2.2*(s.corr[7]-s.corr[28]+s.corr[63]);y=2.2*(s.corr[16]-s.corr[72]+s.corr[85]);break;
 case'rotation':x=1.1*(s.rot[0]-s.rot[2]+s.rot[6])+.7*(s.rot[8]-s.rot[4]);y=1.1*(s.rot[1]-s.rot[5]+s.rot[9])+.7*(s.rot[3]-s.rot[7]);break;
 case'counter':x=1.1*s.shadowVec[1]+1.3*s.U[0]*s.U[3]*s.U[7]+1.1*(s.zS[0]+s.zL[12]);y=1.1*s.shadowVec[7]+1.3*s.U[2]*s.U[5]*s.U[8]+1.1*(s.zS[7]-s.zL[3]);break;
 }
 /* species-specific nonlinear observation lens; uses only OMEF-A state */
 if(g.arch==='triad'||g.arch==='fracture'||g.arch==='counter'){x+=.18*Math.sin(3*y+p);y+=.18*Math.sin(2*x-p)}
 if(g.arch==='golden'||g.arch==='inflation'){a=x;x=a*Math.cos(.35*s.cycle[0])-y*Math.sin(.35*s.cycle[0]);y=a*Math.sin(.35*s.cycle[0])+y*Math.cos(.35*s.cycle[0])}
 return [x,y];}
function installGenome(g){window.OMEFA_SPECIES=g;window.OMEFA_PROJECT=function(s,base){return project(g,s,base)}}
function apply(name){var s=SPECIES[name];if(!s)return;currentCustom=name;for(var i=0;i<ids.length;i++){var el=document.getElementById(ids[i]);if(el)el.value=s[ids[i]]}installGenome(s);clearActive();var b=grid.querySelector('[data-omefa-species="'+name+'"]');if(b)b.classList.add('active');render.click()}
Array.prototype.slice.call(grid.querySelectorAll('button')).forEach(function(b){b.addEventListener('click',function(){currentCustom=null;window.OMEFA_SPECIES=null;window.OMEFA_PROJECT=null})});
Object.keys(SPECIES).forEach(function(name){var s=SPECIES[name],b=document.createElement('button');b.type='button';b.textContent=s.label;b.title=s.note;b.setAttribute('aria-label',s.label+': '+s.note);b.dataset.omefaSpecies=name;b.onclick=function(){apply(name)};grid.appendChild(b)});
reset.onclick=function(){if(currentCustom){apply(currentCustom)}else if(oldReset){oldReset.call(reset)}};
var hint=document.createElement('div');hint.className='small';hint.style.marginTop='9px';hint.textContent='Species v2: each species now changes which OMEF-A state structures become the attractor coordinates—not merely the 11 sliders.';grid.parentNode.insertBefore(hint,grid.nextSibling);
})();