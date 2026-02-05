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
    
    if not results:
        # Fallback or help
        reply_msg = TextSendMessage(text=f"ไม่พบโปรโมชั่นที่เกี่ยวกับ '{user_msg}' ครับ\nลองคำอื่น หรือพิมพ์ 'ล่าสุด' เพื่อดูโปรใหม่ๆ")
        if user_msg == "ล่าสุด":
            results = search_engine.get_latest()
    
    if results:
        # Create Flex Message or Simple List
        try:
            lines = [f"🔍 พบ {len(results)} รายการ:"]
            for promo in results[:3]: # Limit to 3 (more details per item)
                # Clean up title (remove date prefixes)
                title = promo['title'].split('\n')[-1].strip() if '\n' in promo['title'] else promo['title']
                
                # Get full content or description
                content = promo.get('content', '') or promo.get('description', '')
                
                # Get link
                link = promo.get('link', '')
                
                # Get attachment URLs
                attachments = promo.get('attachments', [])
                
                # Build message
                msg_parts = [f"📌 {title}"]
                if content:
                    msg_parts.append(content)
                if link:
                    msg_parts.append(f"🔗 รายละเอียด: {link}")
                
                # Add attachment links
                if attachments:
                    msg_parts.append("\n📎 ไฟล์แนบ:")
                    for att in attachments[:5]:  # Limit to 5 attachments
                        att_text = att.get('text', 'ไฟล์')
                        att_url = att.get('url', '')
                        if att_url and not att_url.endswith('#'):
                            msg_parts.append(f"• {att_text}\n  {att_url}")
                
                lines.append("\n".join(msg_parts))
            
            if len(results) > 3:
                lines.append(f"...และอีก {len(results)-3} รายการ")

            reply_msg = TextSendMessage(text="\n\n".join(lines))
        except Exception as e:
            print(f"Error building reply: {e}")
            reply_msg = TextSendMessage(text="เกิดข้อผิดพลาดในการแสดงผล")

    line_bot_api.reply_message(
        event.reply_token,
        reply_msg
    )
