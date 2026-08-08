/*
 * Growth Canvas — reduced Growing Polarised Tissue (GPT) style growth engine.
 * Vanilla ES module, no dependencies.
 *
 * Scientific model: Kennaway, Coen, Green & Bangham (2011), PLoS Comput Biol
 * 7(6):e1002071. This is a deliberately small 2-D implementation: growth is
 * encoded as an incremental eigenstrain, then neighbouring elements negotiate
 * a compatible resultant displacement through linear elastic FEM. Large
 * deformations are accumulated as many small linear steps (paper §Methods:
 * deformation/growth), never by a large-strain solver.
 */

const EPS = 1e-12;
const DEG = Math.PI / 180;

function clamp(x, a, b) { return x < a ? a : x > b ? b : x; }
function edgeKey(a, b) { return a < b ? `${a},${b}` : `${b},${a}`; }
function now() { return typeof performance !== 'undefined' ? performance.now() : Date.now(); }

/** Small deterministic RNG for reproducible topology tie-breaking. */
function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function signedArea2(pos, a, b, c) {
  const ax = pos[2*a], ay = pos[2*a+1];
  const bx = pos[2*b], by = pos[2*b+1];
  const cx = pos[2*c], cy = pos[2*c+1];
  return (bx-ax)*(cy-ay) - (by-ay)*(cx-ax);
}

function triAspect(pos, a, b, c) {
  const ax=pos[2*a], ay=pos[2*a+1], bx=pos[2*b], by=pos[2*b+1], cx=pos[2*c], cy=pos[2*c+1];
  const l0=(ax-bx)**2+(ay-by)**2, l1=(bx-cx)**2+(by-cy)**2, l2=(cx-ax)**2+(cy-ay)**2;
  const lmax=Math.max(l0,l1,l2);
  const A2=Math.abs((bx-ax)*(cy-ay)-(by-ay)*(cx-ax));
  // longest edge / corresponding altitude = L^2 / (2A) = L^2 / A2.
  return A2 > EPS ? lmax / A2 : Infinity;
}

function barycentric(px, py, ax, ay, bx, by, cx, cy) {
  const den=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy);
  if (Math.abs(den)<EPS) return null;
  const w0=((by-cy)*(px-cx)+(cx-bx)*(py-cy))/den;
  const w1=((cy-ay)*(px-cx)+(ax-cx)*(py-cy))/den;
  const w2=1-w0-w1;
  return (w0>=-1e-9 && w1>=-1e-9 && w2>=-1e-9) ? [w0,w1,w2] : null;
}

export class GrowthCanvas {
  constructor(options={}) {
    this.options = {
      shape: options.shape || 'petal',
      resolution: Math.max(4, options.resolution || 24),
      poisson: 0.3,                 // GPT: material constants barely affect growth; fixed by brief.
      young: 1.0,
      retainResidual: clamp(options.retainResidual ?? 0, 0, 1),
      shallowGradient: options.shallowGradient || 'freeze',
      maxGrowthPerStep: options.maxGrowthPerStep ?? 0.10,
      maxRotationPerStep: options.maxRotationPerStep ?? 10,
      seed: options.seed ?? 12345
    };
    if (!['sources','freeze','isotropic'].includes(this.options.shallowGradient)) {
      throw new Error("shallowGradient must be 'sources', 'freeze', or 'isotropic'");
    }
    this._rng = mulberry32(this.options.seed);
    this.time = 0;
    this._steps = 0;
    this._remeshes = 0;
    this._ms = 0;
    this._fields = new Map();
    this._organisers = { plusFn:null, minusFn:null };
    this._hasOrganisers = false;
    this._buildInitialMesh();
    this._plusMask = new Uint8Array(this.n);
    this._minusMask = new Uint8Array(this.n);
    this._polSignal = new Float64Array(this.n); this._polSignal.fill(0.5);
    this._frozenPol = new Float64Array(2*this.n);
    this._frozenMask = new Uint8Array(this.n);
    this._lastPol = new Float64Array(2*this.n);
    for (let i=0;i<this.n;i++) { this._lastPol[2*i]=0; this._lastPol[2*i+1]=1; }
    this._lastDisp = new Float64Array(2*this.n);
    this._lastDt = 1;
    this._resultant = new Float64Array(4*this.n); // mean rate, anisotropy, angle, principal2
    this._residual = new Float64Array(3*this.nt);
    this._growthEvalPar = new Float64Array(this.n);
    this._growthEvalPer = new Float64Array(this.n);
    this._rebuildTopology();
    this._initialEdge = this._medianEdgeLength();
    this._initialArea = this.area();
    this._lowerEdge = 1.45 * this._initialEdge;
    this._upperEdge = 1.85 * this._initialEdge;
    this._worldGridDirty = true;
    this._materialGridDirty = true;
  }

  // -------------------------------------------------------------------------
  // Mesh creation. Material coordinates are immutable labels (u,v); current
  // positions start from an undeformed reference embedding of those labels.
  // -------------------------------------------------------------------------
  _buildInitialMesh() {
    const r=this.options.resolution;
    const nu=r, nv=r;
    const pos=[], mat=[];
    const shape=this.options.shape;
    const halfWidth = (u) => {
      if (shape==='square') return 0.5;
      if (shape==='disc') {
        // A smooth lens-like disc embedding. A tiny finite pole width avoids the
        // degenerate fan triangles produced by sampling an exact circle on a
        // rectangular (u,v) lattice.
        return 0.15 + 0.35*Math.sin(Math.PI*clamp(u,0,1));
      }
      // Petal: a narrow but finite attachment and a broad smooth blade. Using
      // a C1 width profile keeps the initial finite elements below the 10:1
      // conditioning limit instead of creating skinny triangles at the poles.
      const s=Math.sin(Math.PI*clamp(u,0,1));
      return 0.20 + 0.40*s*(0.88+0.12*u);
    };
    for(let i=0;i<nu;i++) {
      const u=i/(nu-1);
      const hw=halfWidth(u);
      for(let j=0;j<nv;j++) {
        const v=-1+2*j/(nv-1);
        mat.push(u,v);
        pos.push(v*hw, shape==='square' ? u-0.5 : u);
      }
    }
    const tri=[];
    for(let i=0;i<nu-1;i++) for(let j=0;j<nv-1;j++) {
      const a=i*nv+j, b=a+1, c=(i+1)*nv+j, d=c+1;
      // Alternate diagonal to avoid a persistent directional bias.
      if (((i+j)&1)===0) { tri.push(a,b,d, a,d,c); }
      else { tri.push(a,b,c, b,d,c); }
    }
    this.pos=new Float64Array(pos);
    this.mat=new Float64Array(mat);
    this.tri=new Int32Array(tri);
    this.n=pos.length/2;
    this.nt=tri.length/3;
  }

  addField(name, spec={}) {
    if (this._fields.has(name)) throw new Error(`Field '${name}' already exists`);
    const type=spec.type;
    if (type!=='identity' && type!=='signal') throw new Error("field type must be 'identity' or 'signal'");
    const values=new Float64Array(this.n);
    const init=spec.init || (()=>0);
    for(let i=0;i<this.n;i++) values[i]=Number(init(this.mat[2*i],this.mat[2*i+1]))||0;
    this._fields.set(name, {
      name, type,
      diffusion: type==='signal' ? Math.max(0,spec.diffusion||0) : 0,
      decay: type==='signal' ? Math.max(0,spec.decay||0) : 0,
      dilutable: type==='signal' ? spec.dilutable!==false : false,
      values
    });
    return this;
  }

  getField(name) {
    const f=this._fields.get(name); if(!f) throw new Error(`Unknown field '${name}'`);
    return f.values;
  }

  setField(name, arrayOrFn) {
    const f=this._fields.get(name); if(!f) throw new Error(`Unknown field '${name}'`);
    if (typeof arrayOrFn==='function') {
      for(let i=0;i<this.n;i++) f.values[i]=Number(arrayOrFn(this.mat[2*i],this.mat[2*i+1],this._fieldView(i)))||0;
    } else {
      if (!arrayOrFn || arrayOrFn.length!==this.n) throw new Error(`Field '${name}' requires ${this.n} values`);
      f.values.set(arrayOrFn);
    }
    return this;
  }

  _fieldView(i) {
    // Reused mutable view: growth callbacks receive current scalar field values
    // without allocating one object per vertex in the hot evaluation loop.
    const o=this._fieldScratch||(this._fieldScratch=Object.create(null));
    for(const [name,f] of this._fields) o[name]=f.values[i];
    o.POL=this._polSignal[i];
    return o;
  }

  // -------------------------------------------------------------------------
  // Operator-split signalling diffusion (paper: growth and diffusion are
  // solved separately over short increments). Explicit graph diffusion is
  // sub-stepped for stability. Dilution is NOT mixed into this pass.
  // -------------------------------------------------------------------------
  diffuse(dt) {
    if (!(dt>0)) return;
    for (const f of this._fields.values()) if (f.type==='signal' && (f.diffusion>0 || f.decay>0)) {
      this._diffuseArray(f.values, dt, f.diffusion, f.decay, null, null);
    }
    // POL is an internal signalling factor with organisers acting as Dirichlet
    // + (1) and - (0) organisers.
    if (this._hasOrganisers) {
      this._diffuseArray(this._polSignal, dt, 0.18, 0, this._plusMask, this._minusMask);
    }
  }

  _diffuseArray(values, dt, D, decay, plusMask, minusMask) {
    const minL=this._minEdgeLength();
    const stable = D>0 ? 0.12*minL*minL/(D+EPS) : dt;
    const sub=Math.max(1,Math.ceil(dt/Math.max(stable,1e-6)));
    const h=dt/sub;
    if (!this._diffScratch || this._diffScratch.length!==this.n) this._diffScratch=new Float64Array(this.n);
    const tmp=this._diffScratch;
    for(let s=0;s<sub;s++) {
      for(let i=0;i<this.n;i++) {
        if (plusMask && plusMask[i]) { tmp[i]=1; continue; }
        if (minusMask && minusMask[i]) { tmp[i]=0; continue; }
        let sum=0, wsum=0;
        const a=this._nbrOff[i], b=this._nbrOff[i+1];
        const xi=this.pos[2*i], yi=this.pos[2*i+1];
        for(let q=a;q<b;q++) {
          const j=this._nbr[q];
          const dx=this.pos[2*j]-xi, dy=this.pos[2*j+1]-yi;
          const w=1/(dx*dx+dy*dy+1e-12);
          sum += w*(values[j]-values[i]); wsum += w;
        }
        // Normalised weighted graph Laplacian. D controls physical response;
        // normalisation keeps explicit stepping predictable on irregular mesh.
        const lap = wsum>0 ? sum/wsum/(minL*minL+EPS) : 0;
        tmp[i]=values[i] + h*(D*lap - decay*values[i]);
      }
      values.set(tmp);
      if (plusMask) for(let i=0;i<this.n;i++) if(plusMask[i]) values[i]=1;
      if (minusMask) for(let i=0;i<this.n;i++) if(minusMask[i]) values[i]=0;
    }
  }

  setOrganisers({plus,minus}) {
    this._organisers.plusFn=plus||(()=>false);
    this._organisers.minusFn=minus||(()=>false);
    this._hasOrganisers = true;
    this._plusMask=new Uint8Array(this.n); this._minusMask=new Uint8Array(this.n);
    for(let i=0;i<this.n;i++) {
      const u=this.mat[2*i], v=this.mat[2*i+1];
      this._plusMask[i]=this._organisers.plusFn(u,v)?1:0;
      this._minusMask[i]=this._organisers.minusFn(u,v)?1:0;
      this._polSignal[i]=this._plusMask[i]?1:this._minusMask[i]?0:0.5;
    }
    // Establish a usable initial POL field by harmonic relaxation. Thereafter
    // normal diffuse(dt) updates it on the changing geometry.
    this._relaxPOL(100);
    this._frozenMask.fill(0);
    this.polarity();
    return this;
  }

  _relaxPOL(iterations) {
    if (!this._polRelax || this._polRelax.length!==this.n) this._polRelax=new Float64Array(this.n);
    const tmp=this._polRelax;
    for(let it=0;it<iterations;it++) {
      for(let i=0;i<this.n;i++) {
        if(this._plusMask[i]) { tmp[i]=1; continue; }
        if(this._minusMask[i]) { tmp[i]=0; continue; }
        let sum=0,w=0;
        for(let q=this._nbrOff[i];q<this._nbrOff[i+1];q++) {
          const j=this._nbr[q];
          const dx=this.pos[2*j]-this.pos[2*i], dy=this.pos[2*j+1]-this.pos[2*i+1];
          const ww=1/(Math.sqrt(dx*dx+dy*dy)+1e-9);
          sum+=ww*this._polSignal[j]; w+=ww;
        }
        tmp[i]=w?sum/w:this._polSignal[i];
      }
      this._polSignal.set(tmp);
    }
  }

  // Local POL gradient from linear triangular shape functions; averaged to
  // vertices. This is GPT polarity-based axiality: orientation comes from a
  // molecular signal gradient, independently of growth rate or stress.
  polarity() {
    // No organisers means no molecular axis. Returning zero vectors is
    // important: anisotropy is not allowed to appear from an arbitrary global
    // direction when the biology supplied no polarity cue.
    let hasOrg=false;
    for(let i=0;i<this.n;i++) if(this._plusMask[i]||this._minusMask[i]) { hasOrg=true; break; }
    if(!hasOrg) return new Float64Array(2*this.n);
    if (!this._polScratch || this._polScratch.length!==2*this.n) {
      this._polScratch=new Float64Array(2*this.n);
      this._polWeight=new Float64Array(this.n);
    }
    const out=this._polScratch, wt=this._polWeight; out.fill(0); wt.fill(0);
    let maxMag=0;
    for(let t=0;t<this.nt;t++) {
      const a=this.tri[3*t],b=this.tri[3*t+1],c=this.tri[3*t+2];
      const ax=this.pos[2*a],ay=this.pos[2*a+1], bx=this.pos[2*b],by=this.pos[2*b+1], cx=this.pos[2*c],cy=this.pos[2*c+1];
      const A2=(bx-ax)*(cy-ay)-(by-ay)*(cx-ax); if(Math.abs(A2)<EPS) continue;
      const gx0=(by-cy)/A2, gy0=(cx-bx)/A2;
      const gx1=(cy-ay)/A2, gy1=(ax-cx)/A2;
      const gx2=(ay-by)/A2, gy2=(bx-ax)/A2;
      const pa=this._polSignal[a],pb=this._polSignal[b],pc=this._polSignal[c];
      const gx=pa*gx0+pb*gx1+pc*gx2, gy=pa*gy0+pb*gy1+pc*gy2;
      const area=0.5*Math.abs(A2), m=Math.hypot(gx,gy); maxMag=Math.max(maxMag,m);
      out[2*a]+=gx*area; out[2*a+1]+=gy*area; wt[a]+=area;
      out[2*b]+=gx*area; out[2*b+1]+=gy*area; wt[b]+=area;
      out[2*c]+=gx*area; out[2*c+1]+=gy*area; wt[c]+=area;
    }
    const threshold=Math.max(1e-8, maxMag*0.025);
    for(let i=0;i<this.n;i++) {
      let gx=wt[i]?out[2*i]/wt[i]:0, gy=wt[i]?out[2*i+1]/wt[i]:0;
      let m=Math.hypot(gx,gy);
      if(m>=threshold) {
        gx/=m; gy/=m;
        this._lastPol[2*i]=gx; this._lastPol[2*i+1]=gy;
        if(!this._frozenMask[i]) { this._frozenPol[2*i]=gx; this._frozenPol[2*i+1]=gy; }
      } else if(this.options.shallowGradient==='freeze') {
        // Published shallow-gradient workaround: once signal orientation becomes
        // unreadably flat, lock it to tissue and convect it with deformation.
        if(!this._frozenMask[i]) {
          this._frozenMask[i]=1;
          this._frozenPol[2*i]=this._lastPol[2*i]; this._frozenPol[2*i+1]=this._lastPol[2*i+1];
        }
        gx=this._frozenPol[2*i]; gy=this._frozenPol[2*i+1];
      } else if(this.options.shallowGradient==='isotropic') {
        gx=0; gy=0;
      } else { // 'sources': organiser masks are extended to newborn tissue on remesh.
        gx=this._lastPol[2*i]; gy=this._lastPol[2*i+1];
      }
      out[2*i]=gx; out[2*i+1]=gy;
    }
    return out; // Typed-array view; callers should treat it as read-only until the next polarity() call.
  }

  // -------------------------------------------------------------------------
  // Growth step. Order follows the brief exactly: evaluate rates, diffuse,
  // construct eigenstrain, FEM solve, dilute, residual handling, time/remesh.
  // If a bound is exceeded the whole attempt is rolled back and dt is halved.
  // -------------------------------------------------------------------------
  step(dt, growth) {
    if (!(dt>0)) throw new Error('dt must be > 0');
    const start=now();
    let h=dt;
    for(let retry=0;retry<20;retry++) {
      const backup=this._backupForRetry();
      this._evaluateGrowth(growth.kpar,growth.kper);
      let maxSpec=0;
      for(let i=0;i<this.n;i++) maxSpec=Math.max(maxSpec,Math.abs(this._growthEvalPar[i]*h),Math.abs(this._growthEvalPer[i]*h));
      if(maxSpec>this.options.maxGrowthPerStep) { this._restoreRetry(backup); h*=0.5; continue; }
      this.diffuse(h);
      const pol=this.polarity();
      const oldPos=new Float64Array(this.pos);
      const oldVA=this._vertexAreas(oldPos);
      const solve=this._elasticIncrement(h,pol);
      if(!solve.ok) { this._restoreRetry(backup); h*=0.5; continue; }
      const maxRot=this._measureMaxRotation(oldPos,this.pos);
      const newVA=this._vertexAreas(this.pos);
      let maxAreal=0;
      for(let i=0;i<this.n;i++) maxAreal=Math.max(maxAreal,Math.abs(newVA[i]/Math.max(oldVA[i],EPS)-1));
      if(maxAreal>this.options.maxGrowthPerStep+1e-8 || maxRot>this.options.maxRotationPerStep*DEG+1e-9) {
        this._restoreRetry(backup); h*=0.5; continue;
      }
      // Dilution is explicitly its own pass after mechanics (paper workaround).
      for(const f of this._fields.values()) if(f.type==='signal' && f.dilutable) {
        for(let i=0;i<this.n;i++) f.values[i] /= Math.max(newVA[i]/Math.max(oldVA[i],EPS),1e-9);
      }
      // Convect already-frozen polarity directions with the resultant deformation.
      this._convectFrozenPolarity(oldPos,this.pos);
      this.time += h; this._steps++; this._lastDt=h; this._lastDisp=solve.disp;
      this._computeResultantGrowth(oldPos,this.pos,h);
      this._worldGridDirty=true;
      this._maybeRemesh();
      this._ms += now()-start;
      return h;
    }
    throw new Error('Adaptive timestep collapsed after 20 retries');
  }

  grow(totalTime, growth) {
    if (!(totalTime>=0)) throw new Error('totalTime must be >= 0');
    let remaining=totalTime;
    let base=(growth && growth.dt) || Math.min(0.08, Math.max(0.002,totalTime/25 || 0.02));
    while(remaining>1e-12) {
      const accepted=this.step(Math.min(base,remaining),growth);
      remaining-=accepted;
      // if adaptive controller had to cut strongly, stay near that stable scale;
      // otherwise allow a modest recovery.
      base=Math.min(base,accepted*1.35);
    }
    return this;
  }

  _evaluateGrowth(kpar,kper) {
    const evalOne=(src,out) => {
      if(typeof src==='function') for(let i=0;i<this.n;i++) out[i]=Number(src(this.mat[2*i],this.mat[2*i+1],this._fieldView(i)))||0;
      else { if(!src || src.length!==this.n) throw new Error(`growth array must have ${this.n} values`); out.set(src); }
    };
    evalOne(kpar,this._growthEvalPar); evalOne(kper,this._growthEvalPer);
  }

  _elasticIncrement(dt,pol) {
    this._assembleStiffnessAndLoad(dt,pol);
    const nd=2*this.n;
    if(!this._cgX || this._cgX.length!==nd) {
      this._cgX=new Float64Array(nd); this._cgR=new Float64Array(nd); this._cgP=new Float64Array(nd); this._cgAp=new Float64Array(nd);
    }
    const x=this._cgX; x.fill(0);
    const ok=this._cgSolve(this._rhs,x,Math.max(80,Math.min(350,Math.floor(12*Math.sqrt(nd)))),1e-9);
    if(!ok) return {ok:false,disp:new Float64Array(nd)};
    this._removeRigidIncrement(x);
    const old=new Float64Array(this.pos);
    for(let i=0;i<nd;i++) this.pos[i]+=x[i];
    for(let t=0;t<this.nt;t++) if(signedArea2(this.pos,this.tri[3*t],this.tri[3*t+1],this.tri[3*t+2])<=EPS) {
      this.pos.set(old); return {ok:false,disp:new Float64Array(nd)};
    }
    return {ok:true,disp:new Float64Array(x)};
  }

  _assembleStiffnessAndLoad(dt,pol) {
    this._Kval.fill(0); this._rhs.fill(0);
    const nu=0.3, E=1.0;
    const c=E/(1-nu*nu);
    // Plane-stress constitutive matrix. GPT notes E cancels and nu has weak
    // influence because all loads are internally generated; both are fixed.
    const D00=c,D01=c*nu,D11=c,D22=c*(1-nu)/2;
    const B=this._Bscratch||(this._Bscratch=new Float64Array(18));
    const DB=this._DBscratch||(this._DBscratch=new Float64Array(18));
    const ke=this._KeScratch||(this._KeScratch=new Float64Array(36));
    const fe=this._FeScratch||(this._FeScratch=new Float64Array(6));
    const ids=this._id6Scratch||(this._id6Scratch=new Int32Array(6));
    for(let t=0;t<this.nt;t++) {
      const ia=this.tri[3*t],ib=this.tri[3*t+1],ic=this.tri[3*t+2];
      const ax=this.pos[2*ia],ay=this.pos[2*ia+1], bx=this.pos[2*ib],by=this.pos[2*ib+1], cx=this.pos[2*ic],cy=this.pos[2*ic+1];
      const A2=(bx-ax)*(cy-ay)-(by-ay)*(cx-ax); if(A2<=EPS) continue;
      const A=0.5*A2;
      const gx0=(by-cy)/A2,gx1=(cy-ay)/A2,gx2=(ay-by)/A2;
      const gy0=(cx-bx)/A2,gy1=(ax-cx)/A2,gy2=(bx-ax)/A2;
      B.fill(0);
      B[0]=gx0;B[7]=gy0;B[12]=gy0;B[13]=gx0;
      B[2]=gx1;B[9]=gy1;B[14]=gy1;B[15]=gx1;
      B[4]=gx2;B[11]=gy2;B[16]=gy2;B[17]=gx2;
      // DB = D * B (3x6 stored row-major by row chunks of 6).
      for(let j=0;j<6;j++) {
        DB[j]=D00*B[j]+D01*B[6+j];
        DB[6+j]=D01*B[j]+D11*B[6+j];
        DB[12+j]=D22*B[12+j];
      }
      ke.fill(0);
      for(let i=0;i<6;i++) for(let j=0;j<6;j++) ke[6*i+j]=A*(B[i]*DB[j]+B[6+i]*DB[6+j]+B[12+i]*DB[12+j]);
      let p0=(pol[2*ia]+pol[2*ib]+pol[2*ic])/3,p1=(pol[2*ia+1]+pol[2*ib+1]+pol[2*ic+1])/3;
      let kpa=(this._growthEvalPar[ia]+this._growthEvalPar[ib]+this._growthEvalPar[ic])/3;
      let kpe=(this._growthEvalPer[ia]+this._growthEvalPer[ib]+this._growthEvalPer[ic])/3;
      const pm=Math.hypot(p0,p1);
      let exx,eyy,exy;
      if(pm<1e-8) {
        const k=0.5*(kpa+kpe)*dt; exx=k;eyy=k;exy=0;
      } else {
        p0/=pm;p1/=pm; const q0=-p1,q1=p0;
        // Specified growth is an eigenstrain: eps_g = dt*(kpar pp^T + kper qq^T).
        // FEM solves B u ~= eps_g subject to neighbour compatibility; curvature
        // and resultant anisotropy therefore emerge from conflict, not commands.
        exx=dt*(kpa*p0*p0+kpe*q0*q0);
        eyy=dt*(kpa*p1*p1+kpe*q1*q1);
        exy=dt*(kpa*p0*p1+kpe*q0*q1);
      }
      // Residual growth mismatch can be retained for later contact-like uses.
      // Default 0 implements GPT "snip and fill": unresolved stress is discarded.
      exx += this.options.retainResidual*this._residual[3*t];
      eyy += this.options.retainResidual*this._residual[3*t+1];
      exy += this.options.retainResidual*this._residual[3*t+2];
      const eg0=exx,eg1=eyy,eg2=2*exy; // engineering shear component gamma_xy.
      const sg0=D00*eg0+D01*eg1, sg1=D01*eg0+D11*eg1, sg2=D22*eg2;
      for(let i=0;i<6;i++) fe[i]=A*(B[i]*sg0+B[6+i]*sg1+B[12+i]*sg2);
      ids[0]=2*ia;ids[1]=2*ia+1;ids[2]=2*ib;ids[3]=2*ib+1;ids[4]=2*ic;ids[5]=2*ic+1;
      for(let i=0;i<6;i++) {
        this._rhs[ids[i]]+=fe[i];
        const base=36*t+6*i;
        for(let j=0;j<6;j++) this._Kval[this._triKIndex[base+j]]+=ke[6*i+j];
      }
      // residual updated after solve in _updateResidualFromIncrement.
      this._targetStrain[3*t]=eg0; this._targetStrain[3*t+1]=eg1; this._targetStrain[3*t+2]=exy;
    }
  }

  _cgSolve(b,x,maxIter,tol) {
    const r=this._cgR,p=this._cgP,Ap=this._cgAp;
    r.set(b); p.set(r);
    let rr=0,bn=0; for(let i=0;i<b.length;i++){rr+=r[i]*r[i];bn+=b[i]*b[i];}
    if(bn<EPS) return true;
    const target=tol*tol*bn;
    for(let it=0;it<maxIter;it++) {
      this._matVec(p,Ap);
      let pAp=0; for(let i=0;i<b.length;i++) pAp+=p[i]*Ap[i];
      if(Math.abs(pAp)<1e-24) return rr<1e-14*bn;
      const a=rr/pAp;
      for(let i=0;i<b.length;i++){x[i]+=a*p[i];r[i]-=a*Ap[i];}
      let rr2=0; for(let i=0;i<b.length;i++) rr2+=r[i]*r[i];
      if(rr2<=target) return true;
      const beta=rr2/rr; for(let i=0;i<b.length;i++) p[i]=r[i]+beta*p[i];
      rr=rr2;
    }
    return rr<1e-6*bn;
  }

  _matVec(x,y) {
    y.fill(0);
    for(let i=0;i<2*this.n;i++) {
      let s=0; for(let q=this._Krow[i];q<this._Krow[i+1];q++) s+=this._Kval[q]*x[this._Kcol[q]];
      y[i]=s;
    }
  }

  _removeRigidIncrement(d) {
    let mx=0,my=0,cx=0,cy=0;
    for(let i=0;i<this.n;i++){mx+=d[2*i];my+=d[2*i+1];cx+=this.pos[2*i];cy+=this.pos[2*i+1];}
    mx/=this.n;my/=this.n;cx/=this.n;cy/=this.n;
    let num=0,den=0;
    for(let i=0;i<this.n;i++) {
      const rx=this.pos[2*i]-cx, ry=this.pos[2*i+1]-cy;
      const ux=d[2*i]-mx, uy=d[2*i+1]-my;
      num += rx*uy-ry*ux; den += rx*rx+ry*ry;
    }
    const w=den>EPS?num/den:0;
    for(let i=0;i<this.n;i++) {
      const rx=this.pos[2*i]-cx, ry=this.pos[2*i+1]-cy;
      d[2*i]-=mx-w*ry; d[2*i+1]-=my+w*rx;
    }
  }

  _updateResidualFromIncrement(oldPos,newPos) {
    if(this.options.retainResidual<=0) { this._residual.fill(0); return; }
    for(let t=0;t<this.nt;t++) {
      const a=this.tri[3*t],b=this.tri[3*t+1],c=this.tri[3*t+2];
      const ax=oldPos[2*a],ay=oldPos[2*a+1], bx=oldPos[2*b],by=oldPos[2*b+1], cx=oldPos[2*c],cy=oldPos[2*c+1];
      const A2=(bx-ax)*(cy-ay)-(by-ay)*(cx-ax); if(Math.abs(A2)<EPS) continue;
      const gx=[(by-cy)/A2,(cy-ay)/A2,(ay-by)/A2], gy=[(cx-bx)/A2,(ax-cx)/A2,(bx-ax)/A2];
      let dux=0,duy=0,dvx=0,dvy=0;
      for(let q=0;q<3;q++) {
        const i=[a,b,c][q], ux=newPos[2*i]-oldPos[2*i], uy=newPos[2*i+1]-oldPos[2*i+1];
        dux+=ux*gx[q];duy+=ux*gy[q];dvx+=uy*gx[q];dvy+=uy*gy[q];
      }
      const exx=dux, eyy=dvy, exy=0.5*(duy+dvx);
      this._residual[3*t]=this._targetStrain[3*t]-exx;
      this._residual[3*t+1]=this._targetStrain[3*t+1]-eyy;
      this._residual[3*t+2]=this._targetStrain[3*t+2]-exy;
    }
  }

  _measureMaxRotation(oldPos,newPos) {
    let m=0;
    for(let t=0;t<this.nt;t++) {
      const a=this.tri[3*t],b=this.tri[3*t+1],c=this.tri[3*t+2];
      const X0=oldPos[2*a],Y0=oldPos[2*a+1], X1=oldPos[2*b],Y1=oldPos[2*b+1], X2=oldPos[2*c],Y2=oldPos[2*c+1];
      const x0=newPos[2*a],y0=newPos[2*a+1], x1=newPos[2*b],y1=newPos[2*b+1], x2=newPos[2*c],y2=newPos[2*c+1];
      const A00=X1-X0,A01=X2-X0,A10=Y1-Y0,A11=Y2-Y0, det=A00*A11-A01*A10; if(Math.abs(det)<EPS) continue;
      const i00=A11/det,i01=-A01/det,i10=-A10/det,i11=A00/det;
      const b00=x1-x0,b01=x2-x0,b10=y1-y0,b11=y2-y0;
      const F00=b00*i00+b01*i10,F01=b00*i01+b01*i11,F10=b10*i00+b11*i10,F11=b10*i01+b11*i11;
      const ang=Math.abs(Math.atan2(F10-F01,F00+F11)); m=Math.max(m,ang);
    }
    this._updateResidualFromIncrement(oldPos,newPos);
    return m;
  }

  _convectFrozenPolarity(oldPos,newPos) {
    if(!this._frozenMask.some?.(x=>x)) {
      let any=false; for(let i=0;i<this.n;i++) if(this._frozenMask[i]){any=true;break;} if(!any) return;
    }
    const acc=new Float64Array(2*this.n), wt=new Float64Array(this.n);
    for(let t=0;t<this.nt;t++) {
      const a=this.tri[3*t],b=this.tri[3*t+1],c=this.tri[3*t+2];
      const X0=oldPos[2*a],Y0=oldPos[2*a+1], X1=oldPos[2*b],Y1=oldPos[2*b+1], X2=oldPos[2*c],Y2=oldPos[2*c+1];
      const x0=newPos[2*a],y0=newPos[2*a+1], x1=newPos[2*b],y1=newPos[2*b+1], x2=newPos[2*c],y2=newPos[2*c+1];
      const A00=X1-X0,A01=X2-X0,A10=Y1-Y0,A11=Y2-Y0, det=A00*A11-A01*A10;if(Math.abs(det)<EPS)continue;
      const i00=A11/det,i01=-A01/det,i10=-A10/det,i11=A00/det;
      const b00=x1-x0,b01=x2-x0,b10=y1-y0,b11=y2-y0;
      const F00=b00*i00+b01*i10,F01=b00*i01+b01*i11,F10=b10*i00+b11*i10,F11=b10*i01+b11*i11;
      for(const i of [a,b,c]) if(this._frozenMask[i]) {
        const px=this._frozenPol[2*i],py=this._frozenPol[2*i+1];
        acc[2*i]+=F00*px+F01*py;acc[2*i+1]+=F10*px+F11*py;wt[i]++;
      }
    }
    for(let i=0;i<this.n;i++) if(this._frozenMask[i]&&wt[i]) {
      let x=acc[2*i]/wt[i],y=acc[2*i+1]/wt[i],m=Math.hypot(x,y);if(m>EPS){x/=m;y/=m;this._frozenPol[2*i]=x;this._frozenPol[2*i+1]=y;this._lastPol[2*i]=x;this._lastPol[2*i+1]=y;}
    }
  }

  _computeResultantGrowth(oldPos,newPos,dt) {
    this._resultant=new Float64Array(4*this.n); const wt=new Float64Array(this.n);
    for(let t=0;t<this.nt;t++) {
      const ids=[this.tri[3*t],this.tri[3*t+1],this.tri[3*t+2]], a=ids[0],b=ids[1],c=ids[2];
      const ax=oldPos[2*a],ay=oldPos[2*a+1],bx=oldPos[2*b],by=oldPos[2*b+1],cx=oldPos[2*c],cy=oldPos[2*c+1];
      const A2=(bx-ax)*(cy-ay)-(by-ay)*(cx-ax);if(Math.abs(A2)<EPS)continue;
      const gx=[(by-cy)/A2,(cy-ay)/A2,(ay-by)/A2],gy=[(cx-bx)/A2,(ax-cx)/A2,(bx-ax)/A2];
      let L00=0,L01=0,L10=0,L11=0;
      for(let q=0;q<3;q++) {const i=ids[q],vx=(newPos[2*i]-oldPos[2*i])/dt,vy=(newPos[2*i+1]-oldPos[2*i+1])/dt;L00+=vx*gx[q];L01+=vx*gy[q];L10+=vy*gx[q];L11+=vy*gy[q];}
      const s00=L00,s11=L11,s01=0.5*(L01+L10), tr=0.5*(s00+s11), d=Math.sqrt((0.5*(s00-s11))**2+s01*s01);
      const l1=tr+d,l2=tr-d, ang=0.5*Math.atan2(2*s01,s00-s11), area=0.5*Math.abs(A2);
      for(const i of ids){this._resultant[4*i]+=(l1+l2)*area;this._resultant[4*i+1]+=(l1-l2)*area;this._resultant[4*i+2]+=ang*area;this._resultant[4*i+3]+=l2*area;wt[i]+=area;}
    }
    for(let i=0;i<this.n;i++) if(wt[i]) for(let k=0;k<4;k++) this._resultant[4*i+k]/=wt[i];
  }

  resultantGrowth() {
    const out=new Array(this.n);
    for(let i=0;i<this.n;i++) {
      const rate=this._resultant[4*i], an=this._resultant[4*i+1], angle=this._resultant[4*i+2], l2=this._resultant[4*i+3];
      out[i]={rate,anisotropy:an,angle,principal:[l2+an,l2]};
    }
    return out;
  }

  // -------------------------------------------------------------------------
  // Remeshing: published two-threshold batch split. If any edge breaches the
  // upper threshold, EVERY edge over the lower threshold is marked before any
  // topology change. New samples use interpolating butterfly weights; fields
  // and material coordinates use the identical stencil.
  // -------------------------------------------------------------------------
  _maybeRemesh() {
    // Thresholds scale with sqrt(total area): uniform enlargement should not
    // recursively refine the whole sheet. Distortion relative to that global
    // scale still triggers splitting, which keeps the requested small mesh
    // budget while controlling anisotropic element quality.
    const scale=Math.sqrt(Math.max(this.area(),EPS)/Math.max(this._initialArea,EPS));
    this._lowerEdge=1.45*this._initialEdge*scale;
    this._upperEdge=1.85*this._initialEdge*scale;
    let trigger=false; const marked=[];
    for(const e of this._edges) {
      const dx=this.pos[2*e.a]-this.pos[2*e.b],dy=this.pos[2*e.a+1]-this.pos[2*e.b+1],L=Math.hypot(dx,dy);
      if(L>this._upperEdge) trigger=true;
      if(L>this._lowerEdge) marked.push(e);
    }
    let did=false;
    if(trigger && marked.length) { this._batchSplit(marked); did=true; }
    this._flipThinElements();

    // Edge flips are the first thin-element remedy. If a triangle is still
    // beyond the 10:1 conditioning limit after those local transformations,
    // batch-split the longest edges of all bad elements together. This stays
    // within the same two remeshing mechanisms while avoiding one-at-a-time
    // refinement and the order dependence it creates.
    for(let pass=0;pass<2;pass++) {
      const em=this._buildEdgeMap(), qmarks=new Map(); let worst=0;
      for(let t=0;t<this.nt;t++) {
        const a=this.tri[3*t],b=this.tri[3*t+1],c=this.tri[3*t+2],asp=triAspect(this.pos,a,b,c); worst=Math.max(worst,asp);
        if(asp<=9.25) continue;
        const pairs=[[a,b],[b,c],[c,a]]; let best=pairs[0],bestL=-1;
        for(const pr of pairs){const dx=this.pos[2*pr[0]]-this.pos[2*pr[1]],dy=this.pos[2*pr[0]+1]-this.pos[2*pr[1]+1],l=dx*dx+dy*dy;if(l>bestL){bestL=l;best=pr;}}
        const k=edgeKey(best[0],best[1]),e=em.get(k); if(e) qmarks.set(k,e);
      }
      if(worst<=9.25 || !qmarks.size) break;
      this._batchSplit([...qmarks.values()]); did=true;
      this._flipThinElements();
    }
    if(did) { this._remeshes++; this._worldGridDirty=true;this._materialGridDirty=true; }
    return did;
  }

  _butterflyStencil(edge) {
    const a=edge.a,b=edge.b;
    const terms=new Map([[a,0.5],[b,0.5]]);
    if(edge.t0>=0 && edge.t1>=0) {
      const c=this._oppositeVertex(edge.t0,a,b), d=this._oppositeVertex(edge.t1,a,b);
      terms.set(c,(terms.get(c)||0)+0.125);terms.set(d,(terms.get(d)||0)+0.125);
      const far=[];
      for(const x of [c,d]) {
        for(let q=this._nbrOff[x];q<this._nbrOff[x+1];q++) {
          const j=this._nbr[q]; if(j!==a&&j!==b&&j!==c&&j!==d&&!far.includes(j)) far.push(j);
        }
      }
      // Classic 8-point butterfly has four second-ring vertices at -1/16.
      for(let k=0;k<Math.min(4,far.length);k++) terms.set(far[k],(terms.get(far[k])||0)-0.0625);
      // Normalise in incomplete neighbourhoods without turning it into bisection.
      let s=0;for(const w of terms.values())s+=w;if(Math.abs(s)>EPS)for(const [i,w] of [...terms])terms.set(i,w/s);
    } else {
      // Modified 4-point interpolatory boundary butterfly: 9/16(A+B)-1/16(P+Q).
      terms.set(a,9/16);terms.set(b,9/16);
      const pa=this._boundaryOther(a,b), pb=this._boundaryOther(b,a);
      if(pa!=null) terms.set(pa,(terms.get(pa)||0)-1/16);
      if(pb!=null) terms.set(pb,(terms.get(pb)||0)-1/16);
      let s=0;for(const w of terms.values())s+=w;if(Math.abs(s)>EPS)for(const [i,w] of [...terms])terms.set(i,w/s);
    }
    // In 2-D an unconstrained butterfly point can occasionally overshoot far
    // enough to make a local triangle nearly singular. Keep the interpolating
    // butterfly stencil, but blend it toward the edge midpoint only when its
    // normal displacement exceeds 10% of the edge length. The SAME blended
    // weights are then used for geometry, material coordinates, and fields.
    let sx=0,sy=0; for(const [i,w] of terms){ sx+=w*this.pos[2*i]; sy+=w*this.pos[2*i+1]; }
    const mx=0.5*(this.pos[2*a]+this.pos[2*b]), my=0.5*(this.pos[2*a+1]+this.pos[2*b+1]);
    const L=Math.hypot(this.pos[2*a]-this.pos[2*b],this.pos[2*a+1]-this.pos[2*b+1]);
    const dev=Math.hypot(sx-mx,sy-my), cap=0.10*L;
    if(dev>cap && dev>EPS){ const alpha=cap/dev; for(const [i,w] of [...terms])terms.set(i,w*alpha); terms.set(a,(terms.get(a)||0)+(1-alpha)*0.5); terms.set(b,(terms.get(b)||0)+(1-alpha)*0.5); }
    return terms;
  }

  _interpolateStencil(arr,stride,stencil,k=0) { let v=0;for(const [i,w] of stencil)v+=w*arr[stride*i+k];return v; }

  _batchSplit(marked) {
    const split=new Map(); const oldN=this.n, oldNt=this.nt;
    const pos=Array.from(this.pos),mat=Array.from(this.mat),pol=Array.from(this._polSignal),last=Array.from(this._lastPol),frozen=Array.from(this._frozenPol),fm=Array.from(this._frozenMask),pm=Array.from(this._plusMask),mm=Array.from(this._minusMask),resultant=Array.from(this._resultant),lastDisp=Array.from(this._lastDisp);
    const fieldArrays=new Map(); for(const [name,f] of this._fields) fieldArrays.set(name,Array.from(f.values));
    for(const e of marked) {
      const key=edgeKey(e.a,e.b); if(split.has(key))continue;
      const st=this._butterflyStencil(e), ni=pos.length/2; split.set(key,ni);
      pos.push(this._interpolateStencil(this.pos,2,st,0),this._interpolateStencil(this.pos,2,st,1));
      mat.push(this._interpolateStencil(this.mat,2,st,0),this._interpolateStencil(this.mat,2,st,1));
      pol.push(this._interpolateStencil(this._polSignal,1,st,0));
      let lx=this._interpolateStencil(this._lastPol,2,st,0),ly=this._interpolateStencil(this._lastPol,2,st,1),lm=Math.hypot(lx,ly);if(lm>EPS){lx/=lm;ly/=lm;}last.push(lx,ly);
      let fx=this._interpolateStencil(this._frozenPol,2,st,0),fy=this._interpolateStencil(this._frozenPol,2,st,1),fmag=Math.hypot(fx,fy);if(fmag>EPS){fx/=fmag;fy/=fmag;}frozen.push(fx,fy);
      for(let k=0;k<4;k++) resultant.push(this._interpolateStencil(this._resultant,4,st,k));
      lastDisp.push(this._interpolateStencil(this._lastDisp,2,st,0),this._interpolateStencil(this._lastDisp,2,st,1));
      let freeze=0;for(const [i,w] of st)if(w>0&&this._frozenMask[i])freeze=1;fm.push(freeze);
      const u=mat[2*ni],v=mat[2*ni+1];
      let newPlus, newMinus;
      if(this._organisers.plusFn) newPlus=this._organisers.plusFn(u,v)?1:0;
      else { let z=0; for(const [i,w] of st) z+=w*this._plusMask[i]; newPlus=z>0.5?1:0; }
      if(this._organisers.minusFn) newMinus=this._organisers.minusFn(u,v)?1:0;
      else { let z=0; for(const [i,w] of st) z+=w*this._minusMask[i]; newMinus=z>0.5?1:0; }
      pm.push(newPlus);mm.push(newMinus);
      if(pm[ni])pol[ni]=1;if(mm[ni])pol[ni]=0;
      for(const [name,f] of this._fields){const a=fieldArrays.get(name);let val=0;for(const [i,w]of st)val+=w*f.values[i];a.push(val);}
    }
    const nt=[],parent=[];
    const add=(a,b,c,p)=>{if(signedArea2(new Float64Array(pos),a,b,c)>EPS){nt.push(a,b,c);parent.push(p);}else{nt.push(a,c,b);parent.push(p);}};
    for(let t=0;t<oldNt;t++) {
      const a=this.tri[3*t],b=this.tri[3*t+1],c=this.tri[3*t+2];
      const m0=split.get(edgeKey(a,b)),m1=split.get(edgeKey(b,c)),m2=split.get(edgeKey(c,a));
      const s0=m0!==undefined,s1=m1!==undefined,s2=m2!==undefined,n=(s0?1:0)+(s1?1:0)+(s2?1:0);
      if(n===0)add(a,b,c,t);
      else if(n===1){if(s0){add(a,m0,c,t);add(m0,b,c,t);}else if(s1){add(b,m1,a,t);add(m1,c,a,t);}else{add(c,m2,b,t);add(m2,a,b,t);}}
      else if(n===2){if(s0&&s1){add(b,m1,m0,t);add(a,m0,c,t);add(m0,m1,c,t);}else if(s1&&s2){add(c,m2,m1,t);add(b,m1,a,t);add(m1,m2,a,t);}else{add(a,m0,m2,t);add(c,m2,b,t);add(m2,m0,b,t);}}
      else{add(a,m0,m2,t);add(m0,b,m1,t);add(m2,m1,c,t);add(m0,m1,m2,t);}
    }
    this.pos=new Float64Array(pos);this.mat=new Float64Array(mat);this.tri=new Int32Array(nt);this.n=pos.length/2;this.nt=nt.length/3;
    this._polSignal=new Float64Array(pol);this._lastPol=new Float64Array(last);this._frozenPol=new Float64Array(frozen);this._frozenMask=new Uint8Array(fm);this._plusMask=new Uint8Array(pm);this._minusMask=new Uint8Array(mm);
    for(const [name,f]of this._fields)f.values=new Float64Array(fieldArrays.get(name));
    const newRes=new Float64Array(3*this.nt);for(let t=0;t<this.nt;t++){const p=parent[t];newRes[3*t]=this._residual[3*p]||0;newRes[3*t+1]=this._residual[3*p+1]||0;newRes[3*t+2]=this._residual[3*p+2]||0;}this._residual=newRes;
    this._growthEvalPar=new Float64Array(this.n);this._growthEvalPer=new Float64Array(this.n);this._lastDisp=new Float64Array(lastDisp);this._resultant=new Float64Array(resultant);
    this._rebuildTopology();
  }

  _flipThinElements() {
    // Local 2-2 flips; only accept flips that strictly improve worst aspect.
    for(let sweep=0;sweep<8;sweep++) {
      let changed=false;
      const edgeMap=this._buildEdgeMap();
      for(const e of edgeMap.values()) {
        if(e.t0<0||e.t1<0)continue;
        const a=e.a,b=e.b,c=this._oppositeVertex(e.t0,a,b),d=this._oppositeVertex(e.t1,a,b);if(c==null||d==null||c===d)continue;
        const cur=Math.max(triAspect(this.pos,a,b,c),triAspect(this.pos,a,b,d));
        if(cur<6)continue;
        if(signedArea2(this.pos,c,d,a)*signedArea2(this.pos,c,d,b)>=0)continue; // a,b must lie opposite sides of new edge.
        const p1=[c,d,b],p2=[d,c,a];
        if(signedArea2(this.pos,...p1)<=EPS){const q=p1[1];p1[1]=p1[2];p1[2]=q;}if(signedArea2(this.pos,...p2)<=EPS){const q=p2[1];p2[1]=p2[2];p2[2]=q;}
        const neu=Math.max(triAspect(this.pos,...p1),triAspect(this.pos,...p2));
        if(neu+1e-6<cur*0.99){this.tri.set(p1,3*e.t0);this.tri.set(p2,3*e.t1);changed=true;}
      }
      if(!changed)break; this._rebuildTopology();
    }
  }

  // -------------------------------------------------------------------------
  // Geometry/material lookup. Uniform triangle buckets make toMaterial cheap;
  // toWorld uses an analogous material-space grid. Barycentric interpolation
  // guarantees patterns painted in material coordinates are advected exactly
  // with the finite-element mesh (up to interpolation/remesh error).
  // -------------------------------------------------------------------------
  bbox(){let x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity;for(let i=0;i<this.n;i++){const x=this.pos[2*i],y=this.pos[2*i+1];x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y);}return{x0,y0,x1,y1};}
  area(){let a=0;for(let t=0;t<this.nt;t++)a+=0.5*Math.abs(signedArea2(this.pos,this.tri[3*t],this.tri[3*t+1],this.tri[3*t+2]));return a;}

  toMaterial(x,y){if(this._worldGridDirty)this._buildSpatialGrid(false);return this._queryGrid(this._worldGrid,x,y,false);}
  toWorld(u,v){if(this._materialGridDirty)this._buildSpatialGrid(true);return this._queryGrid(this._materialGrid,u,v,true);}

  _buildSpatialGrid(material) {
    const arr=material?this.mat:this.pos;let x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity;
    for(let i=0;i<this.n;i++){x0=Math.min(x0,arr[2*i]);y0=Math.min(y0,arr[2*i+1]);x1=Math.max(x1,arr[2*i]);y1=Math.max(y1,arr[2*i+1]);}
    const g=Math.max(8,Math.min(64,Math.ceil(Math.sqrt(this.nt/1.5))));const buckets=Array.from({length:g*g},()=>[]),dx=(x1-x0||1)/g,dy=(y1-y0||1)/g;
    for(let t=0;t<this.nt;t++){const a=this.tri[3*t],b=this.tri[3*t+1],c=this.tri[3*t+2];const xs=[arr[2*a],arr[2*b],arr[2*c]],ys=[arr[2*a+1],arr[2*b+1],arr[2*c+1]];let i0=clamp(Math.floor((Math.min(...xs)-x0)/dx),0,g-1),i1=clamp(Math.floor((Math.max(...xs)-x0)/dx),0,g-1),j0=clamp(Math.floor((Math.min(...ys)-y0)/dy),0,g-1),j1=clamp(Math.floor((Math.max(...ys)-y0)/dy),0,g-1);for(let j=j0;j<=j1;j++)for(let i=i0;i<=i1;i++)buckets[j*g+i].push(t);}
    const grid={arr,x0,y0,x1,y1,g,dx,dy,buckets};if(material){this._materialGrid=grid;this._materialGridDirty=false;}else{this._worldGrid=grid;this._worldGridDirty=false;}
  }

  _queryGrid(grid,x,y,material){if(x<grid.x0-1e-9||x>grid.x1+1e-9||y<grid.y0-1e-9||y>grid.y1+1e-9)return null;const i=clamp(Math.floor((x-grid.x0)/grid.dx),0,grid.g-1),j=clamp(Math.floor((y-grid.y0)/grid.dy),0,grid.g-1);const src=material?this.mat:this.pos,dst=material?this.pos:this.mat;for(const t of grid.buckets[j*grid.g+i]){const a=this.tri[3*t],b=this.tri[3*t+1],c=this.tri[3*t+2];const w=barycentric(x,y,src[2*a],src[2*a+1],src[2*b],src[2*b+1],src[2*c],src[2*c+1]);if(w)return material?{x:w[0]*dst[2*a]+w[1]*dst[2*b]+w[2]*dst[2*c],y:w[0]*dst[2*a+1]+w[1]*dst[2*b+1]+w[2]*dst[2*c+1]}:{u:w[0]*dst[2*a]+w[1]*dst[2*b]+w[2]*dst[2*c],v:w[0]*dst[2*a+1]+w[1]*dst[2*b+1]+w[2]*dst[2*c+1]};}return null;}

  outline(){const map=this._buildEdgeMap(),adj=new Map();for(const e of map.values())if(e.t1<0){if(!adj.has(e.a))adj.set(e.a,[]);if(!adj.has(e.b))adj.set(e.b,[]);adj.get(e.a).push(e.b);adj.get(e.b).push(e.a);}if(!adj.size)return[];let start=[...adj.keys()].sort((a,b)=>this.pos[2*a+1]-this.pos[2*b+1]||this.pos[2*a]-this.pos[2*b])[0],prev=-1,cur=start,out=[];for(let k=0;k<adj.size+2;k++){out.push([this.pos[2*cur],this.pos[2*cur+1]]);const ns=adj.get(cur)||[];let next=ns[0]===prev?ns[1]:ns[0];if(next==null||next===start)break;prev=cur;cur=next;}return out;}

  snapshot(){const fields=[];for(const [name,f]of this._fields)fields.push({name,type:f.type,diffusion:f.diffusion,decay:f.decay,dilutable:f.dilutable,values:Array.from(f.values)});return{version:1,options:{...this.options},time:this.time,steps:this._steps,remeshes:this._remeshes,ms:this._ms,pos:Array.from(this.pos),mat:Array.from(this.mat),tri:Array.from(this.tri),polSignal:Array.from(this._polSignal),plusMask:Array.from(this._plusMask),minusMask:Array.from(this._minusMask),lastPol:Array.from(this._lastPol),frozenPol:Array.from(this._frozenPol),frozenMask:Array.from(this._frozenMask),residual:Array.from(this._residual),resultant:Array.from(this._resultant),lastDisp:Array.from(this._lastDisp),lastDt:this._lastDt,fields,hasOrganisers:this._hasOrganisers,initialEdge:this._initialEdge,initialArea:this._initialArea,lowerEdge:this._lowerEdge,upperEdge:this._upperEdge};}

  restore(s){if(!s||s.version!==1)throw new Error('Unsupported GrowthCanvas snapshot');this.options={...s.options,poisson:0.3,young:1};this.time=s.time;this._steps=s.steps;this._remeshes=s.remeshes;this._ms=s.ms;this.pos=new Float64Array(s.pos);this.mat=new Float64Array(s.mat);this.tri=new Int32Array(s.tri);this.n=this.pos.length/2;this.nt=this.tri.length/3;this._polSignal=new Float64Array(s.polSignal);this._plusMask=new Uint8Array(s.plusMask);this._minusMask=new Uint8Array(s.minusMask);this._lastPol=new Float64Array(s.lastPol);this._frozenPol=new Float64Array(s.frozenPol);this._frozenMask=new Uint8Array(s.frozenMask);this._residual=new Float64Array(s.residual);this._resultant=new Float64Array(s.resultant||4*this.n);this._lastDisp=new Float64Array(s.lastDisp||2*this.n);this._lastDt=s.lastDt||1;this._fields=new Map();for(const f of s.fields)this._fields.set(f.name,{...f,values:new Float64Array(f.values)});this._initialEdge=s.initialEdge;this._initialArea=s.initialArea||this.area();this._lowerEdge=s.lowerEdge;this._upperEdge=s.upperEdge;this._growthEvalPar=new Float64Array(this.n);this._growthEvalPer=new Float64Array(this.n);if(this._lastDisp.length!==2*this.n)this._lastDisp=new Float64Array(2*this.n);if(this._resultant.length!==4*this.n)this._resultant=new Float64Array(4*this.n);this._organisers={plusFn:null,minusFn:null};this._hasOrganisers=!!s.hasOrganisers||this._plusMask.some(x=>x)||this._minusMask.some(x=>x);this._rebuildTopology();this._worldGridDirty=true;this._materialGridDirty=true;return this;}

  validate(totalTime,opts){const snap=this.snapshot(),base=(opts&&opts.dt)||Math.min(0.05,Math.max(0.005,totalTime/20));const a=new GrowthCanvas(snap.options).restore(snap),b=new GrowthCanvas(snap.options).restore(snap);a.grow(totalTime,{...opts,dt:base});b.grow(totalTime,{...opts,dt:base/2});let max=0;const stride=Math.max(1,Math.floor(this.n/500));for(let i=0;i<this.n;i+=stride){const u=this.mat[2*i],v=this.mat[2*i+1],pa=a.toWorld(u,v),pb=b.toWorld(u,v);if(pa&&pb)max=Math.max(max,Math.hypot(pa.x-pb.x,pa.y-pb.y));}const bb=a.bbox(),diam=Math.hypot(bb.x1-bb.x0,bb.y1-bb.y0);return{maxDisplacement:max,relative:max/Math.max(diam,EPS),pass:max/Math.max(diam,EPS)<0.01,dt:base,halfDt:base/2};}
  stats(){return{tris:this.nt,verts:this.n,steps:this._steps,ms:this._ms,remeshes:this._remeshes};}

  // ----------------------------- topology/scratch --------------------------
  _backupForRetry(){const fields=[];for(const [n,f]of this._fields)if(f.type==='signal')fields.push([n,new Float64Array(f.values)]);return{pos:new Float64Array(this.pos),pol:new Float64Array(this._polSignal),frozenPol:new Float64Array(this._frozenPol),frozenMask:new Uint8Array(this._frozenMask),lastPol:new Float64Array(this._lastPol),residual:new Float64Array(this._residual),fields};}
  _restoreRetry(b){this.pos.set(b.pos);this._polSignal.set(b.pol);this._frozenPol.set(b.frozenPol);this._frozenMask.set(b.frozenMask);this._lastPol.set(b.lastPol);this._residual.set(b.residual);for(const [n,a]of b.fields)this._fields.get(n).values.set(a);this._worldGridDirty=true;}
  _vertexAreas(pos){const a=new Float64Array(this.n);for(let t=0;t<this.nt;t++){const i=this.tri[3*t],j=this.tri[3*t+1],k=this.tri[3*t+2],A=Math.abs(signedArea2(pos,i,j,k))/6;a[i]+=A;a[j]+=A;a[k]+=A;}return a;}
  _oppositeVertex(t,a,b){for(let k=0;k<3;k++){const x=this.tri[3*t+k];if(x!==a&&x!==b)return x;}return null;}
  _boundaryOther(a,exclude){const ns=this._boundaryAdj?.get(a)||[];for(const x of ns)if(x!==exclude)return x;return null;}
  _buildEdgeMap(){const map=new Map();for(let t=0;t<this.nt;t++){const a=this.tri[3*t],b=this.tri[3*t+1],c=this.tri[3*t+2];for(const [x,y]of[[a,b],[b,c],[c,a]]){const k=edgeKey(x,y);let e=map.get(k);if(!e){e={a:Math.min(x,y),b:Math.max(x,y),t0:t,t1:-1};map.set(k,e);}else e.t1=t;}}return map;}
  _rebuildTopology(){this.nt=this.tri.length/3;this.n=this.pos.length/2;const edgeMap=this._buildEdgeMap();this._edges=[...edgeMap.values()];const sets=Array.from({length:this.n},()=>new Set()),badj=new Map();for(const e of this._edges){sets[e.a].add(e.b);sets[e.b].add(e.a);if(e.t1<0){if(!badj.has(e.a))badj.set(e.a,[]);if(!badj.has(e.b))badj.set(e.b,[]);badj.get(e.a).push(e.b);badj.get(e.b).push(e.a);}}this._boundaryAdj=badj;this._nbrOff=new Int32Array(this.n+1);let total=0;for(let i=0;i<this.n;i++){this._nbrOff[i]=total;total+=sets[i].size;}this._nbrOff[this.n]=total;this._nbr=new Int32Array(total);let q=0;for(let i=0;i<this.n;i++)for(const j of sets[i])this._nbr[q++]=j;this._buildSparsePattern();this._worldGridDirty=true;this._materialGridDirty=true;}
  _buildSparsePattern(){const nd=2*this.n,rows=Array.from({length:nd},()=>new Set());for(let i=0;i<nd;i++)rows[i].add(i);for(let t=0;t<this.nt;t++){const ids=[2*this.tri[3*t],2*this.tri[3*t]+1,2*this.tri[3*t+1],2*this.tri[3*t+1]+1,2*this.tri[3*t+2],2*this.tri[3*t+2]+1];for(const i of ids)for(const j of ids)rows[i].add(j);}this._Krow=new Int32Array(nd+1);let nnz=0;for(let i=0;i<nd;i++){this._Krow[i]=nnz;nnz+=rows[i].size;}this._Krow[nd]=nnz;this._Kcol=new Int32Array(nnz);const lookup=Array.from({length:nd},()=>new Map());let p=0;for(let i=0;i<nd;i++){const cols=[...rows[i]].sort((a,b)=>a-b);for(const j of cols){this._Kcol[p]=j;lookup[i].set(j,p++);}}this._Kval=new Float64Array(nnz);this._rhs=new Float64Array(nd);this._triKIndex=new Int32Array(36*this.nt);for(let t=0;t<this.nt;t++){const ids=[2*this.tri[3*t],2*this.tri[3*t]+1,2*this.tri[3*t+1],2*this.tri[3*t+1]+1,2*this.tri[3*t+2],2*this.tri[3*t+2]+1];for(let i=0;i<6;i++)for(let j=0;j<6;j++)this._triKIndex[36*t+6*i+j]=lookup[ids[i]].get(ids[j]);}this._targetStrain=new Float64Array(3*this.nt);}
  _minEdgeLength(){let m=Infinity;for(const e of this._edges){const dx=this.pos[2*e.a]-this.pos[2*e.b],dy=this.pos[2*e.a+1]-this.pos[2*e.b+1];m=Math.min(m,Math.hypot(dx,dy));}return isFinite(m)?m:1;}
  _medianEdgeLength(){const a=[];for(const e of this._edges){const dx=this.pos[2*e.a]-this.pos[2*e.b],dy=this.pos[2*e.a+1]-this.pos[2*e.b+1];a.push(Math.hypot(dx,dy));}a.sort((x,y)=>x-y);return a[Math.floor(a.length/2)]||1;}
}

export default GrowthCanvas;
