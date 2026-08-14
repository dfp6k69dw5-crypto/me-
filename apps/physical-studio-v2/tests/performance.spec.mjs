import { test, expect } from '@playwright/test';

test('QA-PERF phone animation stays responsive under repeated interaction', async ({page})=>{
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await page.goto('index.html?qa-perf=1',{waitUntil:'domcontentloaded'});
  await page.waitForTimeout(1000);
  const canvas=page.locator('canvas').first();
  await expect(canvas).toBeVisible();
  const box=await canvas.boundingBox();
  expect(box).toBeTruthy();

  const metrics=await page.evaluate(async()=>{
    const frames=[]; let last=performance.now();
    await new Promise(resolve=>{
      const start=performance.now();
      function tick(t){frames.push(t-last);last=t;if(t-start<2200)requestAnimationFrame(tick);else resolve();}
      requestAnimationFrame(tick);
    });
    const sorted=[...frames].sort((a,b)=>a-b);
    const pct=p=>sorted[Math.min(sorted.length-1,Math.floor(sorted.length*p))]||999;
    return {count:frames.length,mean:frames.reduce((a,b)=>a+b,0)/Math.max(1,frames.length),p95:pct(.95),p99:pct(.99),long50:frames.filter(x=>x>50).length,long100:frames.filter(x=>x>100).length};
  });

  for(let i=0;i<16;i++){
    const sx=box.x+box.width*.50,sy=box.y+box.height*.50;
    const dx=(i%2?1:-1)*95,dy=(i%4<2?1:-1)*70;
    await page.mouse.move(sx,sy);await page.mouse.down();await page.mouse.move(sx+dx,sy+dy,{steps:8});await page.mouse.up();
  }
  await page.waitForTimeout(500);

  expect(errors,'QA-PERF-004 runtime errors during stress').toEqual([]);
  expect(metrics.count,'QA-PERF-001 too few animation frames').toBeGreaterThan(45);
  expect(metrics.long100,'QA-PERF-002 repeated >100ms stalls').toBeLessThanOrEqual(3);
  expect(metrics.p95,'QA-PERF-003 severe p95 frame regression').toBeLessThan(80);
  await page.screenshot({path:'qa-results/artifacts/performance-after.png',fullPage:true});
});
