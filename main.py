import os
import logging
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, InlineQueryHandler, CallbackQueryHandler

# سيرفر وهمي لمنع Render من إيقاف البوت
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Whisper Bot is Alive!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

logging.basicConfig(level=logging.INFO)

TOKEN = "8983390041:AAFPEbUCr4WuXwj2yznl4qWZNQJ5EZouMlI"
whispers_db = {}

async def start_command(update, context):
    welcome_text = (
        "أهلاً بك في **بوت الهمسات السرية** البسيط والمباشر! 🤫✨\n\n"
        "--- 💡 **طريقة الاستخدام السهلة** ---\n\n"
        "فقط اكتب في أي شات أو جروب:\n"
        "`@vv_cbot @username الرسالة`\n\n"
        "وستظهر لك قائمة خيارات فاخرة لتختار منها نوع الهمسة بنقرة واحدة! 🎯"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def inline_whisper(update, context):
    query = update.inline_query.query.strip()
    if not query:
        return

    sender = update.inline_query.from_user
    sender_id = sender.id
    sender_name = sender.first_name
    sender_username = sender.username.lower() if sender.username else ""

    parts = query.split(' ', 1)
    if len(parts) < 2:
        return

    target_user = parts[0].strip().lower()
    whisper_text = parts[1].strip()

    if not target_user.startswith('@'):
        return

    clean_target = target_user.replace('@', '')

    # إنشاء معرفات لكل خيار من الخيارات
    id_normal = str(uuid.uuid4())[:8]
    id_anon = str(uuid.uuid4())[:8]
    id_public = str(uuid.uuid4())[:8]

    # حفظ الخيارات في قاعدة البيانات
    whispers_db[id_normal] = {
        'target': clean_target, 'sender_id': sender_id, 'sender_name': sender_name,
        'sender_username': sender_username, 'text': whisper_text, 'type': 'normal', 'read': False
    }
    
    whispers_db[id_anon] = {
        'target': clean_target, 'sender_id': sender_id, 'sender_name': sender_name,
        'sender_username': sender_username, 'text': whisper_text, 'type': 'anon', 'read': False
    }

    whispers_db[id_public] = {
        'target': clean_target, 'sender_id': sender_id, 'sender_name': sender_name,
        'sender_username': sender_username, 'text': whisper_text, 'type': 'public', 'read': False
    }

    # الأزرار التي ستظهر بعد الإرسال
    kb_normal = InlineKeyboardMarkup([[InlineKeyboardButton("🔒 اضغط لقراءة الهمسة", callback_data=f"show_{id_normal}")]])
    kb_anon = InlineKeyboardMarkup([[InlineKeyboardButton("🤫 همسة سرية من مجهول", callback_data=f"show_{id_anon}")]])
    kb_public = InlineKeyboardMarkup([[InlineKeyboardButton("🌐 همسة عامة للجميع", callback_data=f"show_{id_public}")]])

    # الخيارات التي تظهر للمستخدم أثناء الكتابة
    results = [
        InlineQueryResultArticle(
            id=id_normal,
            title=f"🔒 همسة عادية إلى {target_user}",
            description="يظهر اسمك للمستلم عند فتح الهمسة",
            input_message_content=InputTextMessageContent(
                message_text=f"🔒 **همسة سرية موجهة إلى [{target_user}]**\nلا يمكن لأحد قراءتها غيره.",
                parse_mode="Markdown"
            ),
            reply_markup=kb_normal
        ),
        InlineQueryResultArticle(
            id=id_anon,
            title=f"🤫 همسة مجهولة إلى {target_user}",
            description="لن يظهر اسمك للمستلم (مجهول)",
            input_message_content=InputTextMessageContent(
                message_text=f"🤫 **همسة مجهولة موجهة إلى [{target_user}]**\nلا يمكن لأحد قراءتها غيره.",
                parse_mode="Markdown"
            ),
            reply_markup=kb_anon
        ),
        InlineQueryResultArticle(
            id=id_public,
            title=f"🌐 همسة عامة إلى {target_user}",
            description="يمكن لجميع أعضاء الشات قراءتها",
            input_message_content=InputTextMessageContent(
                message_text=f"🌐 **همسة عامة موجهة إلى [{target_user}]**",
                parse_mode="Markdown"
            ),
            reply_markup=kb_public
        )
    ]

    await update.inline_query.answer(results, cache_time=1)

async def handle_click(update, context):
    query = update.callback_query
    data = query.data

    if data.startswith("show_"):
        whisper_id = data.split("show_")[1]
        whisper = whispers_db.get(whisper_id)

        if not whisper:
            await query.answer("❌ عذراً، هذه الهمسة قديمة أو غير موجودة.", show_alert=True)
            return

        user = query.from_user
        current_username = user.username.lower() if user.username else ""
        current_id = user.id

        target_name = whisper['target']
        sender_id = whisper['sender_id']
        sender_username = whisper['sender_username']

        # إذا كانت عامة يسمح للكل، وإلا يقتصر على المستلم والمرسل
        can_read = (whisper['type'] == 'public' or 
                    current_username == target_name or 
                    current_id == sender_id or 
                    (sender_username and current_username == sender_username))

        if can_read:
            sender_info = "شخص مجهول 🤫" if whisper['type'] == 'anon' else whisper['sender_name']
            msg = f"📩 من: {sender_info}\n\n💬 الهمسة: {whisper['text']}"
            
            await query.answer(msg, show_alert=True)

            # إشعار القراءة للمرسل
            if current_id != sender_id and not whisper['read']:
                whisper['read'] = True
                try:
                    await context.bot.send_message(
                        chat_id=sender_id,
                        text=f"👁️ **تمت قراءة همستك!**\nقام {user.first_name} بفتح الهمسة الآن."
                    )
                except Exception:
                    pass
        else:
            await query.answer("🚫 هذه الهمسة ليست موجهة لك!", show_alert=True)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(InlineQueryHandler(inline_whisper))
    app.add_handler(CallbackQueryHandler(handle_click))
    app.run_polling()

if __name__ == "__main__":
    main()
