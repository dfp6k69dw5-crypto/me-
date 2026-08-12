#!/usr/bin/env python3
"""Simulation gate for apps/langlands-fluid-desktop.html.

Requires: Python Playwright + Chromium. Pillow is optional; this harness focuses on
state/interaction metrics so it can run without image-analysis dependencies.

Run from the repository:
  python tools/langlands-fluid-desktop-simulator.py
  python tools/langlands-fluid-desktop-simulator.py --quick
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import argparse, json, math, time

ROOT=Path(__file__).resolve().parents[1]
HTML_PATH=ROOT/'apps'/'langlands-fluid-desktop.html'

def launch(pw):
    return pw.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'])

def load(page, html, errors):
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content(html, wait_until='load', timeout=30000)
    page.wait_for_function('window.__LANG_FLUID_DESKTOP !== undefined')
    if page.locator('#play').inner_text()=='Pause': page.locator('#play').click()
    page.evaluate('window.__LANG_FLUID_DESKTOP.ambient.testMode=true')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--quick',action='store_true'); ap.add_argument('--out',default='langlands-fluid-sim-report.json'); args=ap.parse_args()
    if not HTML_PATH.exists(): raise SystemExit(f'Missing {HTML_PATH}')
    html=HTML_PATH.read_text(encoding='utf-8')
    report={'html':str(HTML_PATH.relative_to(ROOT)),'errors':[],'checks':{}}
    with sync_playwright() as pw:
        # Coupled fluid + ambient run.
        b=launch(pw); p=b.new_page(viewport={'width':1440,'height':900}); load(p,html,report['errors'])
        p.evaluate('__LANG_FLUID_DESKTOP.setMode("auto");__LANG_FLUID_DESKTOP.newJourney()')
        seconds=60 if args.quick else 300
        samples=p.evaluate(f'__LANG_FLUID_DESKTOP.advance({seconds},.125,1)')
        st=p.evaluate('__LANG_FLUID_DESKTOP.getState()')
        sigs=[s['signature'] for s in samples]
        report['checks']['fluid_seconds']=seconds
        report['checks']['finite']=all(math.isfinite(v) for s in samples for v in s['metrics'].values())
        report['checks']['unique_fraction']=len(set(sigs))/len(sigs) if sigs else 0
        report['checks']['mass_range']=[min(s['metrics']['mass'] for s in samples),max(s['metrics']['mass'] for s in samples)]
        report['checks']['ke_range']=[min(s['metrics']['ke'] for s in samples),max(s['metrics']['ke'] for s in samples)]
        report['checks']['safety']=st['safety']; b.close()

        # Mode and UI behavior.
        b=launch(pw); p=b.new_page(viewport={'width':1200,'height':800}); load(p,html,report['errors'])
        p.evaluate('__LANG_FLUID_DESKTOP.setMode("manual");__LANG_FLUID_DESKTOP.newJourney();__LANG_FLUID_DESKTOP.setMode("manual")')
        before=p.evaluate('__LANG_FLUID_DESKTOP.getState().params'); p.evaluate('__LANG_FLUID_DESKTOP.advance(20,.25,1)'); after=p.evaluate('__LANG_FLUID_DESKTOP.getState().params')
        keys=['viscosity','diffusion','vorticity','buoyancy','shear','turbulence','fm','rank','center','genus','dimN']
        report['checks']['manual_drift']=max(abs(after[k]-before[k]) for k in keys)
        p.evaluate('__LANG_FLUID_DESKTOP.setMode("auto");__LANG_FLUID_DESKTOP.retarget(true)'); before=p.evaluate('__LANG_FLUID_DESKTOP.getState().params');p.evaluate('__LANG_FLUID_DESKTOP.advance(20,.25,1)');after=p.evaluate('__LANG_FLUID_DESKTOP.getState().params')
        report['checks']['auto_drift']=max(abs(after[k]-before[k]) for k in keys)
        p.evaluate('__LANG_FLUID_DESKTOP.engine.clearAll();__LANG_FLUID_DESKTOP.setMode("hybrid")');box=p.locator('canvas').bounding_box();x=box['x']+box['width']*.3;y=box['y']+box['height']*.5;p.mouse.move(x,y);p.mouse.down();p.mouse.move(x+180,y-90,steps=8);p.mouse.up();report['checks']['hybrid_draw_mass']=p.evaluate('__LANG_FLUID_DESKTOP.engine.metrics().mass')
        p.evaluate('__LANG_FLUID_DESKTOP.engine.clearAll();__LANG_FLUID_DESKTOP.setMode("auto")');p.mouse.move(x,y);p.mouse.down();p.mouse.move(x+120,y+60,steps=6);p.mouse.up();report['checks']['auto_draw_mass']=p.evaluate('__LANG_FLUID_DESKTOP.engine.metrics().mass')
        p.evaluate("document.getElementById('hideDelay').value='2';document.getElementById('hideDelay').dispatchEvent(new Event('input',{bubbles:true}));__LANG_FLUID_DESKTOP.setMode('auto')");p.mouse.move(4,4);time.sleep(2.25);report['checks']['ui_hidden']=p.evaluate("document.body.classList.contains('ui-hidden')");p.mouse.move(70,70);time.sleep(.1);report['checks']['ui_revealed']=not p.evaluate("document.body.classList.contains('ui-hidden')");b.close()

        # Long non-loop morphology and event family differentiation.
        b=launch(pw); p=b.new_page(viewport={'width':1100,'height':700}); load(p,html,report['errors'])
        p.evaluate('__LANG_FLUID_DESKTOP.setMode("auto");__LANG_FLUID_DESKTOP.newJourney();__LANG_FLUID_DESKTOP.ambient.nextSafety=1e12')
        loops=1200 if args.quick else 14400
        morph=p.evaluate(f'''() => {{const D=__LANG_FLUID_DESKTOP,out=[];D.ambient.nextSafety=1e12;for(let i=0;i<{loops};i++){{D.ambientUpdate(.5,false);if(i%60===0)out.push(D.signature())}}return {{sigs:out,state:D.getState()}}}}''')
        report['checks']['morph_hours']=loops*.5/3600
        report['checks']['morph_unique_fraction']=len(set(morph['sigs']))/len(morph['sigs'])
        report['checks']['event_types']=len(morph['state']['eventCounts']); report['checks']['event_counts']=morph['state']['eventCounts']; b.close()

    report['pass']=not report['errors'] and report['checks']['finite'] and report['checks']['unique_fraction']==1 and report['checks']['manual_drift']==0 and report['checks']['auto_drift']>0 and report['checks']['hybrid_draw_mass']>0 and report['checks']['auto_draw_mass']==0 and report['checks']['ui_hidden'] and report['checks']['ui_revealed'] and report['checks']['morph_unique_fraction']==1
    out=ROOT/args.out; out.write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2)); raise SystemExit(0 if report['pass'] else 1)
if __name__=='__main__': main()
