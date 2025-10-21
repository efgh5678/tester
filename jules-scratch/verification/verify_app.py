from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    page.goto("http://127.0.0.1:5000/")

    # Fill out the URL discovery form and submit
    page.locator("#start-url").fill("example.com")
    page.locator("#target-count").fill("100")
    page.locator("#discover-form button").click()

    # Wait for the progress indicator to be visible
    discover_progress = page.locator("#discover-progress")
    expect(discover_progress).to_be_visible()

    # Take a screenshot
    page.screenshot(path="jules-scratch/verification/verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
