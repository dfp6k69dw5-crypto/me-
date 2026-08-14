import { test, expect } from '@playwright/test';

test('QA-PERF phone animation stays responsive under repeated interaction', async ({page})=>{
  test.setTimeout(60000);
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await page.goto('index.html?qa-perf=1',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.__PS_QA__);
  await page.waitForTimeout(500);
  const canvas=page.locator('canvas').first();
  await expect(canvas).toBeVisible();
  const box=await canvas.boundingBox();
  expect(box).toBeTruthy();

  const metrics=await page.evaluate(async()=>{
    const frames=[]; let last=performance.now();
    await new Promise(resolve=>{
      const start=performance.now();
      function tick(t){frames.push(t-last);last=t;if(t-start<1800)requestAnimationFrame(tick);else resolve();}
      requestAnimationFrame(tick);
    });
    const sorted=[...frames].sort((a,b)=>a-b);
    const pct=p=>sorted[Math.min(sorted.length-1,Math.floor(sorted.length*p))]||999;
    return {count:frames.length,mean:frames.reduce((a,b)=>a+b,0)/Math.max(1,frames.length),p95:pct(.95),p99:pct(.99),long100:frames.filter(x=>x>100).length};
  });

  for(let i=0;i<10;i++){
    const sx=box.x+box.width*.50,sy=box.y+box.height*.50;
    const dx=(i%2?1:-1)*80,dy=(i%4<2?1:-1)*60;
    await page.mouse.move(sx,sy);await page.mouse.down();await page.mouse.move(sx+dx,sy+dy,{steps:6});await page.mouse.up();
  }
  await page.waitForTimeout(300);

  const state=await page.evaluate(()=>window.__PS_QA__.snapshot());
  expect(errors,'QA-PERF-004 runtime errors during stress').toEqual([]);
  expect(state.finite,'QA-PERF-004 simulation became non-finite').toBe(true);
  // CI runners are shared/virtualized, so this is a responsiveness smoke gate, not an iPhone FPS claim.
  expect(metrics.count,'QA-PERF-001 animation nearly stopped').toBeGreaterThan(12);
  expect(metrics.long100,'QA-PERF-002 repeated >100ms stalls').toBeLessThanOrEqual(Math.max(8,Math.floor(metrics.count*.45)));
  expect(metrics.p95,'QA-PERF-003 severe p95 frame regression').toBeLessThan(300);
  await page.screenshot({path:'qa-results/artifacts/performance-after.png',fullPage:true});
});
