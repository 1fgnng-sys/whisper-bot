import os
import logging
import uuid
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, InlineQueryHandler, CallbackQueryHandler

# ---------------------------------------------------------
# 1. السيرفر الوهمي للتوافق مع Render و UptimeRobot
# ---------------------------------------------------------
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
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

logging.basicConfig(level=logging.INFO)
TOKEN = "8983390041:AAFPEbUCr4WuXwj2yznl4qWZNQJ5EZouMlI"

# ---------------------------------------------------------
# 2. قاعدة البيانات المحسّنة (SQLite)
# ---------------------------------------------------------
DB_FILE = "whispers.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS whispers (
            id TEXT PRIMARY KEY,
            targets TEXT,
            sender_id INTEGER,
            sender_name TEXT,
            sender_username TEXT,
            text TEXT,
            type TEXT,
            opened INTEGER DEFAULT 0,
            opened_by_user TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocked_users (
            owner_id INTEGER,
            blocked_id INTEGER,
            PRIMARY KEY (owner_id, blocked_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_history (
            user_id INTEGER PRIMARY KEY,
            targets_history TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def save_whisper(whisper_id, targets, sender_id, sender_name, sender_username, text, whisper_type):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    targets_str = ",".join(targets)
    cursor.execute('''
        INSERT INTO whispers (id, targets, sender_id, sender_name, sender_username, text, type, opened, opened_by_user)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, '')
    ''', (whisper_id, targets_str, sender_id, sender_name, sender_username, text, whisper_type))
    conn.commit()
    conn.close()

def get_whisper(whisper_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT targets, sender_id, sender_name, sender_username, text, type, opened, opened_by_user FROM whispers WHERE id = ?', (whisper_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'targets': row[0].split(',') if row[0] else [],
            'sender_id': row[1],
            'sender_name': row[2],
            'sender_username': row[3],
            'text': row[4],
            'type': row[5],
            'opened': bool(row[6]),
            'opened_by_user': row[7]
        }
    return None

def mark_whisper_opened(whisper_id, opened_by_user=""):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE whispers SET opened = 1, opened_by_user = ? WHERE id = ?', (opened_by_user, whisper_id))
    conn.commit()
    conn.close()

def delete_whisper(whisper_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM whispers WHERE id = ?', (whisper_id,))
    conn.commit()
    conn.close()

# الحظر وإلغاء الحظر للحسابات
def block_user(owner_id, blocked_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO blocked_users (owner_id, blocked_id) VALUES (?, ?)', (owner_id, blocked_id))
    conn.commit()
    conn.close()

def unblock_user(owner_id, blocked_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM blocked_users WHERE owner_id = ? AND blocked_id = ?', (owner_id, blocked_id))
    conn.commit()
    conn.close()

def is_blocked(owner_id, user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM blocked_users WHERE owner_id = ? AND blocked_id = ?', (owner_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return bool(row)

# حفظ واسترجاع سجل اليوزرات
def save_user_history(user_id, targets):
    if not targets:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    targets_formatted = " ".join([f"@{t}" for t in targets])
    
    cursor.execute('SELECT targets_history FROM user_history WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    history = row[0].split(";") if row and row[0] else []
    
    if targets_formatted in history:
        history.remove(targets_formatted)
    history.insert(0, targets_formatted)
    history = history[:5]
    
    cursor.execute('REPLACE INTO user_history (user_id, targets_history) VALUES (?, ?)', (user_id, ";".join(history)))
    conn.commit()
    conn.close()

def get_user_history(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT targets_history FROM user_history WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return row[0].split(";")
    return []

# ---------------------------------------------------------
# 3. معالجة الأحداث والـ Inline Mode
# ---------------------------------------------------------
async def start_command(update, context):
    welcome_text = (
        "أهلاً بك 👋✨\n\n"
        "💡 **طريقة الاستخدام السريعة:**\n"
        "اكتب اسم البوت ثم الرسالة ثم المنشنات:\n\n"
        "`@vv_cbot اكتب همستك هنا @user`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def inline_whisper(update, context):
    query = update.inline_query.query.strip()
    sender = update.inline_query.from_user
    sender_id = sender.id
    sender_name = sender.first_name
    sender_username = sender.username.lower() if sender.username else ""

    # استدعاء السجل السريع عند فتح الـ Inline دون كتابة يوزرات
    if not query or not any(word.startswith('@') for word in query.split()):
        history = get_user_history(sender_id)
        if history:
            results = []
            for index, target_group in enumerate(history):
                results.append(
                    InlineQueryResultArticle(
                        id=f"hist_{index}",
                        title=f"👥 إرسال سريع لـ: {target_group}",
                        description="اضغط لتجهيز المنشنات تلقائياً في خانة الكتابة",
                        input_message_content=InputTextMessageContent(
                            message_text=f"💡 تجهيز همسة سريعة لـ {target_group}..."
                        ),
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("✏️ كتابة الهمسة الآن", switch_inline_query_current_chat=f"اكتب همستك هنا {target_group}")
                        ]])
                    )
                )
            await update.inline_query.answer(results, cache_time=1)
            return

    # التفكيك الذكي للرسالة والمنشنات
    words = query.split()
    targets = [w.replace('@', '').lower() for w in words if w.startswith('@')]
    text_words = [w for w in words if not w.startswith('@')]
    whisper_text = " ".join(text_words).strip()

    if not whisper_text:
        return

    # حفظ اليوزرات في السجل
    if targets:
        save_user_history(sender_id, targets)

    targets_display = " ".join([f"@{t}" for t in targets]) if targets else "للجميع (أول من يفتحها)"
    id_normal = str(uuid.uuid4())[:12]
    id_burn = str(uuid.uuid4())[:12]
    id_public = str(uuid.uuid4())[:12]

    results = []

    if targets:
        # همسة خاصة بشرط منشن
        save_whisper(id_normal, targets, sender_id, sender_name, sender_username, whisper_text, 'normal')
        save_whisper(id_burn, targets, sender_id, sender_name, sender_username, whisper_text, 'burn')

        kb_normal = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔒 اضغط لقراءة الهمسة", callback_data=f"show_{id_normal}")],
            [InlineKeyboardButton("👁️ معاينة نص همستك", callback_data=f"prev_{id_normal}")]
        ])
        kb_burn = InlineKeyboardMarkup([
            [InlineKeyboardButton("💣 همسة متفجرة (مرة واحدة)", callback_data=f"show_{id_burn}")],
            [InlineKeyboardButton("👁️ معاينة نص همستك", callback_data=f"prev_{id_burn}")]
        ])

        results.extend([
            InlineQueryResultArticle(
                id=id_normal,
                title=f"🔒 همسة عادية إلى {targets_display}",
                description=f"الرسالة: {whisper_text}",
                input_message_content=InputTextMessageContent(message_text=f"🔒 **همسة سرية موجهة إلى [{targets_display}]**\nلا يمكن لأحد قراءتها غيرهم.", parse_mode="Markdown"),
                reply_markup=kb_normal
            ),
            InlineQueryResultArticle(
                id=id_burn,
                title=f"💣 همسة متفجرة إلى {targets_display}",
                description="تتدمر فور قراءتها من المستلم",
                input_message_content=InputTextMessageContent(message_text=f"💣 **همسة متفجرة موجهة إلى [{targets_display}]**", parse_mode="Markdown"),
                reply_markup=kb_burn
            )
        ])
    else:
        # خيار "الهمسة العامة": تتاح لأول شخص يفتحها
        save_whisper(id_public, [], sender_id, sender_name, sender_username, whisper_text, 'public')
        kb_public = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔓 همسة عامة (تُغلق بعد أول قراءة)", callback_data=f"show_{id_public}")],
            [InlineKeyboardButton("👁️ معاينة نص همستك", callback_data=f"prev_{id_public}")]
        ])

        results.append(
            InlineQueryResultArticle(
                id=id_public,
                title="🌐 همسة عامة (لأول شخص يضغطها)",
                description=f"الرسالة: {whisper_text}",
                input_message_content=InputTextMessageContent(message_text="🌐 **همسة عامة مفتوحة لأول شخص يقرأها!**", parse_mode="Markdown"),
                reply_markup=kb_public
            )
        )

    await update.inline_query.answer(results, cache_time=1)

async def handle_click(update, context):
    query = update.callback_query
    data = query.data
    user = query.from_user
    current_username = user.username.lower() if user.username else ""
    current_id = user.id

    # معاينة النص للمرسل فقط
    if data.startswith("prev_"):
        whisper_id = data.split("prev_")[1]
        whisper = get_whisper(whisper_id)
        if whisper:
            sender_id = whisper['sender_id']
            sender_username = whisper['sender_username']
            if current_id == sender_id or (sender_username and current_username == sender_username):
                await query.answer(f"🔍 معاينة همستك:\n\n{whisper['text']}", show_alert=True)
            else:
                await query.answer("🚫 هذه المعاينة مخصصة لمرسل الهمسة فقط!", show_alert=True)
        else:
            await query.answer("❌ الهمسة غير موجودة.", show_alert=True)
        return

    # إدارة الحظر وإلغاء الحظر
    if data.startswith("block_"):
        target_id = int(data.split("block_")[1])
        block_user(current_id, target_id)
        unblock_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔓 إلغاء حظر هذا المستخدم", callback_data=f"unblock_{target_id}")]])
        await query.answer("✅ تم حظر هذا المستخدم من التفاعل مع همساتك!", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=unblock_kb)
        except Exception:
            pass
        return

    if data.startswith("unblock_"):
        target_id = int(data.split("unblock_")[1])
        unblock_user(current_id, target_id)
        await query.answer("✅ تم إلغاء الحظر بنجاح! يمكنه الآن فتح همساتك القادمة.", show_alert=True)
        return

    # قراءة الهمسة
    if data.startswith("show_"):
        whisper_id = data.split("show_")[1]
        whisper = get_whisper(whisper_id)

        if not whisper:
            await query.answer("❌ عذراً، هذه الهمسة تدمرت أو غير موجودة.", show_alert=True)
            return

        sender_id = whisper['sender_id']
        sender_username = whisper['sender_username']
        targets = whisper['targets']
        whisper_type = whisper['type']

        # التأكد من عدم وجود حظر على المستخدم
        if is_blocked(sender_id, current_id):
            await query.answer("🚫 قام صاحب الهمسة بحظرك من فتح همساته!", show_alert=True)
            return

        is_sender = (current_id == sender_id or (sender_username and current_username == sender_username))
        
        # معالجة "الهمسة العامة" (First Come, First Served)
        if whisper_type == 'public':
            if whisper['opened'] and not is_sender:
                await query.answer(f"🔒 تم قراءة هذه الهمسة العامة وسحبها بواسطة {whisper['opened_by_user']}!", show_alert=True)
                return

            msg = f"📩 من: {whisper['sender_name']}\n\n💬 الهمسة: {whisper['text']}"
            await query.answer(msg, show_alert=True)

            if not whisper['opened'] and not is_sender:
                user_tag = f"@{current_username}" if current_username else user.first_name
                mark_whisper_opened(whisper_id, user_tag)
                new_kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"🔒 تم الفتح بواسطة {user_tag}", callback_data=f"show_{whisper_id}")]])
                try:
                    await query.edit_message_reply_markup(reply_markup=new_kb)
                except Exception:
                    pass
            return

        # معالجة الهمسة المخصصة بمستهدفين
        is_target = current_username in targets

        if is_target or is_sender:
            msg = f"📩 من: {whisper['sender_name']}\n\n💬 الهمسة: {whisper['text']}"
            await query.answer(msg, show_alert=True)

            if is_target and not whisper['opened']:
                mark_whisper_opened(whisper_id)
                new_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔓 تم فتح القراءة", callback_data=f"show_{whisper_id}")]])
                try:
                    await query.edit_message_reply_markup(reply_markup=new_kb)
                except Exception:
                    pass

                # إشعار قراءة للمرسل
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

            if whisper_type == 'burn' and is_target:
                delete_whisper(whisper_id)

        else:
            # تنبيه المتسلل مع زر حظر الحساب الفوري
            await query.answer("🚫 هذه الهمسة ليست موجهة لك!", show_alert=True)
            try:
                user_tag = f"@{current_username}" if current_username else "بدون يوزر"
                block_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚫 حظر هذا المستخدم من همساتي", callback_data=f"block_{current_id}")]])
                await context.bot.send_message(
                    chat_id=sender_id,
                    text=(
                        f"🚨 **تنبيه أمني: محاولة تجسس!**\n\n"
                        f"👤 حاول {user.first_name} ({user_tag}) فتح همستك السرية الموجهة لـ:\n"
                        f"📌 {' '.join(['@'+t for t in targets])}\n"
                        f"🔒 وتم منعه بنجاح!"
                    ),
                    reply_markup=block_kb,
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
