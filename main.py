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
        self.wfile.write(b"Advanced Smart Whisper Bot is Alive!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

logging.basicConfig(level=logging.INFO)

TOKEN = "8983390041:AAFPEbUCr4WuXwj2yznl4qWZNQJ5EZouMlI"
whispers_db = {}
user_history = {}  # الذاكرة النشطة لحفظ آخر المنشنات لكل مستخدم

async def start_command(update, context):
    welcome_text = (
        "أهلاً بك في **بوت الهمسات الذكي**! 🤫✨\n\n"
        "--- 💡 **الترتيب الجديد وطريقة الاستخدام** ---\n\n"
        "1️⃣ **الترتيب:** اكتب يوزر البوت 👈 الرسالة 👈 المنشنات:\n"
        "`@vv_cbot هلا والله كيفك @user1 @user2`\n\n"
        "2️⃣ **المنشنات المتعددة:** يمكنك منشن شخص، شخصين، أو أكثر في نفس الهمسة!\n\n"
        "3️⃣ **الذاكرة النشطة:** اكتب `@vv_cbot ` فقط وسيقترح عليك البوت آخر منشنات همست لها سابقاً!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def inline_whisper(update, context):
    query = update.inline_query.query.strip()
    sender = update.inline_query.from_user
    sender_id = sender.id
    sender_name = sender.first_name
    sender_username = sender.username.lower() if sender.username else ""

    # 🧠 ميزة الذاكرة النشطة: إذا لم يكتب المستعلم منشنات بعد
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

    # 🎯 الترتيب الجديد: استخراج المنشنات والنص
    words = query.split()
    targets = [w.replace('@', '').lower() for w in words if w.startswith('@')]
    text_words = [w for w in words if not w.startswith('@')]
    whisper_text = " ".join(text_words).strip()

    if not targets or not whisper_text:
        return

    # حفظ في الذاكرة النشطة للمستخدم
    if sender_id not in user_history:
        user_history[sender_id] = []
    
    # تجنب التكرار المباشر للحفظ
    user_history[sender_id].insert(0, {'targets': targets, 'text': whisper_text})
    user_history[sender_id] = user_history[sender_id][:5]  # حفظ آخر 5 عمليات

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
        'opened': False
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

        # التحقق هل المستلم من ضمن القائمة المحددة أو هو المرسل نفسه
        is_target = current_username in targets
        is_sender = (current_id == sender_id or (sender_username and current_username == sender_username))

        if is_target or is_sender:
            sender_info = "شخص مجهول 🤫" if whisper['type'] == 'anon' else whisper['sender_name']
            msg = f"📩 من: {sender_info}\n\n💬 الهمسة: {whisper['text']}"
            
            await query.answer(msg, show_alert=True)

            # 🔓 التغيير التلقائي للإيموجي بعد فتح القراءة أول مرة
            if not whisper['opened']:
                whisper['opened'] = True
                new_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔓 تم فتح القراءة", callback_data=f"show_{whisper_id}")]])
                try:
                    await query.edit_message_reply_markup(reply_markup=new_kb)
                except Exception:
                    pass

                # إشعار قراءة للمرسل
                if not is_sender:
                    try:
                        await context.bot.send_message(
                            chat_id=sender_id,
                            text=f"👁️ **تمت قراءة همستك!**\nقام {user.first_name} (@{current_username}) بفتح الهمسة."
                        )
                    except Exception:
                        pass

            # تدمير الهمسة المتفجرة
            if whisper['type'] == 'burn' and not is_sender:
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
