"""
Vercel API Route: /api/promotions
Fetches promotions directly from vrcomseven API and returns as JSON.
Uses caching to minimize API calls.
"""
import os
import json
import uuid
import logging
from datetime import datetime
from http.server import BaseHTTPRequestHandler

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import httpx
except ImportError:
    httpx = None

# API Configuration
LOGIN_URL = "https://api.vrcomseven.com/users/web_login"
PROMOTIONS_URL = "https://api.vrcomseven.com/v1/promotions"
USERNAME = os.environ.get("VR_USERNAME", "25622")
PASSWORD = os.environ.get("VR_PASSWORD", "91544")

# Simple in-memory cache
_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 300  # 5 minutes


# Add src to path for import
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional
from src.utils.fetcher import login, fetch_promotions_data

def fetch_promotions(token: str) -> list:
    """Wrapper for fetch_promotions_data."""
    return fetch_promotions_data(token)


def process_promotions(raw_promotions: list) -> list:
    """Transform raw API data to our format."""
    results = []
    
    for promo in raw_promotions:
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
        
        attachments = []
        for att in promo.get("attachments", []) or []:
            attachments.append({
                "text": att.get("title", "ดาวน์โหลด"),
                "url": att.get("uri", "")
            })
        
        text = f"{promo.get('title', '')} {promo.get('description', '')} {promo.get('category', '')}"
        keywords = list(set([w.lower() for w in text.split() if len(w) > 2 and w.lower() not in {'none', 'null', 'ที่', 'และ', 'หรือ', 'ของ', 'ใน'} and not w.endswith(')') and not w.startswith('(')]))[:30]
        
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


def get_promotions_with_cache() -> list:
    """Get promotions with caching."""
    global _cache
    
    now = datetime.now().timestamp()
    if _cache["data"] and (now - _cache["timestamp"] < CACHE_TTL):
        return _cache["data"]
    
    token = login()
    if not token:
        return _cache.get("data") or []
    
    raw = fetch_promotions(token)
    if not raw:
        return _cache.get("data") or []
    
    promotions = process_promotions(raw)
    _cache = {"data": promotions, "timestamp": now}
    
    return promotions


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        try:
            promotions = get_promotions_with_cache()
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "s-maxage=300, stale-while-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            response = {
                "success": True,
                "count": len(promotions),
                "data": promotions
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
