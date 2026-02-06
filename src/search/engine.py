import json
import os
import re
from pathlib import Path

# Get project root (2 levels up from src/search/engine.py)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "promotions.json"

# Stop words - คำที่ไม่ควร match
STOP_WORDS = {
    'ที่', 'และ', 'หรือ', 'ของ', 'ใน', 'จาก', 'ได้', 'ไม่', 'ให้', 'มี', 'เป็น',
    'กับ', 'จะ', 'แต่', 'ว่า', 'ก็', 'นี้', 'มา', 'ไป', 'อยู่', 'แล้ว', 'ยัง',
    'the', 'and', 'or', 'for', 'to', 'in', 'on', 'at', 'of', 'is', 'it', 'by',
    'none', 'null', 'undefined', 'nan'
}

class SearchEngine:
    def __init__(self):
        self.promotions = []
        self.load_data()

    def load_data(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                self.promotions = json.load(f)
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
            
            # 1. Title match - highest priority
            if query in title:
                # Bonus for exact word match
                if re.search(r'\b' + re.escape(query) + r'\b', title):
                    score += 100
                else:
                    score += 50
            
            # 2. Promotion type match
            if query in promo_type:
                score += 40
            
            # 3. Description match - สำหรับ query ยาว 4+ ตัวอักษร
            if len(query) >= 4 and query in description:
                score += 30
            
            # 4. Content match - สำหรับ query ยาว 4+ ตัวอักษร
            if len(query) >= 4 and query in content:
                score += 20
            
            # 5. Keyword match - exact match only สำหรับคำยาว
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

