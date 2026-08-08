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
    busy = ("initialising", "reading DNA", "developing", "growing tissue", "carrying pigment")
    return s and not any(x in s for x in busy) and "error" not in s.lower() and "variables" in s

try:
    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, 30)
    driver.get(f"http://127.0.0.1:{server.server_port}/apps/genome-flower/index.html")
    wait.until(finished)

    digest0 = text(driver, "digest")
    flower0 = text(driver, "flowerstat")
    assert digest0 and digest0 != "—", "Genome digest did not render"
    assert "petals" in flower0 and "tris" in flower0, f"Flower stats missing: {flower0}"

    transform = driver.execute_script("return document.querySelector('#stage').getContext('2d').getTransform().a")
    dpr = driver.execute_script("return Math.min(window.devicePixelRatio || 1, 2)")
    assert abs(transform - dpr) < 0.01, f"Canvas transform {transform} does not match DPR {dpr}"

    driver.find_element(By.ID, "mutate").click()
    wait.until(lambda d: finished(d) and text(d, "digest") != digest0)
    digest1 = text(driver, "digest")
    assert "bases" in text(driver, "changes")

    driver.find_element(By.ID, "big").click()
    wait.until(lambda d: finished(d) and text(d, "digest") != digest1)

    driver.find_element(By.ID, "undo").click()
    wait.until(lambda d: finished(d) and text(d, "digest") == digest1)

    drawer = driver.find_element(By.ID, "drawer")
    driver.find_element(By.ID, "info").click()
    wait.until(lambda d: "open" in drawer.get_attribute("class"))
    assert len(text(driver, "seq")) > 100, "Genome sequence preview missing"

    severe = [
        x for x in driver.get_log("browser")
        if x.get("level") == "SEVERE" and "favicon.ico" not in x.get("message", "")
    ]
    assert not severe, f"Browser console errors: {severe}"
    print("Genome Flower mobile smoke passed:", text(driver, "status"), text(driver, "flowerstat"))
finally:
    try:
        driver.quit()
    except Exception:
        pass
    server.shutdown()
