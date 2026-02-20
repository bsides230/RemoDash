from playwright.sync_api import sync_playwright
import time
import urllib.request

BASE_URL = "http://localhost:8000"
def set_state(state):
    urllib.request.urlopen(f"{BASE_URL}/control/set_state?state={state}")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    set_state("stopped_files_exist")
    page.goto(BASE_URL)
    time.sleep(2)
    page.screenshot(path="frontend_ready.png")
    browser.close()
