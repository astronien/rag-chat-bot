import asyncio
import os
import json
import re
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

        # 2. Count cards
        print("Extracting promotion cards...")
        try:
            await page.wait_for_selector(".main-card", timeout=60000)
        except Exception as e:
            print(f"Error waiting for cards: {e}")
            await page.screenshot(path="debug_error.png")
            raise e
        
        card_count = await page.locator(".main-card").count()
        print(f"Found {card_count} promotion cards")
        
        if card_count == 0:
            print("No cards found!")
            return

        results = []

        # 3. Process each card
        for i in range(card_count):
            try:
                # Always start from list page
                if page.url != LOGIN_URL:
                    await page.goto(LOGIN_URL)
                    await page.wait_for_selector(".main-card", timeout=30000)
                
                # Get card info before clicking
                cards = await page.locator(".main-card").all()
                if i >= len(cards):
                    continue
                    
                card = cards[i]
                
                # Get title from card
                title_el = card.locator("h1, h2, h3, h4, h5").first
                card_title = await title_el.inner_text() if await title_el.count() > 0 else f"Promotion {i}"
                card_title = card_title.strip()
                
                # Get short description
                desc_el = card.locator(".card-desc").first
                short_desc = await desc_el.inner_text() if await desc_el.count() > 0 else ""
                
                print(f"\n[{i+1}/{card_count}] {card_title[:50]}...")
                
                # Find and click "อ่านเพิ่มเติม"
                read_more = card.locator("text=อ่านเพิ่มเติม").first
                if await read_more.count() > 0:
                    # Store current URL
                    old_url = page.url
                    
                    # Click
                    await read_more.click()
                    
                    # Wait for URL to change (Vue router navigation)
                    try:
                        await page.wait_for_url(re.compile(r"/promotions/\d+"), timeout=10000)
                    except:
                        # If URL doesn't change, wait a bit and check
                        await page.wait_for_timeout(2000)
                    
                    new_url = page.url
                    
                    if new_url != old_url and '/promotions/' in new_url:
                        print(f"  -> Opened: {new_url}")
                        
                        await page.wait_for_load_state('networkidle')
                        
                        # Extract content from detail page
                        full_content = ""
                        
                        # Try .pre-formatted
                        pre_el = page.locator(".pre-formatted").first
                        if await pre_el.count() > 0:
                            full_content = await pre_el.inner_text()
                        
                        # Get title from detail page
                        head_font = page.locator(".head-font").first
                        if await head_font.count() > 0:
                            detail_title = await head_font.inner_text()
                        else:
                            detail_title = card_title
                        
                        # Fallback content
                        if not full_content or len(full_content) < 50:
                            for sel in [".col-md-6", ".container", "article"]:
                                el = page.locator(sel).first
                                if await el.count() > 0:
                                    full_content = await el.inner_text()
                                    if len(full_content) > 100:
                                        break
                        
                        if not full_content:
                            full_content = short_desc
                        
                        print(f"  -> Got {len(full_content)} chars")
                        
                        # Keywords
                        text_for_keywords = detail_title + " " + full_content
                        keywords = list(set([w.lower() for w in text_for_keywords.split() if len(w) > 2]))[:30]
                        
                        results.append({
                            "id": i,
                            "title": detail_title.strip(),
                            "link": new_url,
                            "description": short_desc.strip(),
                            "content": full_content.strip()[:5000],  # Limit content size
                            "keywords": keywords
                        })
                    else:
                        print(f"  -> Failed to navigate (stayed at {new_url})")
                        results.append({
                            "id": i,
                            "title": card_title,
                            "link": None,
                            "description": short_desc.strip(),
                            "content": "",
                            "keywords": []
                        })
                else:
                    print(f"  -> No 'อ่านเพิ่มเติม' link")
                    results.append({
                        "id": i,
                        "title": card_title,
                        "link": None,
                        "description": short_desc.strip(),
                        "content": "",
                        "keywords": []
                    })
                    
            except Exception as e:
                print(f"  -> Error: {e}")

        await browser.close()
        
        # Save to JSON
        os.makedirs("data", exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Saved {len(results)} promotions to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(scrape_promotions())
