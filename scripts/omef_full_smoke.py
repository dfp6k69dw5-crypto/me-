import subprocess
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
PORT = 8876
BASE = f"http://127.0.0.1:{PORT}/apps/omef-full.html"


def wait(driver, predicate, timeout=35):
    WebDriverWait(driver, timeout).until(lambda d: predicate(d))


def signature(driver):
    return driver.execute_script("""
      const c=document.querySelector('canvas');
      if(!c) return null;
      const x=c.getContext('2d'), w=c.width, h=c.height;
      let hash=2166136261>>>0;
      for(let gy=1;gy<18;gy++) for(let gx=1;gx<18;gx++){
        const p=x.getImageData(Math.floor(w*gx/18),Math.floor(h*gy/18),1,1).data;
        for(let k=0;k<4;k++){ hash^=p[k]; hash=Math.imul(hash,16777619)>>>0; }
      }
      return [w,h,hash];
    """)


server = subprocess.Popen(
    [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1", "--directory", str(ROOT)],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
opts = webdriver.ChromeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-gpu")
opts.add_argument("--window-size=390,844")
opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})

try:
    time.sleep(.7)
    driver=webdriver.Chrome(options=opts)
    try:
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {"width":390,"height":844,"deviceScaleFactor":3,"mobile":True})
        driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {"enabled":True,"maxTouchPoints":5})
        for layer in range(1,9):
            driver.get(f"{BASE}?selftest=1&fast=1&layer={layer}")
            wait(driver, lambda d: d.title == "OMEF FULL — Total-State Attractor")
            wait(driver, lambda d: d.execute_script("return document.body.dataset.selftest") == "PASS")
            wait(driver, lambda d: len(d.find_elements(By.TAG_NAME,"canvas")) == 1)
            txt=driver.find_element(By.ID,"tests").text
            if "ALL CHECKS PASSED" not in txt:
                raise AssertionError(f"Layer {layer} did not report full self-check pass: {txt[-900:]}")
            sig=signature(driver)
            if not sig or sig[0] != 1400 or sig[1] != 1400:
                raise AssertionError(f"Layer {layer} canvas wrong: {sig}")
            print(f"OMEF FULL cumulative layer {layer}: PASS; canvas={sig}")

        sig0=signature(driver)
        driver.find_element(By.ID,"mutate").click()
        wait(driver, lambda d: d.execute_script("return document.body.dataset.selftest") == "PASS")
        time.sleep(1.2)
        sig1=signature(driver)
        if sig1 == sig0:
            raise AssertionError(f"Mutate species did not alter canvas signature: {sig0}")

        fold=driver.find_element(By.ID,"fold")
        fold.click(); time.sleep(.3)
        if fold.text.strip().lower() != "fold":
            raise AssertionError("Unfold control did not enter unfolded state")
        fold.click()

        severe=[]
        for entry in driver.get_log("browser"):
            msg=entry.get("message","")
            if entry.get("level") == "SEVERE" and "favicon.ico" not in msg:
                severe.append(msg)
        if severe:
            raise AssertionError("Browser errors:\n"+"\n".join(severe))
        print("OMEF FULL mobile-browser smoke test passed; mutation",sig0,"->",sig1)
    finally:
        driver.quit()
finally:
    server.terminate()
    try: server.wait(timeout=3)
    except subprocess.TimeoutExpired: server.kill()
