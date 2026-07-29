import os
import logging
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, InlineQueryHandler, CallbackQueryHandler

# سيرفر وهمي يستجيب لكافة طلبات HTTP (GET و HEAD) بكود 200 OK متوافق 100% مع UptimeRobot و Render
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("OK - Whisper Bot is Alive!".encode("utf-8"))

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_dummy_server():
    # استخدام البورت المخصص من Render تلقائياً
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

logging.basicConfig(level=logging.INFO)

TOKEN = "8983390041:AAFPEbUCr4WuXwj2yznl4qWZNQJ5EZouMlI"
whispers_db = {}
user_history = {}

async def start_command(update, context):
    welcome_text = (
        "أهلاً بك في **بوت الهمسات الذكي والأمني**! 🤫✨\n\n"
        "--- 💡 **الترتيب وطريقة الاستخدام** ---\n\n"
        "1️⃣ **الترتيب:** اكتب يوزر البوت 👈 الرسالة 👈 المنشنات:\n"
        "`@vv_cbot هلا والله كيفكم @user1 @user2`\n\n"
        "2️⃣ **نظام الإشعارات والأمان:**\n"
        "• تصلك إشعارات فورية بكل شخص يفتح الهمسة من المحددين.\n"
        "• يصلك إشعار أمني بأي 'متسلل' يحاول فتح همستك وهويته! 🚨"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def inline_whisper(update, context):
    query = update.inline_query.query.strip()
    sender = update.inline_query.from_user
    sender_id = sender.id
    sender_name = sender.first_name
    sender_username = sender.username.lower() if sender.username else ""

    # الذاكرة النشطة: اقتراح آخر العمليات
    if not query or not any(word.startswith('@') for word in query.split()):
        history = user_history.get(sender_id, [])
        if not history:
            return
        
        results = []
        for index, item in enumerate(history):
            targets_str = " ".join([f"@{t}" for t in item['targets']])
            results.append(
                InlineQueryResultArticle(
                    id=f"history_{index}",
                    title=f"🕒 إعادة همسة لـ: {targets_str}",
                    description=f"آخر همسة: {item['text'][:30]}...",
                    input_message_content=InputTextMessageContent(
                        message_text=f"💡 اخترت إعادة التفاعل مع: {targets_str}\nيرجى كتابة الرسالة والمنشن."
                    )
                )
            )
        await update.inline_query.answer(results, cache_time=1)
        return

    words = query.split()
    targets = [w.replace('@', '').lower() for w in words if w.startswith('@')]
    text_words = [w for w in words if not w.startswith('@')]
    whisper_text = " ".join(text_words).strip()

    if not targets or not whisper_text:
        return

    if sender_id not in user_history:
        user_history[sender_id] = []
    
    user_history[sender_id].insert(0, {'targets': targets, 'text': whisper_text})
    user_history[sender_id] = user_history[sender_id][:5]

    targets_display = " ".join([f"@{t}" for t in targets])
    id_normal = str(uuid.uuid4())[:8]
    id_anon = str(uuid.uuid4())[:8]
    id_burn = str(uuid.uuid4())[:8]

    base_data = {
        'targets': targets, 
        'sender_id': sender_id, 
        'sender_name': sender_name, 
        'sender_username': sender_username, 
        'text': whisper_text, 
        'opened': False,
        'opened_by': [],
        'intruders': []
    }

    whispers_db[id_normal] = {**base_data, 'type': 'normal'}
    whispers_db[id_anon] = {**base_data, 'type': 'anon'}
    whispers_db[id_burn] = {**base_data, 'type': 'burn'}

    kb_normal = InlineKeyboardMarkup([[InlineKeyboardButton("🔒 اضغط لقراءة الهمسة", callback_data=f"show_{id_normal}")]])
    kb_anon = InlineKeyboardMarkup([[InlineKeyboardButton("🤫 همسة من مجهول", callback_data=f"show_{id_anon}")]])
    kb_burn = InlineKeyboardMarkup([[InlineKeyboardButton("💣 همسة متفجرة (مرة واحدة)", callback_data=f"show_{id_burn}")]])

    results = [
        InlineQueryResultArticle(
            id=id_normal,
            title=f"🔒 همسة عادية إلى {targets_display}",
            description=f"الرسالة: {whisper_text}",
            input_message_content=InputTextMessageContent(message_text=f"🔒 **همسة سرية موجهة إلى [{targets_display}]**\nلا يمكن لأحد قراءتها غيرهم.", parse_mode="Markdown"),
            reply_markup=kb_normal
        ),
        InlineQueryResultArticle(
            id=id_anon,
            title=f"🤫 همسة مجهولة إلى {targets_display}",
            description="بدون إظهار اسمك",
            input_message_content=InputTextMessageContent(message_text=f"🤫 **همسة مجهولة موجهة إلى [{targets_display}]**\nلا يمكن لأحد قراءتها غيرهم.", parse_mode="Markdown"),
            reply_markup=kb_anon
        ),
        InlineQueryResultArticle(
            id=id_burn,
            title=f"💣 همسة متفجرة إلى {targets_display}",
            description="تتدمر بعد أول قراءة",
            input_message_content=InputTextMessageContent(message_text=f"💣 **همسة متفجرة موجهة إلى [{targets_display}]**", parse_mode="Markdown"),
            reply_markup=kb_burn
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

        sender_id = whisper['sender_id']
        sender_username = whisper['sender_username']
        targets = whisper['targets']

        is_target = current_username in targets
        is_sender = (current_id == sender_id or (sender_username and current_username == sender_username))

        if is_target or is_sender:
            sender_info = "شخص مجهول 🤫" if whisper['type'] == 'anon' else whisper['sender_name']
            msg = f"📩 من: {sender_info}\n\n💬 الهمسة: {whisper['text']}"
            
            await query.answer(msg, show_alert=True)

            # تغير أيقونة القفل بعد الفتح
            if not whisper['opened']:
                whisper['opened'] = True
                new_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔓 تم فتح القراءة", callback_data=f"show_{whisper_id}")]])
                try:
                    await query.edit_message_reply_markup(reply_markup=new_kb)
                except Exception:
                    pass

            # إرسال إشعار قراءة للمرسل
            if not is_sender and current_id not in whisper['opened_by']:
                whisper['opened_by'].append(current_id)
                try:
                    user_tag = f"@{current_username}" if current_username else user.first_name
                    await context.bot.send_message(
                        chat_id=sender_id,
                        text=(
                            f"👁️ **إشعار قراءة همسة!**\n\n"
                            f"👤 قام {user.first_name} ({user_tag}) بفتح وقراءة همستك الموجهة لـ:\n"
                            f"📌 {' '.join(['@'+t for t in targets])}"
                        ),
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

            if whisper['type'] == 'burn' and not is_sender:
                del whispers_db[whisper_id]

        else:
            # حالة المتسلل
            await query.answer("🚫 هذه الهمسة ليست موجهة لك!", show_alert=True)

            if current_id not in whisper['intruders']:
                whisper['intruders'].append(current_id)
                try:
                    user_tag = f"@{current_username}" if current_username else "بدون يوزر"
                    await context.bot.send_message(
                        chat_id=sender_id,
                        text=(
                            f"🚨 **تنبيه أمني: محاولة فضول/تجسس!**\n\n"
                            f"👤 حاول {user.first_name} ({user_tag}) فتح همستك السرية الموجهة لـ:\n"
                            f"📌 {' '.join(['@'+t for t in targets])}\n"
                            f"🔒 وتم منعه بنجاح!"
                        ),
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(InlineQueryHandler(inline_whisper))
    app.add_handler(CallbackQueryHandler(handle_click))
    app.run_polling()

if __name__ == "__main__":
    main()
