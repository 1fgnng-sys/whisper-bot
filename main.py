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
        self.wfile.write(b"Whisper Bot with Quick Reply is Alive!")

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
        "أهلاً بك في **بوت الهمسات السرية المتكامل**! 🤫✨\n\n"
        "--- 💡 **طريقة الاستخدام السريعة** ---\n\n"
        "فقط اكتب في أي محادثة أو جروب:\n"
        "`@vv_cbot @username الرسالة`\n\n"
        "اختر نوع الهمسة من القائمة المقترحة، وعندما يقبلها المستلم ويقرأها، "
        "يمكنه الرد عليك فوراً بزر **الرد السري المباشر**! 🎯"
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

    id_normal = str(uuid.uuid4())[:8]
    id_anon = str(uuid.uuid4())[:8]
    id_burn = str(uuid.uuid4())[:8]
    id_public = str(uuid.uuid4())[:8]

    # حفظ بيانات الهمسة والمرسل ليتمكن المستلم من الرد السريع عليه
    base_data = {
        'target': clean_target, 
        'sender_id': sender_id, 
        'sender_name': sender_name, 
        'sender_username': sender_username, 
        'text': whisper_text, 
        'read': False
    }

    whispers_db[id_normal] = {**base_data, 'type': 'normal'}
    whispers_db[id_anon] = {**base_data, 'type': 'anon'}
    whispers_db[id_burn] = {**base_data, 'type': 'burn'}
    whispers_db[id_public] = {**base_data, 'type': 'public'}

    kb_normal = InlineKeyboardMarkup([[InlineKeyboardButton("🔒 اضغط لقراءة الهمسة", callback_data=f"show_{id_normal}")]])
    kb_anon = InlineKeyboardMarkup([[InlineKeyboardButton("🤫 همسة من مجهول", callback_data=f"show_{id_anon}")]])
    kb_burn = InlineKeyboardMarkup([[InlineKeyboardButton("💣 همسة متفجرة (مرة واحدة)", callback_data=f"show_{id_burn}")]])
    kb_public = InlineKeyboardMarkup([[InlineKeyboardButton("🌐 همسة عامة للجميع", callback_data=f"show_{id_public}")]])

    results = [
        InlineQueryResultArticle(
            id=id_normal,
            title=f"🔒 همسة عادية إلى {target_user}",
            description="يظهر اسمك للمستلم عند فتح الهمسة مع إمكانية الرد السريع",
            input_message_content=InputTextMessageContent(message_text=f"🔒 **همسة سرية موجهة إلى [{target_user}]**\nلا يمكن لأحد قراءتها غيره.", parse_mode="Markdown"),
            reply_markup=kb_normal
        ),
        InlineQueryResultArticle(
            id=id_anon,
            title=f"🤫 همسة مجهولة إلى {target_user}",
            description="لن يظهر اسمك للمستلم",
            input_message_content=InputTextMessageContent(message_text=f"🤫 **همسة مجهولة موجهة إلى [{target_user}]**\nلا يمكن لأحد قراءتها غيره.", parse_mode="Markdown"),
            reply_markup=kb_anon
        ),
        InlineQueryResultArticle(
            id=id_burn,
            title=f"💣 همسة متفجرة إلى {target_user}",
            description="تُقرأ لمرة واحدة فقط ثم تُحذف نهائياً",
            input_message_content=InputTextMessageContent(message_text=f"💣 **همسة متفجرة موجهة إلى [{target_user}]**\nتتأكل وتتدمر بعد القراءة مباشرة!", parse_mode="Markdown"),
            reply_markup=kb_burn
        ),
        InlineQueryResultArticle(
            id=id_public,
            title=f"🌐 همسة عامة إلى {target_user}",
            description="يمكن لأي شخص في المحادثة قراءتها",
            input_message_content=InputTextMessageContent(message_text=f"🌐 **همسة عامة موجهة إلى [{target_user}]**", parse_mode="Markdown"),
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
            await query.answer("❌ عذراً، هذه الهمسة تدمرت أو انتهت صلاحيتها.", show_alert=True)
            return

        user = query.from_user
        current_username = user.username.lower() if user.username else ""
        current_id = user.id

        target_name = whisper['target']
        sender_id = whisper['sender_id']
        sender_username = whisper['sender_username']

        can_read = (whisper['type'] == 'public' or 
                    current_username == target_name or 
                    current_id == sender_id or 
                    (sender_username and current_username == sender_username))

        if can_read:
            sender_info = "شخص مجهول 🤫" if whisper['type'] == 'anon' else whisper['sender_name']
            
            # نص التنبيه مع إضافة إرشادات للرد السريع إذا كان القارئ هو المستلم
            msg = f"📩 من: {sender_info}\n\n💬 الهمسة: {whisper['text']}"
            
            if current_id != sender_id and sender_username and whisper['type'] != 'anon':
                msg += f"\n\n💡 للرد السريع اكتب:\n`@vv_cbot @{sender_username} النص`"

            await query.answer(msg, show_alert=True)

            # إشعار قراءة للمرسل
            if current_id != sender_id and not whisper['read']:
                whisper['read'] = True
                try:
                    await context.bot.send_message(
                        chat_id=sender_id,
                        text=f"👁️ **تمت قراءة همستك!**\nقام {user.first_name} بفتح همستك الآن."
                    )
                except Exception:
                    pass

            if whisper['type'] == 'burn' and current_id != sender_id:
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
