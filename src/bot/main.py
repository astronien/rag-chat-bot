import os
import sys
from fastapi import FastAPI, Request, HTTPException
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
                
                # Get content - show more text
                content = promo.get('content', '') or promo.get('description', '')
                if len(content) > 1000:
                    content = content[:997] + "..."
                
                # Get link and attachments
                link = promo.get('link', '')
                attachments = promo.get('attachments', [])
                
                # Build action buttons
                actions = []
                if link:
                    actions.append({
                        "type": "button",
                        "style": "primary",
                        "action": {
                            "type": "uri",
                            "label": "ดูรายละเอียด",
                            "uri": link
                        }
                    })
                
                # Add attachment buttons (max 4)
                for idx, att in enumerate(attachments[:4], 1):
                    att_url = att.get('url', '')
                    # Use simple numbered label (LINE limit is 20 chars including emoji)
                    if '.pdf' in att_url.lower():
                        label = f"PDF {idx}"
                    elif '.xls' in att_url.lower():
                        label = f"Excel {idx}"
                    else:
                        label = f"ไฟล์ {idx}"
                    
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
                            }
                        ]
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
