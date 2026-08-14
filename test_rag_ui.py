import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://localhost:8000/")
        await page.wait_for_selector('button[data-nav="rag"]')
        await page.click('button[data-nav="rag"]')
        await page.wait_for_selector('#btn-load-rag')
        await page.click('#btn-load-rag')
        await asyncio.sleep(2)
        await page.screenshot(path="/home/athar/.gemini/antigravity-cli/brain/d095a87c-f1d9-4804-8235-b70f97e0422b/rag_efficiency_dashboard.png")
        await browser.close()

asyncio.run(main())
