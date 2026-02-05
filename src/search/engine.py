import json
import os

DATA_FILE = "data/promotions.json"

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
        results = []
        
        for promo in self.promotions:
            # Check Title
            if query in promo['title'].lower():
                results.append(promo)
                continue
            
            # Check Description
            if query in promo.get('description', '').lower():
                results.append(promo)
                continue
            
            # Check Content
            if query in promo.get('content', '').lower():
                results.append(promo)
                continue
                
            # Check Keywords (Exact match for now)
            if query in promo.get('keywords', []):
                results.append(promo)
                continue

        return results

    def get_latest(self, n=5):
        return self.promotions[:n]
