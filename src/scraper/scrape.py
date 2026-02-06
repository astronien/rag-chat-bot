import asyncio
import os
import json
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

USERNAME = os.getenv("VR_USERNAME", "25622")
PASSWORD = os.getenv("VR_PASSWORD", "91544")
BASE_URL = "https://vrcomseven.com"
API_URL = "https://api.vrcomseven.com/v1/promotions"
LOGIN_URL = f"{BASE_URL}/promotions"
OUTPUT_FILE = "data/promotions.json"

async def scrape_promotions():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"Navigating to {LOGIN_URL}...")
        await page.goto(LOGIN_URL, timeout=60000)

        # 1. Handle Login
        try:
            await page.wait_for_selector("input.input-box.form-control", timeout=10000)
            print("Login page detected. Logging in...")
            inputs = await page.locator("input.input-box.form-control").all()
            if len(inputs) >= 2:
                await inputs[0].fill(USERNAME)
                await inputs[1].fill(PASSWORD)
            await page.click("button.unique-button")
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)
            print("Login submitted.")
        except:
            print("Already logged in or login form not found.")

        await page.wait_for_timeout(2000)
        
        # 2. Get Bearer token from localStorage (retry up to 3 times)
        token = None
        for attempt in range(3):
            token = await page.evaluate("localStorage.getItem('accessToken')")
            if token:
                break
            print(f"  Waiting for token... (attempt {attempt + 1})")
            await page.wait_for_timeout(2000)
            
        if not token:
            print("❌ Error: Could not get access token!")
            await browser.close()
            return
        
        print(f"✅ Got access token: {token[:20]}...")
        
        # 3. Fetch all promotions via API
        print("\n=== Fetching promotions via API ===")
        all_promotions = []
        current_page = 1
        per_page = 200  # Fetch more items per page
        
        while True:
            print(f"\n📄 Fetching page {current_page}...")
            
            api_data = await page.evaluate(f'''async () => {{
                const token = localStorage.getItem('accessToken');
                const response = await fetch(
                    '{API_URL}?page={current_page}&perpage={per_page}&sort_by=updated_at&sort_direction=desc&business_units=Apple',
                    {{ headers: {{ 'Authorization': `Bearer ${{token}}` }} }}
                );
                return await response.json();
            }}''')
            
            if not api_data or 'data' not in api_data:
                print("  -> No more data")
                print(f"  -> Response: {api_data}")
                break
            
            promotions = api_data.get('data', [])
            if not promotions:
                print("  -> Empty page, stopping")
                break
            
            print(f"  -> Got {len(promotions)} promotions")
            
            for promo in promotions:
                # Calculate duration from end_date
                duration = ""
                try:
                    if promo.get('display_to'):
                        end_date = datetime.strptime(promo['display_to'].split()[0], '%Y-%m-%d')
                        today = datetime.now()
                        days_left = (end_date - today).days
                        if days_left > 0:
                            duration = f"เหลือเวลาอีก {days_left} วัน"
                        elif days_left == 0:
                            duration = "วันนี้วันสุดท้าย"
                        else:
                            duration = "หมดอายุแล้ว"
                except:
                    pass
                
                # Format attachments
                attachments = []
                for att in promo.get('attachments', []):
                    attachments.append({
                        "text": att.get('title', 'ดาวน์โหลด'),
                        "url": att.get('uri', '')
                    })
                
                # Generate keywords
                text_for_keywords = f"{promo.get('title', '')} {promo.get('description', '')} {promo.get('category', '')}"
                keywords = list(set([w.lower() for w in text_for_keywords.split() if len(w) > 2]))[:30]
                
                all_promotions.append({
                    "id": promo.get('id'),
                    "title": promo.get('title', ''),
                    "link": f"{BASE_URL}/promotions/{promo.get('id')}",
                    "description": promo.get('description', ''),
                    "content": promo.get('description', ''),  # API doesn't have full content, use description
                    "duration": duration,
                    "start_date": promo.get('start_date', ''),
                    "end_date": promo.get('end_date', ''),
                    "category": promo.get('category', ''),
                    "promotion_type": (promo.get('promotion_type') or {}).get('name', ''),
                    "attachments": attachments,
                    "keywords": keywords
                })
            
            # Check pagination
            meta = api_data.get('meta', {})
            total_pages = meta.get('last_page', 1)
            
            if current_page >= total_pages:
                print(f"  -> Reached last page ({total_pages})")
                break
            
            current_page += 1
        
        await browser.close()
        
        print(f"\n✅ Total: {len(all_promotions)} promotions collected")
        
        # Save to JSON
        os.makedirs("data", exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_promotions, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(scrape_promotions())
