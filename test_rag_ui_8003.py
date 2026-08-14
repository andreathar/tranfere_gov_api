import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://localhost:8003/")
        await page.wait_for_selector('button[data-nav="rag"]', timeout=10000)
        await page.click('button[data-nav="rag"]')
        await page.wait_for_selector('#btn-load-rag', timeout=5000)
        await page.click('#btn-load-rag')
        await asyncio.sleep(5)
        await page.screenshot(path="/home/athar/.gemini/antigravity-cli/brain/d095a87c-f1d9-4804-8235-b70f97e0422b/rag_efficiency_dashboard_8003.png", full_page=True)
        await browser.close()
        print("Screenshot saved to /home/athar/.gemini/antigravity-cli/brain/d095a87c-f1d9-4804-8235-b70f97e0422b/rag_efficiency_dashboard_8003.png")

asyncio.run(main())
