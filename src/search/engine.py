import json
import os
import re
from pathlib import Path

# Get project root (2 levels up from src/search/engine.py)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "promotions.json"

# Stop words - คำที่ไม่ควร match
STOP_WORDS = {
    # Common Thai words
    'ที่', 'และ', 'หรือ', 'ของ', 'ใน', 'จาก', 'ได้', 'ไม่', 'ให้', 'มี', 'เป็น',
    'กับ', 'จะ', 'แต่', 'ว่า', 'ก็', 'นี้', 'มา', 'ไป', 'อยู่', 'แล้ว', 'ยัง',
    # Casual/greeting words
    'พี่ๆ', 'พี่', 'น้อง', 'ครับ', 'ค่ะ', 'คะ', 'นะ', 'จ้า', 'จ๊า', 'สวัสดี',
    'หวัดดี', 'เฮ้', 'เฮ้ย', 'อะ', 'เหรอ', 'ไหม', 'บ้าง', 'ด้วย', 'อีก',
    # Common English
    'the', 'and', 'or', 'for', 'to', 'in', 'on', 'at', 'of', 'is', 'it', 'by',
    'hi', 'hello', 'hey', 'please', 'thank', 'thanks', 'you', 'me', 'we',
    # Technical nulls
    'none', 'null', 'undefined', 'nan'
}

class SearchEngine:
    def __init__(self):
        self.promotions = []
        self.load_data()
    
    def is_expired(self, promo):
        """Check if promotion is expired based on duration field or old year in title/description."""
        duration = promo.get('duration', '')
        title = promo.get('title', '')
        description = promo.get('description', '')
        
        # Check if marked as expired
        if 'หมดอายุ' in duration:
            return True
        
        # Check for old years in title OR description (before current year 2026/2569)
        old_years_christian = ['2020', '2021', '2022', '2023', '2024', '2025']
        old_years_thai = ['2563', '2564', '2565', '2566', '2567', '2568']
        
        text_to_check = title + ' ' + description
        for year in old_years_christian + old_years_thai:
            if year in text_to_check:
                return True
        
        return False

    def load_data(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                all_promos = json.load(f)
                # Filter out expired promotions
                self.promotions = [p for p in all_promos if not self.is_expired(p)]
                print(f"Loaded {len(self.promotions)} active promotions (filtered {len(all_promos) - len(self.promotions)} expired)")
        else:
            print("Warning: promotions.json not found.")

    def search(self, query: str):
        if not query:
            return []
        
        query = query.lower().strip()
        
        # Minimum query length - ต้องมีอย่างน้อย 2 ตัวอักษร
        if len(query) < 2:
            return []
        
        # ถ้าเป็น stop word ไม่ค้นหา
        if query in STOP_WORDS:
            return []
        
        results = []
        
        for promo in self.promotions:
            score = 0
            
            title = promo.get('title', '').lower()
            description = promo.get('description', '').lower()
            content = promo.get('content', '').lower()
            promo_type = promo.get('promotion_type', '').lower()
            
            # 1. Title match - ให้ความสำคัญสูงสุด
            if query in title:
                # Bonus for exact word match
                if re.search(r'\b' + re.escape(query) + r'\b', title):
                    score += 100
                else:
                    score += 70
            
            # 2. Promotion type match
            if query in promo_type:
                score += 50
            
            # 3. Description match - เฉพาะ query ยาว 5+ ตัวอักษร เท่านั้น
            if len(query) >= 5 and query in description:
                score += 20
            
            # 4. Content match - เฉพาะ query ยาว 6+ ตัวอักษร เท่านั้น
            if len(query) >= 6 and query in content:
                score += 10
            
            # 5. Keyword match - exact match only, ยาว 4+ ตัวอักษร
            keywords = promo.get('keywords', [])
            if len(query) >= 3:
                for kw in keywords:
                    if kw and len(kw) >= 3 and kw not in STOP_WORDS:
                        if query == kw.lower():
                            score += 25
                            break
            
            if score > 0:
                results.append((promo, score))
        
        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Return only promos (without scores)
        return [r[0] for r in results]

    def get_latest(self, n=50):
        return self.promotions[:n]

    def get_by_id(self, promo_id: int):
        for promo in self.promotions:
            if promo.get('id') == promo_id:
                return promo
        return None

