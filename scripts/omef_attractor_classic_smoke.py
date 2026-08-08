import subprocess
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
PORT = 8879
BASE = f"http://127.0.0.1:{PORT}/apps/omef-attractor-classic.html"


def wait(driver, predicate, timeout=45):
    WebDriverWait(driver, timeout).until(lambda d: predicate(d))


def signature(driver):
    return driver.execute_script("""
      const c=document.getElementById('cv');
      if(!c) return null;
      const mini=document.createElement('canvas');
      mini.width=64; mini.height=48;
      const m=mini.getContext('2d',{willReadFrequently:true});
      m.drawImage(c,0,0,64,48);
      const data=m.getImageData(0,0,64,48).data;
      let hash=2166136261>>>0, energy=0;
      for(let i=0;i<data.length;i+=4){
        energy += data[i]+data[i+1]+data[i+2];
        hash^=data[i]; hash=Math.imul(hash,16777619)>>>0;
        hash^=data[i+1]; hash=Math.imul(hash,16777619)>>>0;
        hash^=data[i+2]; hash=Math.imul(hash,16777619)>>>0;
      }
      return [c.width,c.height,hash,energy];
    """)


def set_input(driver, element_id, value, event="input"):
    driver.execute_script(
        "const e=document.getElementById(arguments[0]); e.value=arguments[1]; e.dispatchEvent(new Event(arguments[2],{bubbles:true}));",
        element_id, str(value), event,
    )


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
        driver.get(BASE)
        wait(driver, lambda d: d.title == "OMEF Total-State Attractor — Classic")
        wait(driver, lambda d: d.find_element(By.ID,"status").text.strip().lower() == "done")
        sig0=signature(driver)
        if not sig0 or sig0[0] != 1000 or sig0[1] != 760 or sig0[3] <= 0:
            raise AssertionError(f"Initial OMEF canvas invalid: {sig0}")

        set_input(driver,"pair",175)
        wait(driver, lambda d: d.find_element(By.ID,"status").text.strip().lower() == "done")
        sig_pair=signature(driver)
        if sig_pair == sig0:
            raise AssertionError(f"Pair coupling did not alter canvas: {sig0}")

        set_input(driver,"regime",62)
        wait(driver, lambda d: d.find_element(By.ID,"status").text.strip().lower() == "done")
        sig_regime=signature(driver)
        if sig_regime == sig_pair:
            raise AssertionError(f"Regime switching did not alter canvas: {sig_pair}")

        set_input(driver,"lens","cycles","change")
        wait(driver, lambda d: d.find_element(By.ID,"status").text.strip().lower() == "done")
        sig_lens=signature(driver)
        if sig_lens == sig_regime:
            raise AssertionError(f"Projection lens did not alter canvas: {sig_regime}")

        driver.find_element(By.ID,"mutate").click()
        wait(driver, lambda d: d.find_element(By.ID,"status").text.strip().lower() == "done")
        sig_mut=signature(driver)
        if sig_mut == sig_lens:
            raise AssertionError(f"Mutation did not alter canvas: {sig_lens}")

        severe=[]
        for entry in driver.get_log("browser"):
            msg=entry.get("message","")
            if entry.get("level") == "SEVERE" and "favicon.ico" not in msg:
                severe.append(msg)
        if severe:
            raise AssertionError("Browser errors:\n"+"\n".join(severe))

        print("OMEF Total-State Attractor mobile smoke test passed")
        print("signatures:",sig0,"-> pair",sig_pair,"-> regime",sig_regime,"-> lens",sig_lens,"-> mutate",sig_mut)
    finally:
        driver.quit()
finally:
    server.terminate()
    try: server.wait(timeout=3)
    except subprocess.TimeoutExpired: server.kill()
