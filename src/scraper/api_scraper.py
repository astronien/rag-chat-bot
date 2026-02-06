import json
import os
import httpx
from datetime import datetime
from pathlib import Path

# API Configuration
LOGIN_URL = "https://api.vrcomseven.com/users/web_login"
PROMOTIONS_URL = "https://api.vrcomseven.com/v1/promotions"
USERNAME = os.environ.get("VR_USERNAME", "25622")
PASSWORD = os.environ.get("VR_PASSWORD", "91544")

def login() -> str | None:
    """Login via API and return access token."""
    import uuid
    try:
        response = httpx.post(
            LOGIN_URL,
            json={
                "emp_code": USERNAME,
                "pass": PASSWORD,
                "device_uuid": str(uuid.uuid4()),
                "platform": "web"
            },
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            # Token is in data.access_token or data.accessToken
            token_data = data.get("data", {})
            return token_data.get("access_token") or token_data.get("accessToken") or data.get("accessToken")
        else:
            print(f"Login failed: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def fetch_promotions(token: str) -> list:
    """Fetch all promotions via API."""
    try:
        response = httpx.get(
            f"{PROMOTIONS_URL}?perpage=200&sort_by=updated_at&sort_direction=desc&business_units=Apple",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("data", [])
        else:
            print(f"Fetch failed: {response.status_code}")
            return []
    except Exception as e:
        print(f"Fetch error: {e}")
        return []

def process_promotions(raw_promotions: list) -> list:
    """Transform raw API data to our format."""
    results = []
    
    for promo in raw_promotions:
        # Calculate duration
        duration = ""
        try:
            display_to = promo.get("display_to")
            if display_to:
                end_date = datetime.strptime(display_to.split()[0], "%Y-%m-%d")
                days_left = (end_date - datetime.now()).days
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
        for att in promo.get("attachments", []) or []:
            attachments.append({
                "text": att.get("title", "ดาวน์โหลด"),
                "url": att.get("uri", "")
            })
        
        # Generate keywords
        text = f"{promo.get('title', '')} {promo.get('description', '')} {promo.get('category', '')}"
        keywords = list(set([w.lower() for w in text.split() if len(w) > 2]))[:30]
        
        results.append({
            "id": promo.get("id"),
            "title": promo.get("title", ""),
            "link": f"https://vrcomseven.com/promotions/{promo.get('id')}",
            "description": promo.get("description", ""),
            "content": promo.get("description", ""),
            "duration": duration,
            "start_date": promo.get("start_date") or promo.get("display_from", ""),
            "end_date": promo.get("end_date") or promo.get("display_to", ""),
            "category": promo.get("category", ""),
            "promotion_type": (promo.get("promotion_type") or {}).get("name", ""),
            "attachments": attachments,
            "keywords": keywords
        })
    
    return results

def scrape_and_save() -> dict:
    """Main function: login, fetch, process, save."""
    print("🔐 Logging in...")
    token = login()
    if not token:
        return {"success": False, "error": "Login failed"}
    
    print("📥 Fetching promotions...")
    raw = fetch_promotions(token)
    if not raw:
        return {"success": False, "error": "No promotions fetched"}
    
    print(f"🔄 Processing {len(raw)} promotions...")
    promotions = process_promotions(raw)
    
    # Save to file
    output_path = Path(__file__).parent.parent / "data" / "promotions.json"
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(promotions, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Saved {len(promotions)} promotions")
    return {"success": True, "count": len(promotions)}

if __name__ == "__main__":
    result = scrape_and_save()
    print(result)
