(function(){'use strict';
var SPECIES={
 pairLattice:{label:'Pair Lattice',note:'Pairwise organ interaction network dominates; triads and cycles recede.',pair:225,triad:28,market:175,shadow:70,regime:42,golden:42,fib:58,learning:118,stability:112,accounting:66,projection:14},
 triadicBloom:{label:'Triadic Bloom',note:'Higher-order q_ijk interactions dominate the nonlinear field.',pair:72,triad:285,market:82,shadow:92,regime:78,golden:142,fib:88,learning:112,stability:78,accounting:54,projection:73},
 shadowDouble:{label:'Shadow Double',note:'Counterfactual shadow-state feedback dominates the observer correction.',pair:94,triad:102,market:76,shadow:235,regime:58,golden:108,fib:154,learning:88,stability:92,accounting:46,projection:96},
 spectralKnife:{label:'Spectral Knife',note:'Weak stability braking pushes the Jacobian toward the spectral edge.',pair:218,triad:228,market:188,shadow:142,regime:118,golden:88,fib:82,learning:188,stability:24,accounting:28,projection:11},
 accountingCage:{label:'Accounting Cage',note:'Accounting constraints repeatedly project the orbit back toward balance.',pair:126,triad:118,market:96,shadow:102,regime:84,golden:82,fib:92,learning:74,stability:148,accounting:155,projection:56},
 regimeGlass:{label:'Regime Glass',note:'Rapid four-regime mixing inside a highly damped, constrained field.',pair:62,triad:34,market:88,shadow:58,regime:232,golden:118,fib:68,learning:48,stability:174,accounting:128,projection:31},
 fibonacciCoil:{label:'Fibonacci Coil',note:'Eight-lag reciprocal-Fibonacci hidden-strain memory dominates persistence.',pair:98,triad:106,market:102,shadow:142,regime:58,golden:138,fib:255,learning:72,stability:106,accounting:68,projection:64},
 goldenCage:{label:'Golden Cage',note:'Golden-ratio oscillator pairs trapped by strong accounting and stability.',pair:58,triad:42,market:62,shadow:48,regime:38,golden:258,fib:102,learning:38,stability:158,accounting:148,projection:88},
 learningScar:{label:'Learning Scar',note:'Adaptive theta_ij learning continually rewrites pair-interaction geometry.',pair:162,triad:172,market:122,shadow:168,regime:82,golden:72,fib:88,learning:238,stability:82,accounting:62,projection:43},
 marketTide:{label:'Market Tide',note:'The rolling 60-step W^M cross-organ correlation field dominates transport.',pair:112,triad:82,market:235,shadow:78,regime:126,golden:74,fib:62,learning:92,stability:106,accounting:72,projection:77},
 lowRankVeil:{label:'Low-Rank Veil',note:'Most direct interactions are suppressed; cycles and long memory carry the form.',pair:34,triad:22,market:38,shadow:82,regime:28,golden:198,fib:196,learning:22,stability:186,accounting:92,projection:7},
 observerEcho:{label:'Observer Echo',note:'Shadow innovation, observer retention and memory repeatedly echo through state.',pair:76,triad:72,market:54,shadow:222,regime:48,golden:98,fib:188,learning:126,stability:118,accounting:78,projection:51},
 creditFracture:{label:'Credit Fracture',note:'Stress-regime mixing, market coupling and triads compete near instability.',pair:156,triad:214,market:205,shadow:172,regime:206,golden:64,fib:126,learning:152,stability:58,accounting:48,projection:84},
 inflationHalo:{label:'Inflation Halo',note:'Rate-stress regime motion is braided with persistent golden oscillators.',pair:102,triad:86,market:148,shadow:96,regime:218,golden:205,fib:78,learning:82,stability:116,accounting:84,projection:24},
 recessionFold:{label:'Recession Fold',note:'Slow memory, shadow feedback and regime pressure fold the orbit inward.',pair:126,triad:136,market:168,shadow:194,regime:198,golden:52,fib:224,learning:94,stability:91,accounting:72,projection:67},
 covarianceFog:{label:'Covariance Fog',note:'Uncertainty-sensitive damping and market coupling produce diffuse recurrent structure.',pair:132,triad:152,market:194,shadow:188,regime:112,golden:126,fib:132,learning:144,stability:44,accounting:52,projection:39},
 rotationKnot:{label:'Five-Rotation Knot',note:'Adaptive pair asymmetries strongly drive the five internal 2-D rotation blocks.',pair:208,triad:116,market:94,shadow:114,regime:72,golden:122,fib:74,learning:228,stability:76,accounting:58,projection:19},
 counterBloom:{label:'Counterfactual Bloom',note:'Shadow-state closure, triads and golden cycles all reinforce one another.',pair:118,triad:244,market:108,shadow:226,regime:104,golden:224,fib:146,learning:132,stability:66,accounting:44,projection:91}
};
var ids=['pair','triad','market','shadow','regime','golden','fib','learning','stability','accounting','projection'];
var grid=document.getElementById('presets'),render=document.getElementById('render'),reset=document.getElementById('reset');
if(!grid||!render||!reset)return;
var currentCustom=null,oldReset=reset.onclick;
function clearActive(){grid.querySelectorAll('button').forEach(function(b){b.classList.remove('active')})}
function apply(name){var s=SPECIES[name];if(!s)return;currentCustom=name;for(var i=0;i<ids.length;i++){var el=document.getElementById(ids[i]);if(el)el.value=s[ids[i]]}clearActive();var b=grid.querySelector('[data-omefa-species="'+name+'"]');if(b)b.classList.add('active');render.click()}
Array.prototype.slice.call(grid.querySelectorAll('button')).forEach(function(b){b.addEventListener('click',function(){currentCustom=null})});
Object.keys(SPECIES).forEach(function(name){var s=SPECIES[name],b=document.createElement('button');b.type='button';b.textContent=s.label;b.title=s.note;b.setAttribute('aria-label',s.label+': '+s.note);b.dataset.omefaSpecies=name;b.onclick=function(){apply(name)};grid.appendChild(b)});
reset.onclick=function(){if(currentCustom){apply(currentCustom)}else if(oldReset){oldReset.call(reset)}};
var hint=document.createElement('div');hint.className='small';hint.style.marginTop='9px';hint.textContent='24 dynamical species. Each species emphasizes a different OMEF-A subsystem; press and hold / hover a species name for its mathematical emphasis.';grid.parentNode.insertBefore(hint,grid.nextSibling);
})();
