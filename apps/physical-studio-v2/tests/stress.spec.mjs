import { test, expect } from '@playwright/test';

test('QA-STRESS survives repeated camera and tool interactions without runtime failure', async ({page}) => {
  test.setTimeout(60000);
  const errors=[];const failed=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  page.on('requestfailed',r=>failed.push(`${r.method()} ${r.url()} ${r.failure()?.errorText||''}`));
  await page.goto('index.html?qa-stress=1',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.__PS_QA__);
  const canvas=page.locator('canvas').first();await expect(canvas).toBeVisible({timeout:10000});await page.waitForTimeout(400);
  const box=await canvas.boundingBox();expect(box).toBeTruthy();
  const drag=async(dx,dy)=>{const sx=box.x+box.width*.5,sy=box.y+box.height*.52;await canvas.dispatchEvent('pointerdown',{pointerId:1,pointerType:'touch',isPrimary:true,clientX:sx,clientY:sy,buttons:1});for(let i=1;i<=5;i++)await canvas.dispatchEvent('pointermove',{pointerId:1,pointerType:'touch',isPrimary:true,clientX:sx+dx*i/5,clientY:sy+dy*i/5,buttons:1});await canvas.dispatchEvent('pointerup',{pointerId:1,pointerType:'touch',isPrimary:true,clientX:sx+dx,clientY:sy+dy,buttons:0});};
  for(let i=0;i<30;i++){
    const angle=i*.63;await drag(Math.cos(angle)*75,Math.sin(angle)*75);
    if(i%10===0){for(const name of ['select','body','anchor','spring','exciter','mic']){const b=page.locator(`[data-tool="${name}"]`);if(await b.count())await b.click();}const sel=page.locator('[data-tool="select"]');if(await sel.count())await sel.click();}
  }
  await page.waitForTimeout(300);
  const state=await page.evaluate(()=>({snapshot:window.__PS_QA__.snapshot(),validation:window.__PS_QA__.validate()}));
  expect(state.snapshot.renderer.render.calls,'QA-REN-003 renderer stopped drawing').toBeGreaterThan(0);
  expect(state.snapshot.finite,'QA-PHY-001 state became non-finite during stress').toBe(true);
  expect(state.validation.invalidSprings,'QA-PHY-003 invalid spring reference after stress').toEqual([]);
  expect(errors,'Runtime errors during stress: '+errors.join(' | ')).toEqual([]);
  expect(failed.filter(x=>!x.includes('favicon')),'Failed network requests: '+failed.join(' | ')).toEqual([]);
  await page.screenshot({path:'qa-results/artifacts/stress-final.png',fullPage:true});
});
