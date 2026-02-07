import os
import sys
from urllib.parse import quote, urlparse
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, QuickReply, QuickReplyButton, MessageAction
from dotenv import load_dotenv
import re

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.search.engine import SearchEngine

load_dotenv()

app = FastAPI()
search_engine = SearchEngine()

# Line Config
# Note: CHANNEL_ACCESS_TOKEN is required. 
# If user only provided ID/Secret, we might need to issue short-lived token or use long-lived if set.
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "YOUR_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Store user search sessions for pagination (with timestamps for cleanup)
user_sessions = {}
SESSION_TIMEOUT = 1800  # 30 minutes

import uuid
import time
from datetime import datetime
try:
    import httpx
except ImportError:
    httpx = None

@app.get("/")
def root():
    return {
        "status": "ok", 
        "service": "Manual Knowledge Bot (Keyword Search)",
        "promotions_loaded": len(search_engine.promotions),
        "data_file": str(search_engine.promotions[0].get("id") if search_engine.promotions else "empty")
    }

# Scraper Configuration
VR_LOGIN_URL = "https://api.vrcomseven.com/users/web_login"
VR_PROMOTIONS_URL = "https://api.vrcomseven.com/v1/promotions"
VR_USERNAME = os.getenv("VR_USERNAME", "25622")
VR_PASSWORD = os.getenv("VR_PASSWORD", "91544")

# Simple cache for promotions
_promo_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 300  # 5 minutes

@app.get("/api/promotions")
async def get_promotions():
    """Fetch promotions from vrcomseven API with caching."""
    global _promo_cache
    
    now = datetime.now().timestamp()
    if _promo_cache["data"] and (now - _promo_cache["timestamp"] < CACHE_TTL):
        return {"success": True, "count": len(_promo_cache["data"]), "data": _promo_cache["data"], "cached": True}
    
    if not httpx:
        return {"success": False, "error": "httpx not installed"}
    
    # Login
    try:
        login_resp = httpx.post(
            VR_LOGIN_URL,
            json={"emp_code": VR_USERNAME, "pass": VR_PASSWORD, "device_uuid": str(uuid.uuid4()), "platform": "web"},
            timeout=30
        )
        token_data = login_resp.json().get("data", {})
        token = token_data.get("access_token")
        if not token:
            return {"success": False, "error": "Login failed"}
    except Exception as e:
        return {"success": False, "error": f"Login error: {str(e)}"}
    
    # Fetch promotions
    try:
        promo_resp = httpx.get(
            f"{VR_PROMOTIONS_URL}?perpage=200&sort_by=updated_at&sort_direction=desc&business_units=Apple",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60
        )
        raw = promo_resp.json().get("data", [])
    except Exception as e:
        return {"success": False, "error": f"Fetch error: {str(e)}"}
    
    # Process promotions
    results = []
    for promo in raw:
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
        except Exception as e:
            print(f"Error parsing date: {e}")
            pass
        
        attachments = [{"text": a.get("title", "ดาวน์โหลด"), "url": a.get("uri", "")} for a in (promo.get("attachments") or [])]
        
        results.append({
            "id": promo.get("id"),
            "title": promo.get("title", ""),
            "link": f"https://vrcomseven.com/promotions/{promo.get('id')}",
            "description": promo.get("description", ""),
            "duration": duration,
            "category": promo.get("category", ""),
            "promotion_type": (promo.get("promotion_type") or {}).get("name", ""),
            "attachments": attachments
        })
    
    _promo_cache = {"data": results, "timestamp": now}
    return {"success": True, "count": len(results), "data": results}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_decode = body.decode("utf-8")

    try:
        handler.handle(body_decode, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    return "OK"

# View promotion details (no login required)
@app.get("/view/{promo_id}", response_class=HTMLResponse)
def view_promotion(promo_id: int):
    promo = search_engine.get_by_id(promo_id)
    if not promo:
        return HTMLResponse("<h1>ไม่พบโปรโมชั่น</h1>", status_code=404)
    
    title = promo.get('title', 'โปรโมชั่น')
    content = promo.get('content', '') or promo.get('description', '')
    attachments = promo.get('attachments', [])
    
    # Build attachments HTML
    att_html = ""
    if attachments:
        att_html = "<h3>📎 ไฟล์แนบ</h3><ul>"
        for att in attachments:
            att_text = att.get('text', 'ไฟล์').rstrip('>').strip()
            att_url = att.get('url', '')
            if att_url:
                att_html += f'<li><a href="{att_url}" target="_blank">{att_text}</a></li>'
        att_html += "</ul>"
    
    html = f'''<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto; background: #f5f5f5; }}
        .card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ color: #27ACB2; font-size: 1.4em; }}
        h3 {{ color: #333; margin-top: 20px; }}
        .content {{ white-space: pre-wrap; line-height: 1.6; color: #444; }}
        ul {{ padding-left: 20px; }}
        li {{ margin: 8px 0; }}
        a {{ color: #27ACB2; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{title}</h1>
        <div class="content">{content}</div>
        {att_html}
    </div>
</body>
</html>'''
    return HTMLResponse(html)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_msg = event.message.text.strip()
    print(f"Received: {user_msg}")
    
    # Cleanup old sessions (older than 30 minutes)
    current_time = time.time()
    expired_users = [uid for uid, data in user_sessions.items() 
                     if current_time - data.get('timestamp', 0) > SESSION_TIMEOUT]
    for uid in expired_users:
        del user_sessions[uid]
    
    # Help command
    help_commands = ['ช่วยเหลือ', 'วิธีใช้', 'help', '?']
    if user_msg.lower() in help_commands:
        help_text = """🤖 วิธีใช้งาน Bot

📝 พิมพ์คำค้นหา เช่น:
• "iphone" หรือ "ไอโฟน"
• "ผ่อน 0%" หรือ "ผ่อน"
• "kbank" หรือ "กสิกร"
• "airpods" หรือ "แอร์พอด"

⚡ คำสั่งพิเศษ:
• "ล่าสุด" - ดูโปรโมชั่นใหม่ล่าสุด
• "หน้า 2" - ดูหน้าถัดไป

🏷️ หมวดหมู่ยอดนิยม:
• iPhone • Mac • iPad
• Credit Card • Incentive"""
        reply_msg = TextSendMessage(
            text=help_text,
            quick_reply=QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="ล่าสุด", text="ล่าสุด")),
                QuickReplyButton(action=MessageAction(label="iPhone", text="iphone")),
                QuickReplyButton(action=MessageAction(label="ผ่อน 0%", text="ผ่อน")),
                QuickReplyButton(action=MessageAction(label="บัตรเครดิต", text="credit card")),
                QuickReplyButton(action=MessageAction(label="Incentive", text="incentive")),
            ])
        )
        line_bot_api.reply_message(event.reply_token, reply_msg)
        return
    
    # Check for page navigation command (e.g., "หน้า 2", "หน้า2")
    page_match = re.match(r'^หน้า\s*(\d+)$', user_msg)
    
    if page_match:
        page_num = int(page_match.group(1))
        # Get cached results from session
        if user_id in user_sessions and user_sessions[user_id].get('results'):
            results = user_sessions[user_id]['results']
            query = user_sessions[user_id].get('query', 'ค้นหา')
        else:
            reply_msg = TextSendMessage(text="ไม่มีผลการค้นหาก่อนหน้า กรุณาค้นหาใหม่")
            line_bot_api.reply_message(event.reply_token, reply_msg)
            return
    else:
        # New search
        page_num = 1
        
        # Check for special commands
        if user_msg == "ล่าสุด":
            results = search_engine.get_latest(n=50)  # Get more for pagination
            query = "ล่าสุด"
        else:
            results = search_engine.search(user_msg)
            query = user_msg
        
        # Store in session for pagination (with timestamp)
        user_sessions[user_id] = {'results': results, 'query': query, 'timestamp': current_time}
    
    if not results:
        reply_msg = TextSendMessage(text=f"ไม่พบโปรโมชั่นที่เกี่ยวกับ '{user_msg}' ครับ\nลองคำอื่น หรือพิมพ์ 'ล่าสุด' เพื่อดูโปรใหม่ๆ")
    else:
        try:
            # Pagination
            per_page = 12
            total_pages = (len(results) + per_page - 1) // per_page
            start_idx = (page_num - 1) * per_page
            end_idx = start_idx + per_page
            page_results = results[start_idx:end_idx]
            
            if not page_results:
                reply_msg = TextSendMessage(text=f"ไม่มีหน้า {page_num}")
                line_bot_api.reply_message(event.reply_token, reply_msg)
                return
            
            # Build Flex Message Carousel
            bubbles = []
            for promo in page_results:
                # Clean up title
                title = promo['title'].split('\n')[-1].strip() if '\n' in promo['title'] else promo['title']
                
                # Get content
                content = promo.get('content', '') or promo.get('description', '')
                if len(content) > 200:
                    content = content[:197] + "..."
                
                promo_id = promo.get('id', 0)
                attachments = promo.get('attachments', [])
                
                # Build attachment buttons
                actions = []
                for idx, att in enumerate(attachments, 1):
                    att_url = att.get('url', '')
                    
                    # URL encode Thai characters
                    if att_url:
                        try:
                            parsed = urlparse(att_url)
                            encoded_path = quote(parsed.path, safe='/')
                            att_url = f"{parsed.scheme}://{parsed.netloc}{encoded_path}"
                        except:
                            pass
                    
                    att_text = att.get('text', '').strip().rstrip('>').strip()
                    
                    if att_text:
                        label = att_text[:20] if len(att_text) <= 20 else att_text[:17] + "..."
                    else:
                        filename = att_url.split('/')[-1].split('.')[0][:15]
                        label = filename if filename else f"ไฟล์ {idx}"
                    
                    if att_url and att_url.startswith(('http://', 'https://')) and not att_url.endswith('#'):
                        actions.append({
                            "type": "button",
                            "style": "secondary",
                            "action": {"type": "uri", "label": label, "uri": att_url}
                        })
                
                # Build bubble
                bubble = {
                    "type": "bubble",
                    "size": "mega",
                    "header": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [{"type": "text", "text": title, "weight": "bold", "size": "md", "wrap": True, "maxLines": 2}],
                        "backgroundColor": "#27ACB2"
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {"type": "text", "text": content if content else "ไม่มีรายละเอียด", "size": "sm", "wrap": True, "color": "#666666"},
                            {"type": "text", "text": "👆 แตะเพื่อดูรายละเอียดเพิ่มเติม", "size": "xs", "color": "#27ACB2", "margin": "md"}
                        ],
                        "action": {"type": "uri", "uri": f"https://rag-bot-chat.vercel.app/view/{promo_id}"}
                    }
                }
                
                if actions:
                    bubble["footer"] = {"type": "box", "layout": "vertical", "spacing": "sm", "contents": actions}
                
                bubbles.append(bubble)
            
            # Create carousel
            flex_content = {"type": "carousel", "contents": bubbles}
            
            # Build Quick Reply buttons for pagination
            quick_reply_items = []
            if total_pages > 1:
                for p in range(1, min(total_pages + 1, 14)):  # LINE max 13 quick reply items
                    if p != page_num:
                        quick_reply_items.append(
                            QuickReplyButton(action=MessageAction(label=f"หน้า {p}", text=f"หน้า {p}"))
                        )
            
            # Alt text with pagination info
            alt_text = f"พบ {len(results)} รายการ (หน้า {page_num}/{total_pages})"
            
            if quick_reply_items:
                reply_msg = FlexSendMessage(
                    alt_text=alt_text,
                    contents=flex_content,
                    quick_reply=QuickReply(items=quick_reply_items[:13])
                )
            else:
                reply_msg = FlexSendMessage(alt_text=alt_text, contents=flex_content)
            
        except Exception as e:
            print(f"Error building Flex: {e}")
            reply_msg = TextSendMessage(text=f"พบ {len(results)} รายการ แต่ไม่สามารถแสดง Card ได้")

    line_bot_api.reply_message(event.reply_token, reply_msg)

