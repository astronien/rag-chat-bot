import json
import os
from pathlib import Path

# Get project root (2 levels up from src/search/engine.py)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "promotions.json"

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

    def get_by_id(self, promo_id: int):
        for promo in self.promotions:
            if promo.get('id') == promo_id:
                return promo
        return None
