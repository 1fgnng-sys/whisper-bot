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
        self.wfile.write(b"Advanced Whisper Bot is Alive!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

logging.basicConfig(level=logging.INFO)

TOKEN = "8983390041:AAFPEbUCr4WuXwj2yznl4qWZNQJ5EZouMlI"
whispers_db = {}
user_passwords = {}

async def start_command(update, context):
    welcome_text = (
        "أهلاً بك في **بوت الهمسات السرية المتطور**! 🤫✨\n\n"
        "--- 💡 **طرق الاستخدام العصرية** ---\n\n"
        "1️⃣ **همسة عادية:**\n"
        "`@vv_cbot @username نص الهمسة`\n\n"
        "2️⃣ **همسة مجهولة (بدون اسمك):**\n"
        "`@vv_cbot anon: @username نص الهمسة`\n\n"
        "3️⃣ **همسة بكلمة سر (للكل):**\n"
        "`@vv_cbot pass:1234 نص الهمسة`\n\n"
        "4️⃣ **همسة ذاتية التدمير (تقرأ مرة واحدة):**\n"
        "`@vv_cbot burn: @username نص الهمسة`\n"
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

    is_burn = False
    is_anon = False
    is_pass = False
    pass_code = ""

    # تحليل الأوامر والبادئات بدقة
    if query.startswith("burn:"):
        is_burn = True
        query = query.replace("burn:", "").strip()
    
    if query.startswith("anon:"):
        is_anon = True
        query = query.replace("anon:", "").strip()

    if query.startswith("pass:"):
        is_pass = True
        parts = query.split(' ', 1)
        pass_code = parts[0].replace("pass:", "").strip()
        query = parts[1] if len(parts) > 1 else ""

    parts = query.split(' ', 1)
    if not is_pass and len(parts) < 2:
        return

    target_user = parts[0].strip().lower() if not is_pass else "الجميع (بكلمة سر)"
    whisper_text = parts[1].strip() if not is_pass else query

    whisper_id = str(uuid.uuid4())[:8]

    whispers_db[whisper_id] = {
        'target': target_user.replace('@', ''),
        'sender_id': sender_id,
        'sender_name': sender_name,
        'sender_username': sender_username,
        'text': whisper_text,
        'is_burn': is_burn,
        'is_anon': is_anon,
        'is_pass': is_pass,
        'pass_code': pass_code,
        'read': False
    }

    # تخصيص عنوان الزر حسب نوع الهمسة
    btn_text = "🔒 اضغط لقراءة الهمسة"
    if is_burn:
        btn_text = "💣 همسة متفجرة (مرة واحدة)"
    elif is_pass:
        btn_text = "🔑 همسة بكلمة سر"
    elif is_anon:
        btn_text = "🤫 همسة سرية من مجهول"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_text, callback_data=f"show_{whisper_id}")]
    ])

    title_text = f"إرسال همسة إلى {target_user}"
    if is_pass:
        title_text = f"🔑 همسة محمية برمز: {pass_code}"
    elif is_anon:
        title_text = f"🤫 همسة مجهولة إلى {target_user}"

    results = [
        InlineQueryResultArticle(
            id=whisper_id,
            title=title_text,
            description="اضغط هنا لإرسال الهمسة السرية",
            input_message_content=InputTextMessageContent(
                message_text=f"🔒 **همسة سرية موجهة إلى [{target_user}]**\nلا يمكن لأحد قراءتها غيره.",
                parse_mode="Markdown"
            ),
            reply_markup=keyboard
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
            await query.answer("❌ عذراً، هذه الهمسة تدمرت أو غير موجودة.", show_alert=True)
            return

        user = query.from_user
        current_username = user.username.lower() if user.username else ""
        current_id = user.id

        if whisper['is_pass']:
            user_passwords[current_id] = whisper_id
            await query.answer("🔑 هذه الهمسة محمية برمز سري!", show_alert=True)
            return

        target_name = whisper['target']
        sender_id = whisper['sender_id']
        sender_username = whisper['sender_username']

        can_read = (current_username == target_name or 
                    current_id == sender_id or 
                    (sender_username and current_username == sender_username))

        if can_read:
            # تمييز المرسل: إذا كانت مجهولة يظهر "مجهول"، وإذا كانت عادية يظهر اسمه
            sender_info = "شخص مجهول 🤫" if whisper['is_anon'] else whisper['sender_name']
            msg = f"📩 من: {sender_info}\n\n💬 الهمسة: {whisper['text']}"
            
            await query.answer(msg, show_alert=True)

            # إشعار للمرسل بقراءة الهمسة (فقط إذا لم تكن مجهولة أو لتنبيهه سراً)
            if current_id != sender_id and not whisper['read']:
                whisper['read'] = True
                try:
                    await context.bot.send_message(
                        chat_id=sender_id,
                        text=f"👁️ **تمت قراءة همستك!**\nقام {user.first_name} بفتح الهمسة الآن."
                    )
                except Exception:
                    pass

            if whisper['is_burn'] and current_id != sender_id:
                del whispers_db[whisper_id]

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
