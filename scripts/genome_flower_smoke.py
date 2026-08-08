from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

handler = partial(Quiet, directory=str(ROOT))
server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
Thread(target=server.serve_forever, daemon=True).start()

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_experimental_option("mobileEmulation", {
    "deviceMetrics": {"width": 390, "height": 844, "pixelRatio": 2.0},
})
opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})

def text(driver, ident):
    return driver.find_element(By.ID, ident).text

def finished(driver):
    s = text(driver, "status")
    busy = ("initialising", "decoding DNA", "growing petal tissue", "building flower architecture")
    return s and not any(x in s for x in busy) and "error" not in s.lower() and "variables" in s

def canvas_signature(driver):
    return driver.execute_script("""
      const c=document.querySelector('#stage'),x=c.getContext('2d'),d=x.getImageData(0,0,c.width,c.height).data;
      let h=2166136261>>>0,step=Math.max(4,Math.floor(d.length/1600/4)*4);
      for(let i=0;i<d.length;i+=step){h^=d[i];h=Math.imul(h,16777619);h^=d[i+1];h=Math.imul(h,16777619);h^=d[i+2];h=Math.imul(h,16777619)}
      return [c.width,c.height,h>>>0];
    """)

try:
    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, 40)
    driver.get(f"http://127.0.0.1:{server.server_port}/apps/genome-flower/studio.html")
    wait.until(finished)

    digest0 = text(driver, "digest")
    type0 = text(driver, "flowerstat")
    sig0 = canvas_signature(driver)
    assert digest0 and digest0 != "—", "Genome digest did not render"
    assert type0 in {"rose","lily","tulip","daisy","sunflower","orchid","iris","bell"}, f"Unknown flower type: {type0}"

    transform = driver.execute_script("return document.querySelector('#stage').getContext('2d').getTransform().a")
    dpr = driver.execute_script("return Math.min(window.devicePixelRatio || 1, 2)")
    assert abs(transform - dpr) < 0.01, f"Canvas transform {transform} does not match DPR {dpr}"

    driver.find_element(By.ID, "controlsBtn").click()
    controls = driver.find_element(By.ID, "controls")
    wait.until(lambda d: "open" in controls.get_attribute("class"))
    sliders = controls.find_elements(By.CSS_SELECTOR, "input[type=range]")
    assert len(sliders) == 10, f"Expected 10 sequence sliders, got {len(sliders)}"
    driver.execute_script("arguments[0].value=90;arguments[0].dispatchEvent(new Event('input',{bubbles:true}));", sliders[0])
    driver.execute_script("arguments[0].value=100;arguments[0].dispatchEvent(new Event('input',{bubbles:true}));", sliders[5])
    driver.find_element(By.ID, "closeControls").click()

    driver.find_element(By.ID, "mutate").click()
    wait.until(lambda d: finished(d) and text(d, "digest") != digest0)
    digest1 = text(driver, "digest")
    sig1 = canvas_signature(driver)
    assert "bases" in text(driver, "changes")
    assert sig1 != sig0, f"Mutation did not alter rendered canvas: {sig0}"

    driver.find_element(By.ID, "big").click()
    wait.until(lambda d: finished(d) and text(d, "digest") != digest1)
    sig2 = canvas_signature(driver)
    assert sig2 != sig1, "Big mutation did not alter rendered canvas"

    driver.find_element(By.ID, "undo").click()
    wait.until(lambda d: finished(d) and text(d, "digest") == digest1)

    driver.find_element(By.CSS_SELECTOR, ".brand").click()
    drawer = driver.find_element(By.ID, "genomeDrawer")
    wait.until(lambda d: "open" in drawer.get_attribute("class"))
    assert len(text(driver, "seq")) > 100, "Genome sequence preview missing"

    severe = [x for x in driver.get_log("browser") if x.get("level") == "SEVERE" and "favicon.ico" not in x.get("message", "")]
    assert not severe, f"Browser console errors: {severe}"
    print("Genome Flower studio smoke passed:", type0, "->", text(driver, "flowerstat"), sig0, sig1, sig2)
finally:
    try:
        driver.quit()
    except Exception:
        pass
    server.shutdown()
