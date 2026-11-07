import os
import sqlite3
import threading
from flask import Flask
import telebot
from telebot import types

# ---------------- SOZLAMALAR ----------------
BOT_TOKEN = "8689759439:AAEIvwdr8pdnBsDqqUsOEXuR_D2-SlWGOKA"
CHANNEL_USERNAME = "@Growth_Jamiyati"  # Kanal username'i yangilandi

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------- FLASK SERVER (Render uxlamasligi uchun) ----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot ishlayapti va faol!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ---------------- MA'LUMOTLAR BAZASI (SQLITE) ----------------
def init_db():
    conn = sqlite3.connect("referral_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            referrer_id INTEGER,
            points INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect("referral_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, full_name, points FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def register_user(user_id, full_name, referrer_id=None):
    conn = sqlite3.connect("referral_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    existing_user = cursor.fetchone()
    
    if existing_user is None:
        cursor.execute("INSERT INTO users (user_id, full_name, referrer_id, points) VALUES (?, ?, ?, 0)",
                       (user_id, full_name, referrer_id))
        conn.commit()
        
        if referrer_id and referrer_id != user_id:
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (referrer_id,))
            if cursor.fetchone() is not None:
                cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (referrer_id,))
                conn.commit()
                
                try:
                    bot.send_message(
                        referrer_id, 
                        f"🎉 Tabriklaymiz! Sizning havolangiz orqali **{full_name}** botga kirdi va obuna bo'ldi. Sizga +1 ball qo'shildi! 🚀",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
    conn.close()

def get_top_users(limit=3):
    conn = sqlite3.connect("referral_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, points FROM users ORDER BY points DESC LIMIT ?", (limit,))
    top_users = cursor.fetchall()
    conn.close()
    return top_users

# ---------------- TEKSHIRISH FUNKSIYASI ----------------
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
    except Exception:
        pass
    return False

# ---------------- TUGMALAR ----------------
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🔗 Taklif havolam")
    btn2 = types.KeyboardButton("📊 Balim va Reyting")
    btn3 = types.KeyboardButton("🏆 Shartlar va Sovrinlar")
    markup.add(btn1, btn2)
    markup.add(btn3)
    return markup

def sub_keyboard():
    markup = types.InlineKeyboardMarkup()
    btn_channel = types.InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")
    btn_check = types.InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub")
    markup.add(btn_channel)
    markup.add(btn_check)
    return markup

# ---------------- BOT BUYRUQLARI VA XABARLARI ----------------
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    full_name = message.from_user.first_name
    
    if not check_subscription(user_id):
        text = (
            f"Salom, {full_name}! 👋\n\n"
            f"Botdan foydalanish va konkursda qatnashish uchun avval bizning kanalimizga obuna bo'lishingiz kerak:\n\n"
            f"📢 Kanal: {CHANNEL_USERNAME}\n\n"
            f"Obuna bo'lgach, '✅ Obunani tekshirish' tugmasini bosing:"
        )
        bot.send_message(user_id, text, reply_markup=sub_keyboard())
        return

    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])

    register_user(user_id, full_name, referrer_id)

    welcome_text = (
        f"Xush kelibsiz, {full_name}! 🎉\n"
        f"Siz muvaffaqiyatli obuna bo'ldingiz. Endi do'stlaringizni taklif qilib ballar to'plang!"
    )
    bot.send_message(user_id, welcome_text, reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check_sub(call):
    user_id = call.from_user.id
    full_name = call.from_user.first_name
    
    if check_subscription(user_id):
        bot.answer_callback_query(call.id, "Rahmat, obuna tasdiqlandi! ✅")
        register_user(user_id, full_name)
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(
            user_id, 
            "Tabriklaymiz! Botning barcha imkoniyatlari ochildi: 👇", 
            reply_markup=main_menu()
        )
    else:
        bot.answer_callback_query(call.id, "Siz hali kanalga obuna bo'lmadingiz! ❌", show_alert=True)

@bot.message_handler(func=lambda msg: msg.text == "🔗 Taklif havolam")
def send_ref_link(message):
    user_id = message.from_user.id
    if not check_subscription(user_id):
        bot.send_message(user_id, f"Iltimos, avval {CHANNEL_USERNAME} kanaliga obuna bo'ling!", reply_markup=sub_keyboard())
        return
        
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    msg_text = (
        f"Sizning shaxsiy taklif havolangiz:\n\n"
        f"`{ref_link}`\n\n"
        f"Ushbu havolani do'stlaringizga yuboring. Har bir yangi do'stingiz kanalga obuna bo'lib botga kirsa, sizga **1 ball** qo'shiladi!"
    )
    bot.send_message(user_id, msg_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📊 Balim va Reyting")
def show_stats(message):
    user_id = message.from_user.id
    if not check_subscription(user_id):
        bot.send_message(user_id, f"Iltimos, avval {CHANNEL_USERNAME} kanaliga obuna bo'ling!", reply_markup=sub_keyboard())
        return
        
    user = get_user(user_id)
    user_points = user[2] if user else 0
    top_3 = get_top_users(3)
    
    text = f"👤 **Sizning ballaringiz:** {user_points} ball\n\n"
    text += "🏆 **Ayni vaqtdagi TOP 3 ishtirokchilar:**\n"
    
    medals = ["🥇", "🥈", "🥉"]
    if top_3:
        for i, (name, pts) in enumerate(top_3):
            medal = medals[i] if i < 3 else "🔹"
            text += f"{medal} **{i+1}-o'rin:** {name} — {pts} ball\n"
    else:
        text += "Hozircha reyting bo'sh."

    bot.send_message(user_id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🏆 Shartlar va Sovrinlar")
def show_rules(message):
    rules = (
        "🎁 **Konkurs shartlari va sovrinlar:**\n\n"
        "🥇 **1-o'rin:** Sovrin nomi (masalan, Smartfon)\n"
        "🥈 **2-o'rin:** Sovrin nomi (masalan, Naushnik)\n"
        "🥉 **3-o'rin:** Sovrin nomi (masalan, Pul mukofoti)\n\n"
        "📌 **Qoidalar:** O'zingizni o'zingiz taklif qila olmaysiz. "
        "Kanalimizga obuna bo'lgan holda eng ko'p do'stlarini taklif qilgan 3 nafar qatnashchi g'olib deb topiladi!"
    )
    bot.send_message(message.chat.id, rules, parse_mode="Markdown")

# ---------------- Dasturni ishga tushirish ----------------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    bot.infinity_polling(skip_pending=True)