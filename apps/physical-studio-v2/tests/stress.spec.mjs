import { test, expect } from '@playwright/test';

test('QA-STRESS survives repeated camera and tool interactions without runtime failure', async ({page}) => {
  const errors=[];const failed=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  page.on('requestfailed',r=>failed.push(`${r.method()} ${r.url()} ${r.failure()?.errorText||''}`));
  await page.goto('index.html?qa-stress=1',{waitUntil:'domcontentloaded'});
  const canvas=page.locator('canvas').first();await expect(canvas).toBeVisible({timeout:10000});await page.waitForTimeout(800);
  const box=await canvas.boundingBox();expect(box).toBeTruthy();
  const drag=async(dx,dy,id)=>{const sx=box.width*.5,sy=box.height*.52;await canvas.dispatchEvent('pointerdown',{pointerId:id,pointerType:'touch',isPrimary:true,clientX:box.x+sx,clientY:box.y+sy,buttons:1});for(let k=1;k<=6;k++){await canvas.dispatchEvent('pointermove',{pointerId:id,pointerType:'touch',isPrimary:true,clientX:box.x+sx+dx*k/6,clientY:box.y+sy+dy*k/6,buttons:1})}await canvas.dispatchEvent('pointerup',{pointerId:id,pointerType:'touch',isPrimary:true,clientX:box.x+sx+dx,clientY:box.y+sy+dy,buttons:0});};
  for(let i=0;i<60;i++){
    const angle=i*.63;await drag(Math.cos(angle)*80,Math.sin(angle)*80,100+i);
    if(i%10===0){for(const name of ['select','body','anchor','spring','exciter','mic']){const b=page.locator(`[data-tool="${name}"]`);if(await b.count())await b.click();}const sel=page.locator('[data-tool="select"]');if(await sel.count())await sel.click();}
    if(i%12===0)await page.waitForTimeout(60);
  }
  await page.waitForTimeout(500);
  const sig=await canvas.evaluate(c=>{const p=document.createElement('canvas');p.width=64;p.height=96;const x=p.getContext('2d',{willReadFrequently:true});x.drawImage(c,0,0,64,96);const d=x.getImageData(0,0,64,96).data;let min=255,max=0,bad=0;for(let i=0;i<d.length;i+=16){for(let j=0;j<3;j++)if(!Number.isFinite(d[i+j]))bad++;const v=(d[i]+d[i+1]+d[i+2])/3;min=Math.min(min,v);max=Math.max(max,v)}return{range:max-min,bad}});
  expect(sig.bad,'QA-REN-003 invalid rendered pixels after stress').toBe(0);
  expect(sig.range,'QA-REN-003 scene blank after stress').toBeGreaterThan(5);
  expect(errors,'Runtime errors during stress: '+errors.join(' | ')).toEqual([]);
  expect(failed.filter(x=>!x.includes('favicon')),'Failed network requests: '+failed.join(' | ')).toEqual([]);
  await page.screenshot({path:'qa-results/artifacts/stress-final.png',fullPage:true});
});
