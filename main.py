import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

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

import logging
import uuid
from telegram import InlineQueryResultArticle...
import logging
import uuid
from telegram import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, InlineQueryHandler, CallbackQueryHandler, CommandHandler, ContextTypes

TOKEN = "8983390041:AAFPEbUCr4WuXwj2yznl4qWZNQJ5EZouMlI"
whispers_db = {}

logging.basicConfig(level=logging.INFO)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "أهلاً بك في بوت الهمسات السرية! 🤫✨\n\n"
        "يمكنك استخدام البوت في أي محادثة أو مجموعة لإرسال رسائل سرية لا يراها إلا الشخص الموجهة له فقط.\n\n"
        "--- 💡 **طريقة الاستخدام** ---\n\n"
        "1️⃣ افتح المحادثة أو الجروب الذي تريد إرسال الهمسة فيه.\n"
        "2️⃣ اكتب يوزر البوت في خانة الكتابة:\n"
        "   `@vv_cbot`\n"
        "3️⃣ اترك مسافة، ثم اكتب يوزر الشخص المستلم:\n"
        "   `@username`\n"
        "4️⃣ اترك مسافة، ثم اكتب نص الهمسة.\n\n"
        "📌 **مثال للهمسة المخصصة شخصياً:**\n"
        "`@vv_cbot @username هلا بالخوي هذي رسالة سرية`\n\n"
        "📌 **مثال للهمسة العامة (يقرأها أي شخص يضغط الزر):**\n"
        "`@vv_cbot هلا بالجميع هذي همسة عامة`\n\n"
        "اضغط على الخيار الذي يظهر لك فوق خانة الكتابة لإرسال الهمسة فوراً! 🚀"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def inline_whisper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    if not query:
        return

    parts = query.split(" ", 1)
    
    if parts[0].startswith("@") and len(parts) > 1:
        target_user = parts[0].replace("@", "").lower()
        whisper_text = parts[1]
    else:
        target_user = None
        whisper_text = query

    whisper_id = str(uuid.uuid4())[:8]
    whispers_db[whisper_id] = {
        "sender_id": update.inline_query.from_user.id,
        "sender_username": (update.inline_query.from_user.username or "").lower(),
        "sender_name": update.inline_query.from_user.first_name,
        "target_username": target_user,
        "text": whisper_text
    }

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 اضغط لقراءة الهمسة", callback_data=f"whisper_{whisper_id}")]
    ])

    title_text = f"همسة موجهة لـ @{target_user} 🤫" if target_user else "همسة سرية عامة 🤫"
    desc_text = f"الرسالة: {whisper_text}"

    results = [
        InlineQueryResultArticle(
            id=whisper_id,
            title=title_text,
            description=desc_text,
            input_message_content=InputTextMessageContent(f"🤫 **همسة سرية جديدة!**\nمخصصة لـ: {f'@{target_user}' if target_user else 'الجميع'}"),
            reply_markup=keyboard
        )
    ]
    await update.inline_query.answer(results, cache_time=1)

async def handle_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    whisper_id = query.data.replace("whisper_", "")
    clicker_id = query.from_user.id
    clicker_username = (query.from_user.username or "").lower()

    if whisper_id in whispers_db:
        data = whispers_db[whisper_id]
        
        is_sender = (clicker_id == data["sender_id"])
        is_target = (data["target_username"] and clicker_username == data["target_username"])

        if is_sender or is_target or data["target_username"] is None:
            await query.answer(f"💬 همسة من ({data['sender_name']}):\n\n{data['text']}", show_alert=True)
        else:
            await query.answer("🚫 عذراً! هذه الهمسة ليست موجهة لك.", show_alert=True)
    else:
        await query.answer("❌ هذه الهمسة قديمة أو تم حذفها.", show_alert=True)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(InlineQueryHandler(inline_whisper))
    app.add_handler(CallbackQueryHandler(handle_click))
    print("DONE")
    app.run_polling()

if __name__ == "__main__":
    main()
