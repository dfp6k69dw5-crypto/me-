import { test, expect } from '@playwright/test';

const sleep = ms => new Promise(r=>setTimeout(r,ms));

async function canvasBox(page){
  const canvas=page.locator('canvas').first();
  await expect(canvas).toBeVisible();
  const box=await canvas.boundingBox();
  expect(box?.width||0).toBeGreaterThan(100);
  expect(box?.height||0).toBeGreaterThan(100);
  return {canvas,box};
}

async function frameSignature(page){
  return await page.locator('canvas').first().evaluate(c=>{
    const probe=document.createElement('canvas'); probe.width=96; probe.height=160;
    const x=probe.getContext('2d',{willReadFrequently:true}); x.drawImage(c,0,0,probe.width,probe.height);
    const d=x.getImageData(0,0,probe.width,probe.height).data;
    let sum=0,sum2=0,min=255,max=0,n=0;
    for(let i=0;i<d.length;i+=16){const v=(d[i]+d[i+1]+d[i+2])/3;sum+=v;sum2+=v*v;min=Math.min(min,v);max=Math.max(max,v);n++}
    return {mean:sum/n,var:sum2/n-(sum/n)**2,range:max-min};
  });
}

async function drag(page,dx,dy){
  const {canvas,box}=await canvasBox(page);
  const sx=box.width*.5, sy=box.height*.52;
  await canvas.dispatchEvent('pointerdown',{pointerId:1,pointerType:'touch',isPrimary:true,clientX:box.x+sx,clientY:box.y+sy,buttons:1});
  for(let i=1;i<=12;i++){
    await canvas.dispatchEvent('pointermove',{pointerId:1,pointerType:'touch',isPrimary:true,clientX:box.x+sx+dx*i/12,clientY:box.y+sy+dy*i/12,buttons:1});
    await page.waitForTimeout(12);
  }
  await canvas.dispatchEvent('pointerup',{pointerId:1,pointerType:'touch',isPrimary:true,clientX:box.x+sx+dx,clientY:box.y+sy+dy,buttons:0});
  await page.waitForTimeout(350);
}

function signatureDelta(a,b){return Math.abs(a.mean-b.mean)+Math.abs(a.var-b.var)*.02+Math.abs(a.range-b.range)*.05}

for(const path of ['index.html']){
  test.beforeEach(async({page})=>{
    const errors=[];
    page.on('pageerror',e=>errors.push('pageerror:'+e.message));
    page.on('console',m=>{if(m.type()==='error')errors.push('console:'+m.text())});
    await page.goto(path+'?qa-ci=1',{waitUntil:'domcontentloaded'});
    await page.waitForTimeout(1200);
    page.__qaErrors=errors;
  });

  test('QA-BOOT/REN boot and nonblank render',async({page})=>{
    await canvasBox(page);
    const s=await frameSignature(page);
    expect(s.range,'QA-REN-002 blank/solid frame').toBeGreaterThan(6);
    expect(page.__qaErrors,'QA-BOOT runtime errors').toEqual([]);
    await page.screenshot({path:'qa-results/artifacts/initial.png',fullPage:true});
  });

  test('QA-CAM horizontal and vertical orbit both visibly work',async({page})=>{
    const s0=await frameSignature(page);
    await drag(page,120,0); const s1=await frameSignature(page);
    expect(signatureDelta(s0,s1),'QA-CAM-001 horizontal orbit no change').toBeGreaterThan(.5);
    await drag(page,0,-150); const s2=await frameSignature(page);
    expect(signatureDelta(s1,s2),'QA-CAM-002 vertical orbit no change').toBeGreaterThan(.5);
    await page.screenshot({path:'qa-results/artifacts/orbit-after.png',fullPage:true});
  });

  test('QA-CAM repeated drags continue instead of sticking',async({page})=>{
    let prior=await frameSignature(page); let changed=0;
    for(let i=0;i<4;i++){await drag(page,105,0);const now=await frameSignature(page);if(signatureDelta(prior,now)>.25)changed++;prior=now;}
    expect(changed,'QA-CAM-003 repeated horizontal orbit stuck').toBeGreaterThanOrEqual(3);
    prior=await frameSignature(page);changed=0;
    for(let i=0;i<3;i++){await drag(page,0,-95);const now=await frameSignature(page);if(signatureDelta(prior,now)>.25)changed++;prior=now;}
    expect(changed,'QA-CAM-003 repeated vertical orbit stuck').toBeGreaterThanOrEqual(2);
  });

  test('QA-UI controls stay inside phone viewport and activate',async({page})=>{
    const overflow=await page.evaluate(()=>[...document.querySelectorAll('button,input,section,nav')].filter(el=>{const r=el.getBoundingClientRect();return r.width&&r.height&&(r.left<0||r.top<0||r.right>innerWidth+1||r.bottom>innerHeight+1)}).map(el=>el.id||el.className||el.tagName));
    expect(overflow,'QA-UI-001 viewport overflow: '+overflow.join(', ')).toEqual([]);
    const body=page.locator('[data-tool="body"]');await body.click();await expect(body).toHaveClass(/active/);
    const spring=page.locator('[data-tool="spring"]');await spring.click();await expect(spring).toHaveClass(/active/);
  });

  test('QA-AUD actual worklet produces finite decaying signal',async({page,browserName})=>{
    const result=await page.evaluate(async()=>{
      const AC=window.AudioContext||window.webkitAudioContext;if(!AC)return {skip:'AudioContext unavailable'};
      const ctx=new AC({latencyHint:'interactive'});await ctx.audioWorklet.addModule('./physics-worklet.js?ci='+Date.now());
      const node=new AudioWorkletNode(ctx,'physical-graph',{outputChannelCount:[2]});
      const analyser=new AnalyserNode(ctx,{fftSize:2048});const mute=new GainNode(ctx,{gain:0});node.connect(analyser).connect(mute).connect(ctx.destination);await ctx.resume();
      node.port.postMessage({t:'graph',bodies:[{mass:1,damping:.1,anchor:true},{mass:1,damping:.14,anchor:false}],springs:[{a:0,b:1,stiffness:450,damping:2.5}]});
      const measure=()=>{const a=new Float32Array(analyser.fftSize);analyser.getFloatTimeDomainData(a);let ss=0,peak=0,dc=0,bad=0;for(const v of a){if(!Number.isFinite(v))bad++;ss+=v*v;dc+=v;peak=Math.max(peak,Math.abs(v))}return{rms:Math.sqrt(ss/a.length),peak,dc:dc/a.length,bad}};
      await new Promise(r=>setTimeout(r,100));const pre=measure();node.port.postMessage({t:'hit',index:1,amount:1.8});await new Promise(r=>setTimeout(r,100));const hit=measure();await new Promise(r=>setTimeout(r,700));const tail=measure();await ctx.close();return{pre,hit,tail};
    });
    test.skip(!!result.skip,result.skip||'');
    expect(result.pre.rms,'QA-AUD unexpected pre-hit noise').toBeLessThan(.01);
    expect(result.hit.rms,'QA-AUD-002 silence after hit').toBeGreaterThan(.00005);
    expect(result.hit.bad,'QA-AUD-004 non-finite samples').toBe(0);
    expect(result.hit.peak,'QA-AUD-003 clipping').toBeLessThan(1.05);
    expect(Math.abs(result.hit.dc),'QA-AUD-006 DC offset').toBeLessThan(.1);
    expect(result.tail.rms,'QA-AUD-005 signal did not decay').toBeLessThan(result.hit.rms);
  });
}
