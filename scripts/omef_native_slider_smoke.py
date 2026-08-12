#!/usr/bin/env python3
import io
import os
import sys
import time
import socket
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from PIL import Image, ImageChops, ImageStat
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

ROOT = Path(__file__).resolve().parents[1]

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def shot_gray(el):
    return Image.open(io.BytesIO(el.screenshot_as_png)).convert("L")

def diff_score(a, b):
    # Structural change score: changed bright/dark geometry pixels divided by the
    # visible geometry union, plus a small whole-frame MAE term.
    if a.size != b.size:
        b = b.resize(a.size)
    diff = ImageChops.difference(a, b)
    da = diff.point(lambda p: 255 if p >= 10 else 0)
    aa = a.point(lambda p: 255 if p >= 10 else 0)
    bb = b.point(lambda p: 255 if p >= 10 else 0)
    union = ImageChops.lighter(aa, bb)
    changed = sum(1 for p in da.getdata() if p)
    visible = max(1, sum(1 for p in union.getdata() if p))
    mae = ImageStat.Stat(diff).mean[0] / 255.0
    return changed / visible + 0.35 * mae

def main():
    os.chdir(ROOT)
    port = free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), QuietHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--use-gl=angle")
    opts.add_argument("--use-angle=swiftshader")
    opts.add_argument("--enable-webgl")
    opts.add_argument("--ignore-gpu-blocklist")
    opts.add_experimental_option("mobileEmulation", {
        "deviceMetrics": {"width": 390, "height": 844, "pixelRatio": 2.0},
        "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
    })

    driver = webdriver.Chrome(options=opts)
    try:
        # Capture the actual WebGL2 context so test mode can redraw deterministically
        # after a slider input. Also suppress only the 140ms heavy-state settle timer;
        # this isolates the immediate renderer route while the finger is moving.
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": r'''
(() => {
  const origGet = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function(type, opts) {
    const ctx = origGet.call(this, type, opts);
    if (type === 'webgl2' && ctx) window.__OMEF_TEST_GL__ = ctx;
    return ctx;
  };
  const origSetTimeout = window.setTimeout.bind(window);
  window.setTimeout = function(fn, ms, ...args) {
    if (ms >= 130 && ms <= 160 && String(fn).includes('rebuild')) return -987654;
    return origSetTimeout(fn, ms, ...args);
  };
})();
'''} )

        url = f"http://127.0.0.1:{port}/apps/omef-native.html?test=1&slider-sim=1"
        driver.get(url)
        WebDriverWait(driver, 45).until(lambda d: d.execute_script("return !!window.__OMEF_NATIVE_READY__"))
        status = driver.find_element(By.ID, "status").text
        if "✓" not in status:
            raise AssertionError(f"OMEF Native did not self-test cleanly: {status}")

        canvas = driver.find_element(By.ID, "gl")
        inputs = driver.find_elements(By.CSS_SELECTOR, "#controls input[type=range]")
        if len(inputs) < 8:
            raise AssertionError(f"Expected curated sliders, found {len(inputs)}")

        # Ensure a deterministic test draw helper is available. TESTMODE already uses
        # 20k points, so this exercises the actual current vertex/fragment shaders fast.
        driver.execute_script(r'''
window.__OMEF_TEST_DRAW__ = () => {
  const gl = window.__OMEF_TEST_GL__;
  if (!gl) throw new Error('no captured WebGL2 context');
  gl.clearColor(.012,.016,.02,1);
  gl.clear(gl.COLOR_BUFFER_BIT);
  gl.drawArrays(gl.POINTS, 0, 20000);
  gl.finish();
};
''')

        failures = []
        report = []
        fractions = [0.0, 0.25, 0.5, 0.75, 1.0]
        MIN_SEGMENT = 0.105
        MIN_TOTAL = 0.32

        for inp in inputs:
            cid = inp.get_attribute("id")
            mn = float(inp.get_attribute("min"))
            mx = float(inp.get_attribute("max"))
            images = []
            for f in fractions:
                value = mn + (mx - mn) * f
                driver.execute_script(r'''
const el=arguments[0], v=arguments[1];
el.value=String(v);
el.dispatchEvent(new Event('input',{bubbles:true}));
if(window.__OMEF_TEST_DRAW__) window.__OMEF_TEST_DRAW__();
''', inp, value)
                images.append(shot_gray(canvas))

            seg = [diff_score(images[i], images[i+1]) for i in range(4)]
            total = diff_score(images[0], images[-1])
            low = min(seg)
            name = cid.replace("i-", "")
            report.append((name, low, total, seg))
            print(f"SLIDER {name:22s} min-segment={low:.4f} total={total:.4f} segments=" + ",".join(f"{x:.4f}" for x in seg))
            if low < MIN_SEGMENT or total < MIN_TOTAL:
                failures.append((name, low, total, seg))

        if failures:
            print("\nDEAD/WEAK SLIDER ROUTES:")
            for name, low, total, seg in failures:
                print(f"  {name}: min-segment={low:.4f}, total={total:.4f}, segments={seg}")
            raise AssertionError(f"{len(failures)} slider routes failed renderer sensitivity thresholds")

        print(f"OMEF Native slider simulator PASS: {len(report)} sliders; every quartile segment >= {MIN_SEGMENT} and total >= {MIN_TOTAL}")
    finally:
        driver.quit()
        server.shutdown()

if __name__ == "__main__":
    main()
