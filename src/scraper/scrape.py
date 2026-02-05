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

        # 2. Extract Promotion Cards
        print("Extracting promotion cards...")
        try:
            await page.wait_for_selector(".main-card", timeout=60000)
        except Exception as e:
            print(f"Error waiting for cards: {e}")
            await page.screenshot(path="debug_error.png")
            raise e
        
        cards = await page.locator(".main-card").all()
        if not cards:
            print("No cards found!")
            await page.screenshot(path="debug_no_cards.png")
            return

        # Collect basic info first
        basic_info = []
        for i, card in enumerate(cards):
            try:
                title_el = card.locator("h1, h2, h3, h4, h5, .title").first
                title = await title_el.inner_text() if await title_el.count() > 0 else "No Title"
                
                link_el = card.locator("a[href]").first
                link = await link_el.get_attribute("href") if await link_el.count() > 0 else None
                if link and not link.startswith("http"):
                    link = BASE_URL + link

                desc_el = card.locator(".card-desc").first
                desc = await desc_el.inner_text() if await desc_el.count() > 0 else ""

                basic_info.append({
                    "id": i,
                    "title": title.strip(),
                    "link": link,
                    "description": desc.strip(),
                })
                print(f"Found: {title.strip()[:50]}...")
            except Exception as e:
                print(f"Error parsing card {i}: {e}")

        # 3. Visit each detail page to get full content
        print(f"\n--- Scraping details for {len(basic_info)} promotions ---")
        results = []
        
        for item in basic_info:
            full_content = ""
            if item['link']:
                try:
                    print(f"Visiting: {item['title'][:40]}...")
                    await page.goto(item['link'], timeout=30000)
                    await page.wait_for_load_state('domcontentloaded')
                    
                    # Try to find main content area (adjust selector based on site structure)
                    # Common selectors for content
                    content_selectors = [
                        ".content-body",
                        ".promotion-content", 
                        ".article-content",
                        ".main-content",
                        ".card-body",
                        "article",
                        ".container main",
                    ]
                    
                    for selector in content_selectors:
                        content_el = page.locator(selector).first
                        if await content_el.count() > 0:
                            full_content = await content_el.inner_text()
                            break
                    
                    # Fallback: get all text from body but clean it up
                    if not full_content:
                        body_text = await page.locator("body").inner_text()
                        # Take first 2000 chars to avoid too much junk
                        full_content = body_text[:2000]
                    
                    print(f"  -> Got {len(full_content)} chars")
                    
                except Exception as e:
                    print(f"  -> Error: {e}")
                    full_content = item['description']  # Fallback to short desc
            
            # Build keywords from title and content
            text_for_keywords = item['title'] + " " + full_content
            keywords = list(set([word.lower() for word in text_for_keywords.split() if len(word) > 2]))[:20]
            
            results.append({
                "id": item['id'],
                "title": item['title'],
                "link": item['link'],
                "description": item['description'],
                "content": full_content.strip(),
                "keywords": keywords
            })

        await browser.close()
        
        # Save to JSON
        os.makedirs("data", exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\nSaved {len(results)} promotions with full details to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(scrape_promotions())

