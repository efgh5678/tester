from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto("http://127.0.0.1:5000")

    # 1. Discover URLs
    page.locator("#start-urls").fill("oxylabs.io\napple.com")
    page.locator("#target-count").fill("10")
    page.get_by_role("button", name="Discover URLs").click()

    # Wait for discovery to complete for both domains
    page.wait_for_selector("text=/URL: oxylabs.io - Status: (completed|failed)/", timeout=120000)
    page.wait_for_selector("text=/URL: apple.com - Status: (completed|failed)/", timeout=120000)
    page.wait_for_timeout(2000) # Wait for UI to update

    # 2. Select URLs
    page.locator('input[name="domain"][value="all"]').check()
    page.locator("#select-all").click()

    # 3. Create jobs
    page.locator("#job-target-count").fill("5")
    page.get_by_role("button", name="Create Jobs").click()

    # Wait for job creation to complete
    page.wait_for_selector("text=/Domain: oxylabs.io - Status: (completed|failed)/", timeout=120000)
    page.wait_for_selector("text=/Domain: apple.com - Status: (completed|failed)/", timeout=120000)

    page.screenshot(path="jules-scratch/verification/verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
