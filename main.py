import os
import logging
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, InlineQueryHandler

# سيرفر وهمي لمنع Render من إيقاف البوت
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

# إعدادات تسجيل الأخطاء
logging.basicConfig(level=logging.INFO)

TOKEN = "8983390041:AAFPEbUCr4WuXwj2yznl4qWZNQJ5EZouMlI"
whispers_db = {}

async def start_command(update, context):
    welcome_text = (
        "أهلاً بك في بوت الهمسات السرية! 🤫✨\n\n"
        "إرسال رسائل سرية لا يراها إلا الشخص الموجهة له فقط.\n"
        "--- 💡 **طريقة الاستخدام** ---\n\n"
        "1️⃣ في أي محادثة أو الجروب الذي تريد إرسال الهمسة فيه:\n"
        "   اكتب يوزر البوت في خانة الكتابة:\n"
        "   `@vv_cbot`\n\n"
        "2️⃣ اترك مسافة، ثم اكتب يوزر الشخص المستلم:\n"
        "   `@username`\n\n"
        "3️⃣ اترك مسافة، ثم اكتب نص الهمسة.\n"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def inline_whisper(update, context):
    query = update.inline_query.query.strip()
    if not query:
        return

    parts = query.split(' ', 1)
    if len(parts) < 2:
        return

    target_user = parts[0].strip()
    whisper_text = parts[1].strip()

    if not target_user.startswith('@'):
        return

    whisper_id = str(uuid.uuid4())[:8]
    whispers_db[whisper_id] = {
        'target': target_user.lower(),
        'text': whisper_text,
        'sender': update.inline_query.from_user.first_name
    }

    results = [
        InlineQueryResultArticle(
            id=whisper_id,
            title=f"إرسال همسة سرية إلى {target_user}",
            description="اضغط هنا لإرسال الهمسة (لن يراها غير المستلم)",
            input_message_content=InputTextMessageContent(
                message_text=f"🔒 **همسة سرية موجهة إلى {target_user}**\nلا يمكن لأحد قراءتها غيره.",
                parse_mode="Markdown"
            )
        )
    ]

    await update.inline_query.answer(results, cache_time=1)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(InlineQueryHandler(inline_whisper))
    app.run_polling()

if __name__ == "__main__":
    main()
