import os
import sys
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
from dotenv import load_dotenv

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

@app.get("/")
def root():
    return {"status": "ok", "service": "Manual Knowledge Bot (Keyword Search)"}

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
    user_msg = event.message.text.strip()
    print(f"Received: {user_msg}")
    
    # 1. Search
    results = search_engine.search(user_msg)
    
    if not results and user_msg == "ล่าสุด":
        results = search_engine.get_latest()
    
    if not results:
        reply_msg = TextSendMessage(text=f"ไม่พบโปรโมชั่นที่เกี่ยวกับ '{user_msg}' ครับ\nลองคำอื่น หรือพิมพ์ 'ล่าสุด' เพื่อดูโปรใหม่ๆ")
    else:
        try:
            # Build Flex Message Carousel
            bubbles = []
            for promo in results[:5]:  # Limit to 5 cards
                # Clean up title
                title = promo['title'].split('\n')[-1].strip() if '\n' in promo['title'] else promo['title']
                if len(title) > 40:
                    title = title[:37] + "..."
                
                # Get content - show short preview
                content = promo.get('content', '') or promo.get('description', '')
                if len(content) > 200:
                    content = content[:197] + "..."
                
                # Get attachments and promo ID
                promo_id = promo.get('id', 0)
                attachments = promo.get('attachments', [])
                
                # Build action buttons (attachments only, no detail button)
                actions = []
                
                # Add attachment buttons (show ALL with original names)
                for idx, att in enumerate(attachments, 1):
                    att_url = att.get('url', '')
                    att_text = att.get('text', '').strip()
                    
                    # Clean up text (remove trailing > and extra spaces)
                    att_text = att_text.rstrip('>').strip()
                    
                    # Use file name from text, truncated to LINE's 20 char limit
                    if att_text:
                        label = att_text[:20] if len(att_text) <= 20 else att_text[:17] + "..."
                    else:
                        # Fallback: extract filename from URL
                        filename = att_url.split('/')[-1].split('.')[0][:15]
                        label = filename if filename else f"ไฟล์ {idx}"
                    
                    if att_url and not att_url.endswith('#'):
                        actions.append({
                            "type": "button",
                            "style": "secondary",
                            "action": {
                                "type": "uri",
                                "label": label,
                                "uri": att_url
                            }
                        })
                
                # Build bubble
                bubble = {
                    "type": "bubble",
                    "size": "mega",
                    "header": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": title,
                                "weight": "bold",
                                "size": "md",
                                "wrap": True,
                                "maxLines": 2
                            }
                        ],
                        "backgroundColor": "#27ACB2"
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": content if content else "ไม่มีรายละเอียด",
                                "size": "sm",
                                "wrap": True,
                                "color": "#666666"
                            },
                            {
                                "type": "text",
                                "text": "👆 แตะเพื่อดูรายละเอียดเพิ่มเติม",
                                "size": "xs",
                                "color": "#27ACB2",
                                "margin": "md"
                            }
                        ],
                        "action": {
                            "type": "uri",
                            "uri": f"https://rag-bot-chat.vercel.app/view/{promo_id}"
                        }
                    }
                }
                
                # Add footer with buttons if any
                if actions:
                    bubble["footer"] = {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": actions
                    }
                
                bubbles.append(bubble)
            
            # Create carousel
            flex_content = {
                "type": "carousel",
                "contents": bubbles
            }
            
            reply_msg = FlexSendMessage(
                alt_text=f"พบ {len(results)} โปรโมชั่น",
                contents=flex_content
            )
            
        except Exception as e:
            print(f"Error building Flex: {e}")
            # Fallback to text
            reply_msg = TextSendMessage(text=f"พบ {len(results)} รายการ แต่ไม่สามารถแสดง Card ได้")

    line_bot_api.reply_message(event.reply_token, reply_msg)
