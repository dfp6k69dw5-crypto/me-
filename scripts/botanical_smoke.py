import os
import subprocess
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
PORT = 8765
URL = f"http://127.0.0.1:{PORT}/apps/botanical-harmonograph.html?v=smoke"


def wait_until(driver, predicate, timeout=20, message="condition"):
    WebDriverWait(driver, timeout).until(lambda d: predicate(d))


def button_by_text(driver, text):
    return driver.find_element(By.XPATH, f"//button[translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{text.lower()}']")


def canvas_signature(driver):
    return driver.execute_script("""
      const c=document.querySelector('canvas');
      if(!c || c.width < 50 || c.height < 50) return null;
      const ctx=c.getContext('2d');
      const w=c.width,h=c.height;
      const pts=[[.15,.15],[.5,.5],[.85,.2],[.2,.8],[.8,.8],[.5,.25],[.25,.5],[.75,.5]];
      let s=0;
      for(const [fx,fy] of pts){
        const p=ctx.getImageData(Math.min(w-1,Math.floor(w*fx)),Math.min(h-1,Math.floor(h*fy)),1,1).data;
        s=(s*131 + p[0]*3+p[1]*5+p[2]*7+p[3]) >>> 0;
      }
      return [w,h,s];
    """)


def dump_browser_state(driver, label):
    try:
        body = driver.find_element(By.TAG_NAME, "body").text[:1800]
    except Exception as exc:
        body = f"<body unavailable: {exc}>"
    print(f"--- {label} body ---")
    print(body)
    print(f"--- {label} browser log ---")
    for entry in driver.get_log("browser"):
        print(entry)
    print(f"--- {label} source head ---")
    print(driver.page_source[:2500])


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
    time.sleep(0.8)
    driver = webdriver.Chrome(options=opts)
    try:
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": 390, "height": 844, "deviceScaleFactor": 3, "mobile": True
        })
        driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
        driver.get(URL)

        wait_until(driver, lambda d: d.title == "Botanical Harmonograph", message="app title")
        try:
            wait_until(driver, lambda d: len(d.find_elements(By.TAG_NAME, "canvas")) == 1, message="canvas")
        except Exception:
            dump_browser_state(driver, "canvas-timeout")
            raise
        wait_until(driver, lambda d: len(d.find_elements(By.XPATH, "//button")) >= 4, message="controls")

        time.sleep(1.8)
        sig0 = canvas_signature(driver)
        if not sig0 or sig0[0] < 200 or sig0[1] < 200:
            raise AssertionError(f"Canvas did not size correctly: {sig0}")

        status0 = driver.find_element(By.XPATH, "//*[contains(text(),'· petal') or contains(text(),'· bloom') or contains(text(),'· filament')]").text
        button_by_text(driver, "hybrid").click()
        time.sleep(1.8)
        sig1 = canvas_signature(driver)
        status1 = driver.find_element(By.XPATH, "//*[contains(text(),'· petal') or contains(text(),'· bloom') or contains(text(),'· filament')]").text
        if status1 == status0:
            raise AssertionError(f"Hybrid did not change status: {status0!r}")
        if sig1 == sig0:
            raise AssertionError("Hybrid did not change sampled canvas output")

        button_by_text(driver, "controls").click()
        wait_until(driver, lambda d: len(d.find_elements(By.CSS_SELECTOR, "input[type=range]")) > 0, message="sliders")
        sliders = driver.find_elements(By.CSS_SELECTOR, "input[type=range]")
        slider = sliders[0]
        old = slider.get_attribute("value")
        slider.click()
        slider.send_keys(Keys.ARROW_RIGHT)
        time.sleep(0.35)
        new = slider.get_attribute("value")
        if new == old:
            slider.send_keys(Keys.ARROW_LEFT)
            time.sleep(0.35)
            new = slider.get_attribute("value")
        if new == old:
            raise AssertionError(f"First slider did not respond; value stayed {old}")

        time.sleep(0.8)
        sig2 = canvas_signature(driver)
        if sig2 == sig1:
            raise AssertionError("Slider value changed but canvas sample did not update")

        severe=[]
        for entry in driver.get_log("browser"):
            if entry.get("level") == "SEVERE" and "favicon.ico" not in entry.get("message", ""):
                severe.append(entry.get("message", ""))
        if severe:
            raise AssertionError("Browser errors:\n" + "\n".join(severe))

        print("Botanical browser smoke test passed")
        print("initial status:", status0)
        print("hybrid status:", status1)
        print("slider:", old, "->", new)
        print("canvas signatures:", sig0, sig1, sig2)
    finally:
        driver.quit()
finally:
    server.terminate()
    try:
        server.wait(timeout=3)
    except subprocess.TimeoutExpired:
        server.kill()
