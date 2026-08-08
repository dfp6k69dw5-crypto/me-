(function(){'use strict';
/* Species v2: species alter the recurrence itself. The core calls Math.tanh throughout its nonlinear field; this species-aware transfer therefore changes the actual orbit equations, not just rendering. */
var nativeTanh=Math.tanh;
function speciesTanh(x){var g=window.OMEFA_SPECIES;if(!g)return nativeTanh(x);var t=nativeTanh(x),a=g.arch,p=g.phase||0;
 if(a==='triad'||a==='fracture')return nativeTanh(x+.24*Math.sin(2.7*x+p));
 if(a==='shadow'||a==='observer'||a==='counter')return .78*t+.22*nativeTanh(1.8*x-.35*Math.sin(x+p));
 if(a==='spectral')return nativeTanh(1.22*x)-.09*nativeTanh(3.1*x);
 if(a==='golden'||a==='inflation')return .82*t+.18*Math.sin(1.618*x+p);
 if(a==='fib'||a==='lowrank'||a==='recession')return nativeTanh(.88*x+.18*Math.sin(.618*x+p));
 if(a==='regime')return nativeTanh(x)*(1-.12*Math.cos(2*x+p));
 if(a==='account')return nativeTanh(.78*x)+.12*nativeTanh(2.4*x);
 if(a==='learning'||a==='rotation')return nativeTanh(x+.14*Math.sin(4*x+p));
 if(a==='market'||a==='covariance')return .86*t+.14*nativeTanh(x+Math.sin(1.3*x+p));
 if(a==='lattice')return nativeTanh(x+.12*Math.sin(3*x+p));
 return t}
Math.tanh=speciesTanh;
var SPECIES={
 pairLattice:{label:'Pair Lattice',note:'Sparse pair-network lattice; nonlinear transfer is lattice-modulated.',pair:225,triad:28,market:175,shadow:70,regime:42,golden:42,fib:58,learning:118,stability:112,accounting:66,projection:14,arch:'lattice',phase:.17},
 triadicBloom:{label:'Triadic Bloom',note:'q_ijk-dominant field with a triad-specific nonlinear transfer.',pair:72,triad:285,market:82,shadow:92,regime:78,golden:142,fib:88,learning:112,stability:78,accounting:54,projection:73,arch:'triad',phase:1.31},
 shadowDouble:{label:'Shadow Double',note:'Counterfactual observer plus a shadow-specific asymmetric transfer.',pair:94,triad:102,market:76,shadow:235,regime:58,golden:108,fib:154,learning:88,stability:92,accounting:46,projection:96,arch:'shadow',phase:2.27},
 spectralKnife:{label:'Spectral Knife',note:'Near-spectral-edge recurrence with sharpened two-scale transfer.',pair:218,triad:228,market:188,shadow:142,regime:118,golden:88,fib:82,learning:188,stability:24,accounting:28,projection:11,arch:'spectral',phase:3.07},
 accountingCage:{label:'Accounting Cage',note:'Strong accounting projection plus compressed/expanded nonlinear response.',pair:126,triad:118,market:96,shadow:102,regime:84,golden:82,fib:92,learning:74,stability:148,accounting:155,projection:56,arch:'account',phase:.83},
 regimeGlass:{label:'Regime Glass',note:'Rapid four-regime mixing modulates the nonlinear response itself.',pair:62,triad:34,market:88,shadow:58,regime:232,golden:118,fib:68,learning:48,stability:174,accounting:128,projection:31,arch:'regime',phase:1.77},
 fibonacciCoil:{label:'Fibonacci Coil',note:'Eight-lag memory with a golden-subharmonic nonlinear transfer.',pair:98,triad:106,market:102,shadow:142,regime:58,golden:138,fib:255,learning:72,stability:106,accounting:68,projection:64,arch:'fib',phase:2.91},
 goldenCage:{label:'Golden Cage',note:'Golden oscillators also modulate the recurrence transfer at phi frequency.',pair:58,triad:42,market:62,shadow:48,regime:38,golden:258,fib:102,learning:38,stability:158,accounting:148,projection:88,arch:'golden',phase:.39},
 learningScar:{label:'Learning Scar',note:'Adaptive theta learning with a high-frequency state-dependent transfer.',pair:162,triad:172,market:122,shadow:168,regime:82,golden:72,fib:88,learning:238,stability:82,accounting:62,projection:43,arch:'learning',phase:2.13},
 marketTide:{label:'Market Tide',note:'60-step W^M transport changes both coupling strength and transfer shape.',pair:112,triad:82,market:235,shadow:78,regime:126,golden:74,fib:62,learning:92,stability:106,accounting:72,projection:77,arch:'market',phase:1.09},
 lowRankVeil:{label:'Low-Rank Veil',note:'Suppressed direct interactions with subharmonic memory transfer.',pair:34,triad:22,market:38,shadow:82,regime:28,golden:198,fib:196,learning:22,stability:186,accounting:92,projection:7,arch:'lowrank',phase:2.59},
 observerEcho:{label:'Observer Echo',note:'Observer retention and shadow feedback use an echo-shaped transfer.',pair:76,triad:72,market:54,shadow:222,regime:48,golden:98,fib:188,learning:126,stability:118,accounting:78,projection:51,arch:'observer',phase:.61},
 creditFracture:{label:'Credit Fracture',note:'Stress, market and triads use a folded triadic transfer near instability.',pair:156,triad:214,market:205,shadow:172,regime:206,golden:64,fib:126,learning:152,stability:58,accounting:48,projection:84,arch:'fracture',phase:2.43},
 inflationHalo:{label:'Inflation Halo',note:'Rate-stress regime braided with phi-frequency transfer modulation.',pair:102,triad:86,market:148,shadow:96,regime:218,golden:205,fib:78,learning:82,stability:116,accounting:84,projection:24,arch:'inflation',phase:1.47},
 recessionFold:{label:'Recession Fold',note:'Long memory and recession pressure use a slow subharmonic transfer.',pair:126,triad:136,market:168,shadow:194,regime:198,golden:52,fib:224,learning:94,stability:91,accounting:72,projection:67,arch:'recession',phase:3.31},
 covarianceFog:{label:'Covariance Fog',note:'Covariance/market field drives a correlation-sensitive transfer family.',pair:132,triad:152,market:194,shadow:188,regime:112,golden:126,fib:132,learning:144,stability:44,accounting:52,projection:39,arch:'covariance',phase:.97},
 rotationKnot:{label:'Five-Rotation Knot',note:'Five rotation blocks feed a rapidly modulated recurrence transfer.',pair:208,triad:116,market:94,shadow:114,regime:72,golden:122,fib:74,learning:228,stability:76,accounting:58,projection:19,arch:'rotation',phase:2.01},
 counterBloom:{label:'Counterfactual Bloom',note:'Shadow, triads and golden cycles combine with asymmetric counterfactual transfer.',pair:118,triad:244,market:108,shadow:226,regime:104,golden:224,fib:146,learning:132,stability:66,accounting:44,projection:91,arch:'counter',phase:3.73}
};
var ids=['pair','triad','market','shadow','regime','golden','fib','learning','stability','accounting','projection'];var grid=document.getElementById('presets'),render=document.getElementById('render'),reset=document.getElementById('reset');if(!grid||!render||!reset)return;var currentCustom=null,oldReset=reset.onclick;
function clearActive(){grid.querySelectorAll('button').forEach(function(b){b.classList.remove('active')})}
function apply(name){var s=SPECIES[name];if(!s)return;currentCustom=name;window.OMEFA_SPECIES=s;for(var i=0;i<ids.length;i++){var el=document.getElementById(ids[i]);if(el)el.value=s[ids[i]]}clearActive();var b=grid.querySelector('[data-omefa-species="'+name+'"]');if(b)b.classList.add('active');render.click()}
Array.prototype.slice.call(grid.querySelectorAll('button')).forEach(function(b){b.addEventListener('click',function(){currentCustom=null;window.OMEFA_SPECIES=null})});
Object.keys(SPECIES).forEach(function(name){var s=SPECIES[name],b=document.createElement('button');b.type='button';b.textContent=s.label;b.title=s.note;b.setAttribute('aria-label',s.label+': '+s.note);b.dataset.omefaSpecies=name;b.onclick=function(){apply(name)};grid.appendChild(b)});
reset.onclick=function(){if(currentCustom){apply(currentCustom)}else if(oldReset){oldReset.call(reset)}};
var hint=document.createElement('div');hint.className='small';hint.style.marginTop='9px';hint.textContent='Species v2: switching species now changes the nonlinear recurrence used by the OMEF-A engine as well as its subsystem weights. These are no longer just slider presets.';grid.parentNode.insertBefore(hint,grid.nextSibling);
})();