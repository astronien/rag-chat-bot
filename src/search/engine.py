import json
import os
import re
from datetime import datetime
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

# Synonyms - คำพ้องเสียง/คำเหมือน (ค้นหาคำใดคำหนึ่ง จะ match ทุกคำในกลุ่ม)
SYNONYMS = {
    # Apple Products
    'ไอโฟน': ['iphone', 'ไอโฟน', 'ไอ โฟน'],
    'iphone': ['iphone', 'ไอโฟน', 'ไอ โฟน'],
    'แมค': ['mac', 'macbook', 'แมค', 'แม็ค', 'แม็คบุ๊ค'],
    'mac': ['mac', 'macbook', 'แมค', 'แม็ค', 'แม็คบุ๊ค'],
    'macbook': ['mac', 'macbook', 'แมค', 'แม็ค', 'แม็คบุ๊ค'],
    'ไอแพด': ['ipad', 'ไอแพด', 'ไอ แพด'],
    'ipad': ['ipad', 'ไอแพด', 'ไอ แพด'],
    'แอร์พอด': ['airpods', 'airpod', 'แอร์พอด', 'แอร์พ็อด', 'หูฟังแอปเปิ้ล'],
    'airpods': ['airpods', 'airpod', 'แอร์พอด', 'แอร์พ็อด'],
    'แอปเปิ้ล': ['apple', 'แอปเปิ้ล', 'แอปเปิล'],
    'apple': ['apple', 'แอปเปิ้ล', 'แอปเปิล'],
    'วอช': ['watch', 'วอช', 'นาฬิกา', 'สมาร์ทวอช'],
    'watch': ['watch', 'วอช', 'นาฬิกา', 'smartwatch'],
    'นาฬิกา': ['watch', 'วอช', 'นาฬิกา', 'smartwatch'],
    
    # Other Brands
    'ซัมซุง': ['samsung', 'ซัมซุง', 'ซัมซุ่ง'],
    'samsung': ['samsung', 'ซัมซุง', 'ซัมซุ่ง'],
    'โซนี่': ['sony', 'โซนี่'],
    'sony': ['sony', 'โซนี่'],
    'เอชพี': ['hp', 'เอชพี'],
    'hp': ['hp', 'เอชพี'],
    'แคนนอน': ['canon', 'แคนนอน', 'แคนอน'],
    'canon': ['canon', 'แคนนอน', 'แคนอน'],
    'เอปสัน': ['epson', 'เอปสัน'],
    'epson': ['epson', 'เอปสัน'],
    
    # Product Types
    'โน๊ตบุ๊ค': ['notebook', 'laptop', 'โน๊ตบุ๊ค', 'โน้ตบุ๊ค', 'แล็ปท็อป'],
    'notebook': ['notebook', 'laptop', 'โน๊ตบุ๊ค', 'โน้ตบุ๊ค', 'แล็ปท็อป'],
    'laptop': ['notebook', 'laptop', 'โน๊ตบุ๊ค', 'โน้ตบุ๊ค', 'แล็ปท็อป'],
    'ปริ้นเตอร์': ['printer', 'ปริ้นเตอร์', 'เครื่องปริ้น', 'เครื่องพิมพ์'],
    'printer': ['printer', 'ปริ้นเตอร์', 'เครื่องปริ้น', 'เครื่องพิมพ์'],
    'หูฟัง': ['earbuds', 'earphone', 'headphone', 'หูฟัง'],
    'earbuds': ['earbuds', 'earphone', 'headphone', 'หูฟัง'],
    'headphone': ['earbuds', 'earphone', 'headphone', 'หูฟัง'],
    'เคส': ['case', 'เคส'],
    'case': ['case', 'เคส'],
    'สายชาร์จ': ['cable', 'สายชาร์จ', 'สาย'],
    'cable': ['cable', 'สายชาร์จ', 'สาย'],
    
    # Months - Thai/English
    'มกราคม': ['มกราคม', 'มกรา', 'ม.ค.', 'jan', 'january'],
    'มกรา': ['มกราคม', 'มกรา', 'ม.ค.', 'jan', 'january'],
    'jan': ['มกราคม', 'มกรา', 'ม.ค.', 'jan', 'january'],
    'january': ['มกราคม', 'มกรา', 'ม.ค.', 'jan', 'january'],
    'กุมภาพันธ์': ['กุมภาพันธ์', 'กุมภา', 'ก.พ.', 'feb', 'february'],
    'กุมภา': ['กุมภาพันธ์', 'กุมภา', 'ก.พ.', 'feb', 'february'],
    'ก.พ.': ['กุมภาพันธ์', 'กุมภา', 'ก.พ.', 'feb', 'february'],
    'feb': ['กุมภาพันธ์', 'กุมภา', 'ก.พ.', 'feb', 'february'],
    'february': ['กุมภาพันธ์', 'กุมภา', 'ก.พ.', 'feb', 'february'],
    'มีนาคม': ['มีนาคม', 'มีนา', 'มี.ค.', 'mar', 'march'],
    'มีนา': ['มีนาคม', 'มีนา', 'มี.ค.', 'mar', 'march'],
    'mar': ['มีนาคม', 'มีนา', 'มี.ค.', 'mar', 'march'],
    'march': ['มีนาคม', 'มีนา', 'มี.ค.', 'mar', 'march'],
    'เมษายน': ['เมษายน', 'เมษา', 'เม.ย.', 'apr', 'april'],
    'เมษา': ['เมษายน', 'เมษา', 'เม.ย.', 'apr', 'april'],
    'apr': ['เมษายน', 'เมษา', 'เม.ย.', 'apr', 'april'],
    'april': ['เมษายน', 'เมษา', 'เม.ย.', 'apr', 'april'],
    'พฤษภาคม': ['พฤษภาคม', 'พฤษภา', 'พ.ค.', 'may'],
    'พฤษภา': ['พฤษภาคม', 'พฤษภา', 'พ.ค.', 'may'],
    'may': ['พฤษภาคม', 'พฤษภา', 'พ.ค.', 'may'],
    'มิถุนายน': ['มิถุนายน', 'มิถุนา', 'มิ.ย.', 'jun', 'june'],
    'มิถุนา': ['มิถุนายน', 'มิถุนา', 'มิ.ย.', 'jun', 'june'],
    'jun': ['มิถุนายน', 'มิถุนา', 'มิ.ย.', 'jun', 'june'],
    'june': ['มิถุนายน', 'มิถุนา', 'มิ.ย.', 'jun', 'june'],
    'กรกฎาคม': ['กรกฎาคม', 'กรกฎา', 'ก.ค.', 'jul', 'july'],
    'กรกฎา': ['กรกฎาคม', 'กรกฎา', 'ก.ค.', 'jul', 'july'],
    'jul': ['กรกฎาคม', 'กรกฎา', 'ก.ค.', 'jul', 'july'],
    'july': ['กรกฎาคม', 'กรกฎา', 'ก.ค.', 'jul', 'july'],
    'สิงหาคม': ['สิงหาคม', 'สิงหา', 'ส.ค.', 'aug', 'august'],
    'สิงหา': ['สิงหาคม', 'สิงหา', 'ส.ค.', 'aug', 'august'],
    'aug': ['สิงหาคม', 'สิงหา', 'ส.ค.', 'aug', 'august'],
    'august': ['สิงหาคม', 'สิงหา', 'ส.ค.', 'aug', 'august'],
    'กันยายน': ['กันยายน', 'กันยา', 'ก.ย.', 'sep', 'september'],
    'กันยา': ['กันยายน', 'กันยา', 'ก.ย.', 'sep', 'september'],
    'sep': ['กันยายน', 'กันยา', 'ก.ย.', 'sep', 'september'],
    'september': ['กันยายน', 'กันยา', 'ก.ย.', 'sep', 'september'],
    'ตุลาคม': ['ตุลาคม', 'ตุลา', 'ต.ค.', 'oct', 'october'],
    'ตุลา': ['ตุลาคม', 'ตุลา', 'ต.ค.', 'oct', 'october'],
    'oct': ['ตุลาคม', 'ตุลา', 'ต.ค.', 'oct', 'october'],
    'october': ['ตุลาคม', 'ตุลา', 'ต.ค.', 'oct', 'october'],
    'พฤศจิกายน': ['พฤศจิกายน', 'พฤศจิกา', 'พ.ย.', 'nov', 'november'],
    'พฤศจิกา': ['พฤศจิกายน', 'พฤศจิกา', 'พ.ย.', 'nov', 'november'],
    'nov': ['พฤศจิกายน', 'พฤศจิกา', 'พ.ย.', 'nov', 'november'],
    'november': ['พฤศจิกายน', 'พฤศจิกา', 'พ.ย.', 'nov', 'november'],
    'ธันวาคม': ['ธันวาคม', 'ธันวา', 'ธ.ค.', 'dec', 'december'],
    'ธันวา': ['ธันวาคม', 'ธันวา', 'ธ.ค.', 'dec', 'december'],
    'dec': ['ธันวาคม', 'ธันวา', 'ธ.ค.', 'dec', 'december'],
    'december': ['ธันวาคม', 'ธันวา', 'ธ.ค.', 'dec', 'december'],
    
    # Computer Brands
    'เลโนโว่': ['lenovo', 'เลโนโว่', 'เลอโนโว'],
    'lenovo': ['lenovo', 'เลโนโว่', 'เลอโนโว'],
    'เดลล์': ['dell', 'เดลล์'],
    'dell': ['dell', 'เดลล์'],
    'เอซุส': ['asus', 'เอซุส', 'อัสซุส'],
    'asus': ['asus', 'เอซุส', 'อัสซุส'],
    'เอเซอร์': ['acer', 'เอเซอร์'],
    'acer': ['acer', 'เอเซอร์'],
    'ไมโครซอฟท์': ['microsoft', 'ไมโครซอฟท์', 'ไมโครซอฟ'],
    'microsoft': ['microsoft', 'ไมโครซอฟท์', 'ไมโครซอฟ'],
    
    # Banks
    'กสิกร': ['kbank', 'กสิกร', 'กสิกรไทย'],
    'kbank': ['kbank', 'กสิกร', 'กสิกรไทย'],
    'ไทยพาณิชย์': ['scb', 'ไทยพาณิชย์'],
    'scb': ['scb', 'ไทยพาณิชย์'],
    'กรุงเทพ': ['bbl', 'กรุงเทพ', 'ธนาคารกรุงเทพ'],
    'bbl': ['bbl', 'กรุงเทพ', 'ธนาคารกรุงเทพ'],
    'กรุงศรี': ['krungsri', 'กรุงศรี', 'กรุงศรีอยุธยา'],
    'krungsri': ['krungsri', 'กรุงศรี', 'กรุงศรีอยุธยา'],
    'กรุงไทย': ['ktb', 'ktc', 'กรุงไทย'],
    'ktc': ['ktc', 'กรุงไทย', 'เคทีซี'],
    'ยูโอบี': ['uob', 'ยูโอบี'],
    'uob': ['uob', 'ยูโอบี'],
    'ทีเอ็มบี': ['ttb', 'tmb', 'ทีเอ็มบี', 'ทีทีบี'],
    'ttb': ['ttb', 'tmb', 'ทีเอ็มบี', 'ทีทีบี'],
    'อิออน': ['aeon', 'อิออน'],
    'aeon': ['aeon', 'อิออน'],
    
    # Gaming
    'เกม': ['game', 'gaming', 'เกม', 'เกมมิ่ง'],
    'game': ['game', 'gaming', 'เกม', 'เกมมิ่ง'],
    'gaming': ['game', 'gaming', 'เกม', 'เกมมิ่ง'],
    'เพลย์สเตชั่น': ['playstation', 'ps5', 'ps4', 'เพลย์สเตชั่น'],
    'playstation': ['playstation', 'ps5', 'ps4', 'เพลย์สเตชั่น'],
    'ps5': ['playstation', 'ps5', 'เพลย์สเตชั่น'],
    
    # Common terms
    'โปร': ['promotion', 'โปร', 'โปรโมชั่น', 'โปรโมชัน'],
    'โปรโมชั่น': ['promotion', 'โปร', 'โปรโมชั่น', 'โปรโมชัน'],
    'promotion': ['promotion', 'โปร', 'โปรโมชั่น', 'โปรโมชัน'],
    'ผ่อน': ['ผ่อน', 'installment', '0%', 'ผ่อน0%'],
    'ส่วนลด': ['ส่วนลด', 'discount', 'ลด', 'ลดราคา'],
    'discount': ['ส่วนลด', 'discount', 'ลด', 'ลดราคา'],
    'เครดิต': ['credit', 'เครดิต', 'บัตรเครดิต'],
    'credit': ['credit', 'เครดิต', 'บัตรเครดิต'],
    'อินเซนทีฟ': ['incentive', 'อินเซนทีฟ'],
    'incentive': ['incentive', 'อินเซนทีฟ'],
    'ทรู': ['true', 'ทรู', 'truemove'],
    'true': ['true', 'ทรู', 'truemove'],
    'เอไอเอส': ['ais', 'เอไอเอส'],
    'ais': ['ais', 'เอไอเอส'],
    'ดีแทค': ['dtac', 'ดีแทค'],
    'dtac': ['dtac', 'ดีแทค'],
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
        
        # Check for old years in title OR description (dynamically calculated)
        current_year = datetime.now().year
        current_thai_year = current_year + 543
        old_years_christian = [str(y) for y in range(2020, current_year)]
        old_years_thai = [str(y) for y in range(2563, current_thai_year)]
        
        text_to_check = title + ' ' + description
        for year in old_years_christian + old_years_thai:
            if year in text_to_check:
                return True
        
        return False

    def load_data(self):
        # Check file age and update if needed
        self.check_and_update_data()
        
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    all_promos = json.load(f)
                    
                    # Filter out expired promotions
                    self.promotions = [p for p in all_promos if not self.is_expired(p)]
                    print(f"Loaded {len(self.promotions)} active promotions (filtered {len(all_promos) - len(self.promotions)} expired)")
            except Exception as e:
                print(f"Error loading data: {e}")
        else:
            print("Warning: promotions.json not found.")

    def check_and_update_data(self):
        """Check if data file is old or missing, and fetch new data if needed."""
        should_update = False
        
        if not os.path.exists(DATA_FILE):
            print("Data file missing. Triggering update...")
            should_update = True
        else:
            # Check file age (1 hour = 3600 seconds)
            file_mod_time = os.path.getmtime(DATA_FILE)
            current_time = datetime.now().timestamp()
            if current_time - file_mod_time > 3600:
                print("Data file is older than 1 hour. Triggering update...")
                should_update = True
        
        if should_update:
            try:
                # Add src to path for import
                import sys
                sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                
                from src.utils.fetcher import login, fetch_promotions_data
                # We need process_promotions from api/promotions (or move it to utils?)
                # For now, let's import it carefully
                sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                from api.promotions import process_promotions
                
                print("Logging in to fetch new data...")
                token = login()
                if token:
                    print("Fetching promotions...")
                    raw_data = fetch_promotions_data(token)
                    if raw_data:
                        print(f"Processing {len(raw_data)} items...")
                        processed_data = process_promotions(raw_data)
                        
                        # Save to file
                        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
                        with open(DATA_FILE, "w", encoding="utf-8") as f:
                            json.dump(processed_data, f, ensure_ascii=False, indent=2)
                        print("Data updated successfully.")
            except Exception as e:
                print(f"Failed to auto-update data: {e}")


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
        
        # Expand query using synonyms
        search_terms = [query]
        if query in SYNONYMS:
            search_terms.extend(SYNONYMS[query])
            search_terms = list(set(search_terms))  # Remove duplicates
        
        results = []
        
        for promo in self.promotions:
            score = 0
            
            title = promo.get('title', '')
            description = promo.get('description', '')
            content = promo.get('content', '')
            promo_type = promo.get('promotion_type', '')
            
            title_lower = title.lower()
            desc_lower = description.lower()
            content_lower = content.lower()
            type_lower = promo_type.lower()
            
            matched_terms = set()
            
            # Check all synonym variants
            for term in search_terms:
                term_len = len(term)
                
                # 1. Exact Match Logic
                if term in title_lower:
                    if re.search(r'\b' + re.escape(term) + r'\b', title_lower):
                        score += 100
                    else:
                        score += 70
                    matched_terms.add(term)
                
                if term in type_lower:
                    score += 50
                    matched_terms.add(term)
                
                if term_len >= 5 and term in desc_lower:
                    score += 20
                    matched_terms.add(term)
                
                if term_len >= 6 and term in content_lower:
                    score += 10
                    matched_terms.add(term)
                
                # Keyword match
                keywords = promo.get('keywords', [])
                if term_len >= 3:
                    for kw in keywords:
                        if kw and len(kw) >= 3 and kw not in STOP_WORDS:
                            if term == kw.lower():
                                score += 25
                                matched_terms.add(term)
                                break
            
            # 2. Fuzzy Match (If no exact match found yet)
            if score == 0 and len(query) > 4:
                # Check fuzzy match against title only
                import difflib
                
                # Split title into words to check against query
                title_words = title_lower.split()
                for word in title_words:
                    if len(word) > 4:
                        ratio = difflib.SequenceMatcher(None, query, word).ratio()
                        if ratio > 0.8:  # 80% similarity
                            score += 40
                            matched_terms.add(word)
                            break
            
            if score > 0:
                # Add highlighting
                highlighted_title = title
                highlighted_desc = description
                
                # Simple highlight replacement (case-insensitive)
                for term in matched_terms:
                    # Escape special regex chars
                    pattern = re.compile(re.escape(term), re.IGNORECASE)
                    highlighted_title = pattern.sub(lambda m: f"<em>{m.group(0)}</em>", highlighted_title)
                    highlighted_desc = pattern.sub(lambda m: f"<em>{m.group(0)}</em>", highlighted_desc)
                
                promo_copy = promo.copy()
                promo_copy['highlight'] = {
                    'title': highlighted_title,
                    'description': highlighted_desc
                }
                
                results.append((promo_copy, score))
        
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

