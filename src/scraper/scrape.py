import asyncio
import os
import json
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.getenv("VR_USERNAME", "25622")
PASSWORD = os.getenv("VR_PASSWORD", "91544")
BASE_URL = "https://vrcomseven.com"
LOGIN_URL = f"{BASE_URL}/promotions"
OUTPUT_FILE = "data/promotions.json"

async def scrape_promotions():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"Navigating to {LOGIN_URL}...")
        await page.goto(LOGIN_URL)

        # 1. Handle Login
        try:
            # Wait for login input or redirect
            await page.wait_for_selector("input.input-box.form-control", timeout=5000)
            print("Login page detected. Logging in...")
            
            inputs = await page.locator("input.input-box.form-control").all()
            if len(inputs) >= 2:
                await inputs[0].fill(USERNAME)
                await inputs[1].fill(PASSWORD)
            
            await page.click("button.unique-button")
            await page.wait_for_load_state('networkidle')
            print("Login submitted.")
        except:
            print("Already logged in or login form not found.")

        # 2. Extract Promotions
        print("Extracting promotion cards...")
        try:
            await page.wait_for_selector(".main-card", timeout=60000) # Increased timeout
        except Exception as e:
            print(f"Error waiting for cards: {e}")
            await page.screenshot(path="debug_error.png")
            print("Saved debug_error.png")
            raise e
        
        cards = await page.locator(".main-card").all()
        if not cards:
            print("No cards found! Saving screenshot...")
            await page.screenshot(path="debug_no_cards.png")

        results = []

        for i, card in enumerate(cards):
            try:
                # Title
                title_el = card.locator("h1, h2, h3, h4, h5, .title").first
                title = await title_el.inner_text() if await title_el.count() > 0 else "No Title"
                
                # Link
                link_el = card.locator("a[href]").first
                link = await link_el.get_attribute("href") if await link_el.count() > 0 else None
                if link and not link.startswith("http"):
                    link = BASE_URL + link

                # Description
                desc_el = card.locator(".card-desc").first
                desc = await desc_el.inner_text() if await desc_el.count() > 0 else ""

                # Keywords (Simple extraction from title)
                # Split title by spaces, filter pure alphanumeric or thai
                keywords = [word.lower() for word in title.split() if len(word) > 1]

                results.append({
                    "id": i,
                    "title": title.strip(),
                    "link": link,
                    "description": desc.strip(),
                    "keywords": keywords
                })
                print(f"Found: {title}")
            except Exception as e:
                print(f"Error parsing card {i}: {e}")

        await browser.close()
        
        # Save to JSON
        os.makedirs("data", exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"Saved {len(results)} promotions to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(scrape_promotions())
