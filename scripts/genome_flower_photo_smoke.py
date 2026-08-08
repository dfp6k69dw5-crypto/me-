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

try:
    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, 45)
    driver.get(f"http://127.0.0.1:{server.server_port}/apps/genome-flower/photo-studio-v2.html")
    wait.until(lambda d: d.find_element(By.ID, "core"))
    frame = driver.find_element(By.ID, "core")

    driver.switch_to.frame(frame)
    wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "#controlList input[type=range][data-key]")) == 72)
    sliders = driver.find_elements(By.CSS_SELECTOR, "#controlList input[type=range][data-key]")
    mutation = driver.find_elements(By.CSS_SELECTOR, "#mutationList input[type=range]")
    assert len(sliders) == 72, f"Expected 72 sequence-addressable genetic sliders, got {len(sliders)}"
    assert len(mutation) == 10, f"Expected 10 mutation sliders, got {len(mutation)}"
    first = sliders[0]
    old = int(first.get_attribute("value"))

    driver.switch_to.default_content()
    wait.until(lambda d: d.execute_script("return !!window.__GENOME_PHOTO_TEST__"))
    prompt0 = driver.execute_script("return window.__GENOME_PHOTO_TEST__.buildPrompt()")
    assert len(prompt0) > 2500, "Photo phenotype prompt is unexpectedly short"
    for phrase in ["FLORAL ARCHITECTURE", "PIGMENT BIOLOGY", "REPRODUCTIVE ORGANS", "FULL 72-PATHWAY GENETIC CONTROL VECTOR", "photorealistic macro botanical photograph"]:
        assert phrase in prompt0, f"Missing phenotype-to-photo prompt section: {phrase}"
    vector_count0 = prompt0.split("FULL 72-PATHWAY GENETIC CONTROL VECTOR", 1)[1].count("=")
    assert vector_count0 >= 72, f"Expected all 72 genetic controls in photo prompt, found {vector_count0}"
    assert driver.find_element(By.ID, "renderPhoto").is_displayed()
    assert "GENERATE PHOTOGRAPH" in driver.find_element(By.ID, "renderPhoto").text

    # The core Genome Flower smoke test separately proves that a change event rewrites
    # sequence DNA and regenerates the phenotype. Here we isolate the photo shell and
    # prove that changing a live genetic value changes the image-model phenotype input.
    driver.switch_to.frame(frame)
    sliders = driver.find_elements(By.CSS_SELECTOR, "#controlList input[type=range][data-key]")
    first = sliders[0]
    new = 90 if old < 50 else 10
    driver.execute_script("arguments[0].value=arguments[1];arguments[0].dispatchEvent(new Event('input',{bubbles:true}));", first, new)
    driver.switch_to.default_content()

    prompt1 = driver.execute_script("return window.__GENOME_PHOTO_TEST__.buildPrompt()")
    assert prompt1 != prompt0, "Changing a live genetic control did not change the photographic phenotype prompt"
    vector_count1 = prompt1.split("FULL 72-PATHWAY GENETIC CONTROL VECTOR", 1)[1].count("=")
    assert vector_count1 >= 72, f"Expected all 72 genetic controls in updated photo prompt, found {vector_count1}"

    severe = [x for x in driver.get_log("browser") if x.get("level") == "SEVERE" and "favicon.ico" not in x.get("message", "")]
    assert not severe, f"Browser console errors: {severe}"
    print("Genome Flower photo shell smoke passed: 72 DNA pathways -> prompt chars", len(prompt0), "->", len(prompt1))
finally:
    try:
        driver.quit()
    except Exception:
        pass
    server.shutdown()
