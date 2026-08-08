
'use strict';
var N=384, genome=new Float32Array(N), seed=61429, source='clifford', structure='veil', bankIndex=0, token=0, timer=0, inverted=false, camera=null;
var BANKS=[
 ['Equation','EQ',0,64,'sourceStepper() + dynamics()'],['Memory','MEM',64,48,'dynamics()'],['Modulation','MOD',112,64,'dynamics()'],['Topology','TOP',176,40,'topology()'],['Warp','WRP',216,64,'warp()'],['Projection','PRJ',280,32,'project()'],['Rendering','RND',312,48,'renderParams() + raster'],['Composition','CMP',360,24,'compose()']
];
var SOURCES=[['clifford','Clifford'],['dejong','De Jong'],['hopalong','Hopalong'],['lorenz','Lorenz'],['rossler','Rössler'],['aizawa','Aizawa'],['thomas','Thomas'],['halvorsen','Halvorsen'],['ikeda','Ikeda'],['henon','Hénon'],['tinkerbell','Tinkerbell'],['gumowski','Gumowski–Mira'],['duffing','Duffing'],['chua','Chua'],['sna','SNA'],['omef','OMEF Hybrid']];
var STRUCTS=[['veil','Veil','clifford',61429],['ribbon','Ribbon','dejong',91277],['double','Double Vortex','gumowski',27183],['trefoil','Trefoil','clifford',73031],['wing','Wing','dejong',50287],['fold','Folded Sheet','tinkerbell',41813],['glass','Glass Stack','hopalong',33961],['split','Split Leaf','hopalong',84673],['blade','Blade','clifford',96731]];
var cv=document.getElementById('cv'),ctx=cv.getContext('2d',{alpha:false}),W=cv.width,H=cv.height,acc=new Float32Array(W*H),img=ctx.createImageData(W,H),$=function(id){return document.getElementById(id)};
function clamp(v,a,b){return Math.max(a,Math.min(b,v))}function lerp(a,b,t){return a+(b-a)*t}function soft(x,l){l=l||4;return l*Math.tanh(x/l)}function hash(s){var h=2166136261>>>0;for(var i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)}return h>>>0}function rng(a){return function(){a|=0;a=a+0x6D2B79F5|0;var t=a;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return ((t^t>>>14)>>>0)/4294967296}}
var BANK_GAIN=[2.15,2.55,2.70,2.45,2.60,2.35,2.55,2.35];
function bankForGene(i){return i<64?0:i<112?1:i<176?2:i<216?3:i<280?4:i<312?5:i<360?6:7}
function G(i){var x=genome[i],gain=BANK_GAIN[bankForGene(i)];return gain*(.48*x+.52*Math.tanh(3.6*x))}
function group(start,k){var i=start+k*4;return [G(i),G(i+1),G(i+2),G(i+3)]}
function setStatus(s){$('status').textContent=s}function schedule(preview){clearTimeout(timer);timer=setTimeout(function(){render(!!preview)},preview?55:130)}
function seedGenome(){var r=rng((seed^hash(structure)^hash(source))>>>0);for(var i=0;i<N;i++)genome[i]=(r()*2-1)*.23+.035*Math.sin((i+1)*.13);var bi={veil:[220,.22],ribbon:[232,.28],double:[176,.35],trefoil:[180,.38],wing:[301,.30],fold:[240,.36],glass:[184,.34],split:[204,.34],blade:[365,.30]}[structure];if(bi)for(var j=0;j<10;j++){var ix=(bi[0]+j)%N;genome[ix]=clamp(genome[ix]+bi[1]*Math.sin(j*.8+1),-1,1)}camera=null}
function eqCarrier(x,y,z){var ax=0,ay=0,az=0;for(var k=0;k<16;k++){var g=group(0,k),f=.65+k*.19+Math.abs(g[1])*.32,ph=g[2]*.9+k*.41,amp=.034+.004*(k%4);ax+=(g[0]*Math.sin(y*f+ph)+g[1]*Math.cos((x+z*.25)*(f*.83)+g[3]))*amp;ay+=(g[1]*Math.sin(x*(f*.91)-ph)-g[0]*Math.cos((y-z*.2)*(f*.77)-g[3]))*amp;az+=(g[2]*Math.sin((x-y)*f+g[0]) + g[3]*Math.cos((x+y)*(f*.55)+g[1]))*(amp*.72)}return [ax,ay,az]}
function sourceStepper(){var x=.11,y=.07,z=.19,v=.03,t=0,th=.1;return function(){var g0=group(0,0),g1=group(0,1),nx,ny,nz,dt,a,b,c,d,u,tt,fx,gr;if(source==='clifford'){a=1.7+g0[1]*.55;b=1.8+g1[1]*.55;c=-.2+g0[3]*.35;d=1.3+g1[3]*.35;nx=Math.sin(a*y+g0[2]*.25)+c*Math.cos(a*x);ny=Math.sin(b*x+g1[2]*.25)+d*Math.cos(b*y);x=nx;y=ny}
else if(source==='dejong'){a=1.35+g0[1]*.65;b=-2.1+g0[3]*.55;c=2.15+g1[1]*.65;d=-1.9+g1[3]*.55;nx=Math.sin(a*y)-Math.cos(b*x);ny=Math.sin(c*x)-Math.cos(d*y);x=nx;y=ny}
else if(source==='hopalong'){a=.8+g0[0]*.55;b=.6+g0[1]*.35;c=1.0+g1[1]*.45;nx=y-Math.sign(x||1)*Math.sqrt(Math.abs(b*x-c));ny=a-x+.02*g1[3]*y;x=soft(nx,7);y=soft(ny,7)}
else if(source==='lorenz'){dt=.006;a=10+g0[0];b=28+g0[1]*3;c=2.666+g1[0]*.35;nx=x+dt*a*(y-x);ny=y+dt*(x*(b-z)-y);nz=z+dt*(x*y-c*z);x=nx;y=ny;z=nz;x/=1.002;y/=1.002;return finish(x/14,y/14,z/18)}
else if(source==='rossler'){dt=.018;a=.2+g0[0]*.03;b=.2+g0[1]*.03;c=5.7+g1[0]*.35;nx=x+dt*(-y-z);ny=y+dt*(x+a*y);nz=z+dt*(b+z*(x-c));x=nx;y=ny;z=nz;return finish(x/7,y/7,z/7)}
else if(source==='aizawa'){dt=.011;a=.95+g0[0]*.04;b=.7+g0[1]*.04;c=.6+g1[0]*.04;d=3.5+g1[1]*.2;nx=x+dt*((z-b)*x-d*y);ny=y+dt*(d*x+(z-b)*y);nz=z+dt*(c+a*z-z*z*z/3-(x*x+y*y)*(1+.25*z)+.1*z*x*x*x);x=nx;y=ny;z=nz;return finish(x,y,z)}
else if(source==='thomas'){dt=.05;b=.19+g0[0]*.012;nx=x+dt*(Math.sin(y)-b*x);ny=y+dt*(Math.sin(z)-b*y);nz=z+dt*(Math.sin(x)-b*z);x=nx;y=ny;z=nz;return finish(x,y,z)}
else if(source==='halvorsen'){dt=.005;a=1.4+g0[0]*.12;nx=x+dt*(-a*x-4*y-4*z-y*y);ny=y+dt*(-a*y-4*z-4*x-z*z);nz=z+dt*(-a*z-4*x-4*y-x*x);x=nx;y=ny;z=nz;return finish(x/5,y/5,z/5)}
else if(source==='ikeda'){u=clamp(.89+g0[0]*.03,.72,.97);tt=6+g0[1]*.5-(1+g1[0]*.15)/(1+x*x+y*y);nx=1+u*(x*Math.cos(tt)-y*Math.sin(tt));ny=u*(x*Math.sin(tt)+y*Math.cos(tt));x=nx;y=ny;z=.2*Math.sin(tt)}
else if(source==='henon'){a=1.39+g0[0]*.035;b=.3+g0[1]*.025;nx=1-a*x*x+y;ny=b*x;x=nx;y=ny;z=.16*Math.sin(x+y)}
else if(source==='tinkerbell'){a=.9+g0[0]*.08;b=-.6+g0[1]*.07;c=2+g1[0]*.12;d=.5+g1[1]*.06;nx=x*x-y*y+a*x+b*y;ny=2*x*y+c*x+d*y;x=soft(nx,4);y=soft(ny,4);z=.12*Math.sin(x*y)}
else if(source==='gumowski'){a=g0[0]*.035;b=g0[1]*.04;c=.5+g1[0]*.07;fx=function(q){return a*q+2*(1-a)*q*q/(1+q*q)};nx=y+b*(1-c*y*y)*y+fx(x);ny=-x+fx(nx);x=soft(nx,5);y=soft(ny,5);z=.15*Math.sin(x)}
else if(source==='duffing'){dt=.025;a=.23+g0[0]*.03;b=.3+g0[1]*.05;c=1+g1[0]*.06;v+=(-a*v+x-x*x*x+b*Math.cos(c*t))*dt;x+=v*dt;y=v;t+=dt;z=.16*Math.sin(t)}
else if(source==='chua'){dt=.006;a=10+g0[0];b=16+g0[1]*2;fx=-.714*x+.5*(-1.143+.714)*(Math.abs(x+1)-Math.abs(x-1));nx=x+dt*(a*(y-x-fx));ny=y+dt*(x-y+z);nz=z+dt*(-b*y);x=nx;y=ny;z=nz;return finish(x,y,z*.7)}
else if(source==='sna'){gr=(Math.sqrt(5)-1)/2;a=.72+g0[0]*.05;b=.38+g0[1]*.08;nx=a*x*(1-x)+b*Math.cos(th);th+=Math.PI*2*gr;y=Math.sin(th)*x;x=nx;z=.15*Math.cos(th);x=x*2-1}
else{nx=Math.sin((1.35+g0[0]*.4)*y)+(.5+g0[1]*.25)*Math.cos((1.15+g1[0]*.3)*x)+.25*Math.sin(x*y*(1.8+g1[1]*.2));ny=Math.sin((1.2+g1[1]*.35)*x)+(.42+g0[3]*.2)*Math.cos((1.08+g1[3]*.25)*y)+.2*Math.sin(x-y);x=soft(nx,4);y=soft(ny,4);z=.28*Math.sin(x*y)}return finish(x,y,z);function finish(xx,yy,zz){var e=eqCarrier(xx,yy,zz);return [soft(xx+e[0],5),soft(yy+e[1],5),soft(zz+e[2],4)]}}}
