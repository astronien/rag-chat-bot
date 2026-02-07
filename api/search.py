"""
Vercel API Route: /api/search
Handles search requests with pagination, filtering, and CORS support.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from src.search.engine import SearchEngine
except ImportError:
    # Fallback for Vercel environment where src might be unpredictable
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.search.engine import SearchEngine

# Initialize engine once
search_engine = SearchEngine()

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        try:
            # Parse query parameters
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)
            
            query = params.get('q', [''])[0]
            page = int(params.get('page', ['1'])[0])
            limit = int(params.get('limit', ['20'])[0])
            category = params.get('category', [''])[0]
            promo_type = params.get('type', [''])[0]
            
            # Perform search
            if not query and not category and not promo_type:
                # Default to latest if no query
                results = search_engine.get_latest(n=100)
            else:
                results = search_engine.search(query)
            
            # Apply filters
            if category:
                results = [r for r in results if r.get('category') == category]
            
            if promo_type:
                results = [r for r in results if r.get('promotion_type') == promo_type]
            
            # Pagination
            total_count = len(results)
            total_pages = (total_count + limit - 1) // limit
            
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            
            paginated_results = results[start_idx:end_idx]
            
            # Response
            response = {
                "success": True,
                "data": paginated_results,
                "meta": {
                    "total": total_count,
                    "page": page,
                    "limit": limit,
                    "total_pages": total_pages
                }
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 's-maxage=60, stale-while-revalidate')
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
