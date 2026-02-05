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

        # Wait for page to fully load
        await page.wait_for_timeout(3000)
        
        results = []
        global_id = 0
        current_page = 1
        
        while True:
            print(f"\n📄 Processing page {current_page}...")
            
            # Wait for cards to load
            try:
                await page.wait_for_selector(".main-card", timeout=30000)
            except Exception as e:
                print(f"Error waiting for cards on page {current_page}: {e}")
                break
            
            # Get all cards on this page
            cards = await page.locator(".main-card").all()
            card_count = len(cards)
            print(f"Found {card_count} cards on page {current_page}")
            
            if card_count == 0:
                break
            
            # Process each card on current page
            for i in range(card_count):
                try:
                    # Get fresh card reference
                    cards = await page.locator(".main-card").all()
                    if i >= len(cards):
                        continue
                        
                    card = cards[i]
                    
                    # Get title
                    title_el = card.locator("h1, h2, h3, h4, h5").first
                    card_title = await title_el.inner_text() if await title_el.count() > 0 else f"Promotion {global_id}"
                    card_title = card_title.strip()
                    
                    # Get short description
                    desc_el = card.locator(".card-desc").first
                    short_desc = await desc_el.inner_text() if await desc_el.count() > 0 else ""
                    
                    # Get duration badge (e.g., "เหลือเวลาอีก 23 วัน" or "ตลอดไป")
                    duration = ""
                    try:
                        # Look for badge with duration text
                        badge = card.locator(".badge, .time-badge, [class*='badge']").first
                        if await badge.count() > 0:
                            duration = await badge.inner_text()
                        # Also try looking for text containing "เหลือเวลา" or "วัน"
                        if not duration:
                            duration_el = card.locator("text=/เหลือเวลา|ตลอดไป|วัน/").first
                            if await duration_el.count() > 0:
                                duration = await duration_el.inner_text()
                    except:
                        pass
                    
                    print(f"\n[Page {current_page}, Card {i+1}/{card_count}] {card_title[:50]}...")
                    if duration:
                        print(f"  -> Duration: {duration}")
                    
                    # Click "อ่านเพิ่มเติม" to get full content
                    read_more = card.locator("text=อ่านเพิ่มเติม").first
                    if await read_more.count() > 0:
                        old_url = page.url
                        await read_more.click()
                        
                        try:
                            await page.wait_for_url(re.compile(r"/promotions/\d+"), timeout=10000)
                        except:
                            await page.wait_for_timeout(2000)
                        
                        new_url = page.url
                        
                        if new_url != old_url and '/promotions/' in new_url:
                            print(f"  -> Opened: {new_url}")
                            await page.wait_for_load_state('networkidle')
                            
                            # Extract full content
                            full_content = ""
                            pre_el = page.locator(".pre-formatted").first
                            if await pre_el.count() > 0:
                                full_content = await pre_el.inner_text()
                            
                            # Get title from detail page
                            head_font = page.locator(".head-font").first
                            detail_title = await head_font.inner_text() if await head_font.count() > 0 else card_title
                            
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
                            
                            # Extract attachments
                            attachments = await page.evaluate('''() => {
                                const links = [];
                                const seen = new Set();
                                
                                // Find <a> tags
                                document.querySelectorAll('a').forEach(a => {
                                    const href = a.href;
                                    const text = a.textContent.trim();
                                    if (href.includes('drive.google.com') || 
                                        href.includes('.pdf') ||
                                        href.includes('.xlsb') ||
                                        href.includes('.xlsx') ||
                                        (href.includes('static.vrcomseven.com') && !href.endsWith('.jpg') && !href.endsWith('.png'))) {
                                        if (!href.endsWith('#') && !seen.has(href)) {
                                            seen.add(href);
                                            links.push({ text: text || 'ดาวน์โหลด', url: href });
                                        }
                                    }
                                });
                                
                                // Find img.img-btn (PDF previews)
                                document.querySelectorAll('img.img-btn').forEach(img => {
                                    const src = img.src;
                                    if (src.includes('static.vrcomseven.com')) {
                                        let pdfUrl = src.replace(/\\.(jpg|jpeg|png)$/i, '.pdf');
                                        const filename = pdfUrl.split('/').pop().split('-').slice(1).join('-').replace('.pdf', '');
                                        if (!seen.has(pdfUrl)) {
                                            seen.add(pdfUrl);
                                            links.push({ text: filename || 'PDF ไฟล์', url: pdfUrl });
                                        }
                                    }
                                });
                                
                                return links;
                            }''')
                            
                            print(f"  -> Found {len(attachments)} attachments")
                            
                            # Keywords
                            text_for_keywords = detail_title + " " + full_content
                            keywords = list(set([w.lower() for w in text_for_keywords.split() if len(w) > 2]))[:30]
                            
                            results.append({
                                "id": global_id,
                                "title": detail_title.strip(),
                                "link": new_url,
                                "description": short_desc.strip(),
                                "content": full_content.strip()[:5000],
                                "duration": duration.strip(),
                                "attachments": attachments,
                                "keywords": keywords
                            })
                            global_id += 1
                            
                            # Go back to list page
                            await page.goto(f"{LOGIN_URL}?page={current_page}")
                            await page.wait_for_selector(".main-card", timeout=30000)
                        else:
                            print(f"  -> Failed to navigate")
                    else:
                        print(f"  -> No 'อ่านเพิ่มเติม' link")
                        results.append({
                            "id": global_id,
                            "title": card_title,
                            "link": None,
                            "description": short_desc.strip(),
                            "content": "",
                            "duration": duration.strip(),
                            "attachments": [],
                            "keywords": []
                        })
                        global_id += 1
                        
                except Exception as e:
                    print(f"  -> Error: {e}")
            
            # Check for next page
            next_page_exists = False
            try:
                # Look for pagination - try clicking next page number
                next_page_num = current_page + 1
                next_btn = page.locator(f"text='{next_page_num}'").first
                
                # Also try looking for › (next) button
                if await next_btn.count() == 0:
                    next_btn = page.locator("text='›'").first
                
                if await next_btn.count() > 0:
                    # Scroll to pagination area (usually at bottom)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(500)
                    await next_btn.click()
                    await page.wait_for_timeout(2000)
                    
                    # Check if URL changed or new cards loaded
                    current_page += 1
                    next_page_exists = True
                    print(f"\n>>> Moving to page {current_page}...")
            except Exception as e:
                print(f"No more pages or pagination error: {e}")
            
            if not next_page_exists:
                print("\n>>> No more pages to process")
                break

        await browser.close()
        
        # Save to JSON
        os.makedirs("data", exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Saved {len(results)} promotions to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(scrape_promotions())
