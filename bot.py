import time
import sqlite3
import random
import logging
from datetime import datetime, timedelta
import pyotp
import requests
import telebot
from telebot import types

# ==============================
# CONFIGURATION
# ==============================
BOT_TOKEN = "8581363568:AAEJp3qm5bhzLywHAeauM-zKR6K4G4_wk9U"
ADMIN_ID = 7942994648
DB_NAME = "taskbot.db"

# জিমেইলের স্থায়ী পাসওয়ার্ড (সারাবছর একই থাকবে)
GMAIL_PASSWORD = "Jihad@441" 

# ফেসবুক ও ইনস্টাগ্রামের পাসওয়ার্ড প্রিফিক্স
FB_IG_PREFIX = "Jihad" 

def get_fb_ig_password():
    """Facebook ও Instagram-এর জন্য রাত ৯:০০ টায় তারিখ পরিবর্তন করে পাসওয়ার্ড তৈরি করবে"""
    bd_time = datetime.utcnow() + timedelta(hours=6) # বাংলাদেশ সময় (UTC+6)
    
    # রাত ৯টা (২১:০০) বাজলে পরবর্তী দিনের তারিখ কাউন্ট করবে
    if bd_time.hour >= 21:
        target_date = bd_time + timedelta(days=1)
    else:
        target_date = bd_time
        
    date_str = target_date.strftime("%d") # শুধুমাত্র দিনের সংখ্যা (যেমন: 19)
    return f"{FB_IG_PREFIX}@{date_str}"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
logging.basicConfig(level=logging.INFO)

user_states = {}

# ==============================
# DATA BANK
# ==============================
IG_FIRST_NAMES = ["john", "michael", "david", "james", "robert", "william", "joseph", "thomas", "charles", "daniel", "tanvir", "sakib", "rahim"]
IG_LAST_NAMES = ["smith", "brown", "wilson", "taylor", "johnson", "davis", "miller", "khan", "rahman", "hasan"]

def generate_human_ig_username():
    first = random.choice(IG_FIRST_NAMES)
    last = random.choice(IG_LAST_NAMES)
    num = random.randint(100, 9999)
    return f"{first}{last}{num}"

FB_FIRST_NAMES = ["Md", "Md", "Md", "Tanvir", "Shakil", "Rakib", "Arif", "Faisal", "Kamrul", "Shahin", "Naim", "Alamin"]
FB_LAST_NAMES = ["Khan", "Khan", "Khan", "Rahman", "Hasan", "Ahmed", "Hossain", "Islam", "Chowdhury", "Sheikh", "Uddin", "Ali"]

GMAIL_FIRST_NAMES = ["John", "Michael", "David", "James", "Robert", "William", "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark"]
GMAIL_LAST_NAME = "X"

# ==============================
# HELPER FUNCTIONS & VALIDATIONS
# ==============================
def check_gmail_exists(email):
    """গুগল সার্ভারে সত্যিকারে জিমেইল তৈরি হয়েছে কিনা তা ভেরিফাই করবে"""
    try:
        url = "https://mail.google.com/mail/cx/user/x?client=navclient-auto"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, params={"user": email}, headers=headers, timeout=6)
        if res.status_code == 200 and "true" in res.text.lower():
            return True
        return False
    except Exception:
        return False

def is_valid_fb_uid(uid_str):
    uid_str = uid_str.strip()
    return uid_str.isdigit() and len(uid_str) >= 6

def is_valid_fb_cookie(cookie_str):
    cookie_str = cookie_str.strip()
    if "c_user" in cookie_str or "xs=" in cookie_str or ("name" in cookie_str and "value" in cookie_str):
        return True
    return False

def send_main_menu(chat_id, first_name):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📋 Tasks", callback_data="menu_tasks"),
        types.InlineKeyboardButton("💰 Balance", callback_data="menu_balance")
    )
    keyboard.add(
        types.InlineKeyboardButton("💸 Withdraw", callback_data="menu_withdraw"),
        types.InlineKeyboardButton("👥 Referral", callback_data="menu_referral")
    )
    keyboard.add(
        types.InlineKeyboardButton("📖 Guide", callback_data="menu_guide"),
        types.InlineKeyboardButton("🎫 Support", callback_data="menu_support")
    )

    bot.send_message(
        chat_id,
        f"<b>🤖 PREMIUM TASK & WORK BOT</b>\n\nস্বাগতম <b>{first_name}</b>!\nনিচের মেনু থেকে আপনার কাঙ্ক্ষিত অপশন বেছে নিন।",
        reply_markup=keyboard
    )

def delete_credentials_msg(chat_id, user_id):
    if user_id in user_states and "cred_msg_id" in user_states[user_id]:
        try:
            bot.delete_message(chat_id, user_states[user_id]["cred_msg_id"])
        except Exception:
            pass

# ==============================
# DATABASE SETUP
# ==============================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            referred_by INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_type TEXT,
            proof_data TEXT,
            reward REAL,
            status TEXT DEFAULT 'pending'
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            net_amount REAL,
            address TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def register_user(user_id, username, ref_id=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not cur.fetchone():
        referred_by = ref_id if ref_id and ref_id != user_id else None
        cur.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
                    (user_id, username or "", referred_by))
        conn.commit()
    conn.close()

# ==============================
# START COMMAND
# ==============================
@bot.message_handler(commands=["start"])
def start_cmd(message):
    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    
    register_user(message.from_user.id, message.from_user.username, ref_id)
    send_main_menu(message.chat.id, message.from_user.first_name)

# ==============================
# CALLBACK HANDLERS
# ==============================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "menu_balance":
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        bal_row = cur.fetchone()
        balance = bal_row[0] if bal_row else 0.0

        cur.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='pending'", (user_id,))
        pending_tasks = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='approved'", (user_id,))
        success_tasks = cur.fetchone()[0]
        conn.close()

        msg = f"""
💳 <b>আপনার অ্যাকাউন্ট প্রোফাইল</b>

💵 <b>বর্তমান ব্যালেন্স:</b> {balance:.2f} BDT
⏳ <b>রিভিউতে থাকা টাস্ক:</b> {pending_tasks} টি
✅ <b>সাকসেস হওয়া টাস্ক:</b> {success_tasks} টি
"""
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, msg)

    elif call.data == "menu_tasks":
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("📸 Instagram Task", callback_data="sub_ig_menu"),
            types.InlineKeyboardButton("📘 Facebook Task", callback_data="sub_fb_menu"),
            types.InlineKeyboardButton("📧 Gmail Task", callback_data="sub_gmail_menu")
        )
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "👇 <b>যেকোনো একটি টাস্ক ক্যাটাগরি নির্বাচন করুন:</b>", reply_markup=keyboard)

    elif call.data == "menu_withdraw":
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("📱 নগদ (Nagad)", callback_data="w_method_invalid"),
            types.InlineKeyboardButton("📱 বিকাশ (Bkash)", callback_data="w_method_invalid"),
            types.InlineKeyboardButton("🪙 USDT (BEP20)", callback_data="w_method_bep20"),
            types.InlineKeyboardButton("❌ বাতিল", callback_data="cancel_task")
        )
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "💸 <b>উইথড্র করার পেমেন্ট মেথড সিলেক্ট করুন:</b>", reply_markup=keyboard)

    elif call.data == "w_method_invalid":
        bot.answer_callback_query(call.id, "❌ এটি এখনো প্রযোজ্য নয়!", show_alert=True)

    elif call.data == "w_method_bep20":
        user_states[user_id] = {"step": "withdraw_amount"}
        msg = "💸 <b>WITHDRAWAL (USDT BEP20)</b>\n\n📌 মিনিমাম উইথড্র: ৩০ টাকা\n⛽ ফি: ৫ টাকা\n\nকত টাকা উইথড্র করতে চান তা সংখ্যায় লিখুন:"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, msg)

    elif call.data == "sub_ig_menu":
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("📸 Instagram (৪.১০ টাকা)", callback_data="start_ig_task"),
            types.InlineKeyboardButton("❌ বাতিল", callback_data="cancel_task")
        )
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "👇 <b>ইনস্টাগ্রাম টাস্কটি শুরু করতে নিচে ক্লিক করুন:</b>", reply_markup=keyboard)

    elif call.data == "sub_fb_menu":
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("📘 Facebook (৫.৫০ টাকা)", callback_data="start_fb_task"),
            types.InlineKeyboardButton("❌ বাতিল", callback_data="cancel_task")
        )
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "👇 <b>ফেসবুক টাস্কটি শুরু করতে নিচে ক্লিক করুন:</b>", reply_markup=keyboard)

    elif call.data == "sub_gmail_menu":
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("📧 Gmail (১৮.০০ টাকা)", callback_data="start_gmail_task"),
            types.InlineKeyboardButton("❌ বাতিল", callback_data="cancel_task")
        )
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "👇 <b>জিমেইল টাস্কটি শুরু করতে নিচে ক্লিক করুন:</b>", reply_markup=keyboard)

    elif call.data == "start_ig_task":
        username = generate_human_ig_username()
        password = get_fb_ig_password()

        msg = f"""
📸 <b>INSTAGRAM ACCOUNT TASK</b> (রিওয়ার্ড: ৪.১০ টাকা)

👤 <b>Username:</b> <code>{username}</code>
🔑 <b>Password:</b> <code>{password}</code>

⚠️ উপরে দেওয়া তথ্য দিয়ে অ্যাকাউন্ট তৈরি করুন।
"""
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("🔑 ২এফএ কী সেট করুন", callback_data="ig_click_2fa_btn"),
            types.InlineKeyboardButton("❌ বাতিল", callback_data="cancel_task")
        )
        bot.answer_callback_query(call.id)
        sent_msg = bot.send_message(chat_id, msg, reply_markup=keyboard)
        
        user_states[user_id] = {
            "step": "ig_wait_2fa_key",
            "username": username,
            "reward": 4.10,
            "cred_msg_id": sent_msg.message_id
        }

    elif call.data == "ig_click_2fa_btn":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "📥 আপনার <b>2FA Secret Key</b> টি মেসেজ বক্সে পাঠান:")

    elif call.data == "ig_finish":
        if user_id not in user_states or "secret" not in user_states[user_id]:
            bot.answer_callback_query(call.id, "❌ কোনো ২এফএ ডাটা পাওয়া যায়নি!", show_alert=True)
            return

        u_data = user_states[user_id]
        proof = f"IG: {u_data['username']} | Secret: {u_data['secret']}"

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("INSERT INTO tasks (user_id, task_type, proof_data, reward) VALUES (?, 'instagram', ?, ?)",
                    (user_id, proof, u_data['reward']))
        conn.commit()
        conn.close()

        delete_credentials_msg(chat_id, user_id)
        
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "🎉 <b>আপনার ইনস্টাগ্রাম টাস্কটি সফলভাবে জমা নেওয়া হয়েছে!</b>")
        if user_id in user_states:
            del user_states[user_id]

    elif call.data == "start_fb_task":
        f_name = random.choice(FB_FIRST_NAMES)
        l_name = random.choice(FB_LAST_NAMES)
        password = get_fb_ig_password()

        msg = f"""
📘 <b>FACEBOOK ACCOUNT TASK</b> (রিওয়ার্ড: ৫.৫০ টাকা)

👤 <b>First Name:</b> <code>{f_name}</code>
👤 <b>Last Name:</b> <code>{l_name}</code>
🔑 <b>Password:</b> <code>{password}</code>

⚠️ উপরে দেওয়া তথ্য দিয়ে ফেসবুক অ্যাকাউন্ট তৈরি করুন।
"""
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("🆔 ইউআইডি সেন্ড করুন", callback_data="fb_click_uid_btn"),
            types.InlineKeyboardButton("❌ বাতিল", callback_data="cancel_task")
        )
        bot.answer_callback_query(call.id)
        sent_msg = bot.send_message(chat_id, msg, reply_markup=keyboard)

        user_states[user_id] = {
            "step": "fb_wait_uid",
            "f_name": f_name,
            "l_name": l_name,
            "reward": 5.50,
            "cred_msg_id": sent_msg.message_id
        }

    elif call.data == "fb_click_uid_btn":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "📥 আপনার Facebook <b>UID</b> টি মেসেজ করে পাঠান:")

    elif call.data == "fb_click_cookie_btn":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "📥 এবার অ্যাকাউন্টটির <b>Cookie</b> টি পেস্ট করে পাঠান:")

    elif call.data == "fb_finish":
        if user_id not in user_states or "cookie" not in user_states[user_id]:
            bot.answer_callback_query(call.id, "❌ কোনো তথ্য পাওয়া যায়নি!", show_alert=True)
            return

        u_data = user_states[user_id]
        proof = f"FB Name: {u_data['f_name']} {u_data['l_name']} | UID: {u_data.get('uid')} | Cookie: {u_data['cookie']}"

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("INSERT INTO tasks (user_id, task_type, proof_data, reward) VALUES (?, 'facebook', ?, ?)",
                    (user_id, proof, u_data['reward']))
        conn.commit()
        conn.close()

        delete_credentials_msg(chat_id, user_id)

        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "🎉 <b>ফেসবুক টাস্কটি সফলভাবে জমা নেওয়া হয়েছে!</b>")
        if user_id in user_states:
            del user_states[user_id]

    elif call.data == "start_gmail_task":
        first_name = random.choice(GMAIL_FIRST_NAMES)
        last_name = GMAIL_LAST_NAME
        random_num = random.randint(100, 9999)
        email = f"{first_name.lower()}smith{random_num}@gmail.com"
        password = GMAIL_PASSWORD

        msg = f"""
📧 <b>GMAIL ACCOUNT TASK</b> (রিওয়ার্ড: ১৮.০০ টাকা)

👤 <b>First Name:</b> <code>{first_name}</code>
👤 <b>Last Name:</b> <code>{last_name}</code>
📧 <b>Email:</b> <code>{email}</code>
🔑 <b>Password:</b> <code>{password}</code>

⚠️ অ্যাকাউন্টটি সঠিকভাবে তৈরি শেষ হলে নিচের অপশনে ক্লিক করুন।
"""
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("✅ অ্যাকাউন্ট খোলা শেষ", callback_data="gmail_finish_check"),
            types.InlineKeyboardButton("❌ বাতিল", callback_data="cancel_task")
        )
        bot.answer_callback_query(call.id)
        sent_msg = bot.send_message(chat_id, msg, reply_markup=keyboard)

        user_states[user_id] = {
            "email": email,
            "reward": 18.00,
            "cred_msg_id": sent_msg.message_id
        }

    elif call.data == "gmail_finish_check":
        if user_id not in user_states or "email" not in user_states[user_id]:
            bot.answer_callback_query(call.id, "❌ টাস্কের ডাটা পাওয়া যায়নি!", show_alert=True)
            return

        email = user_states[user_id]["email"]
        bot.answer_callback_query(call.id, "🔍 জিমেইল অ্যাকাউন্ট ভেরিফাই করা হচ্ছে...", show_alert=False)

        is_created = check_gmail_exists(email)

        if not is_created:
            bot.send_message(
                chat_id,
                f"❌ <b>অ্যাপ্রুভ করা সম্ভব হয়নি!</b>\n\nইমেইলটি (<code>{email}</code>) এখনও গুগল সার্ভারে তৈরি করা হয়নি। দয়া করে আগে সঠিকভাবে গুগল অ্যাকাউন্টটি তৈরি করে তারপর ক্লিক করুন।"
            )
            return

        proof = f"Gmail: {email}"
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("INSERT INTO tasks (user_id, task_type, proof_data, reward) VALUES (?, 'gmail', ?, ?)",
                    (user_id, proof, user_states[user_id]['reward']))
        conn.commit()
        conn.close()

        delete_credentials_msg(chat_id, user_id)

        bot.send_message(chat_id, "🎉 <b>জিমেইল অ্যাকাউন্টটি সফলভাবে ভেরিফাই হয়ে জমা হয়েছে!</b>")
        if user_id in user_states:
            del user_states[user_id]

    elif call.data == "cancel_task":
        delete_credentials_msg(chat_id, user_id)
        if user_id in user_states:
            del user_states[user_id]
        bot.answer_callback_query(call.id, "টাস্ক বাতিল করা হয়েছে।")
        bot.send_message(chat_id, "❌ <b>টাস্কটি বাতিল করা হয়েছে।</b>")
        send_main_menu(chat_id, call.from_user.first_name)

    elif call.data == "menu_referral":
        me = bot.get_me()
        link = f"https://t.me/{me.username}?start={user_id}"
        msg = f"👥 <b>REFERRAL PROGRAM</b>\n\n🔗 <b>আপনার রেফারেল লিংক:</b>\n<code>{link}</code>\n\n💰 <b>কমিশন:</b> ১০%"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, msg)

    elif call.data in ["menu_guide", "menu_support"]:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "ℹ️ তথ্য পরবর্তীতে যুক্ত করা হবে।")

# ==============================
# INPUT HANDLERS
# ==============================
@bot.message_handler(func=lambda m: True)
def handle_text_inputs(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()

    if user_id not in user_states:
        return

    state = user_states[user_id].get("step")

    if state == "ig_wait_2fa_key":
        try:
            clean_secret = text.replace(" ", "")
            totp = pyotp.TOTP(clean_secret)
            otp_code = totp.now()
            
            user_states[user_id]["secret"] = clean_secret
            
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                types.InlineKeyboardButton("✅ অ্যাকাউন্ট খোলা শেষ", callback_data="ig_finish"),
                types.InlineKeyboardButton("❌ বাতিল", callback_data="cancel_task")
            )
            bot.send_message(
                chat_id,
                f"🔑 <b>অটো জেনারেটেড ২এফএ কোড:</b> <code>{otp_code}</code>\n\nকোডটি নিয়ে ইনস্টাগ্রামে ব্যবহার করুন। কাজ শেষ হলে নিচের বাটনে চাপ দিন:",
                reply_markup=keyboard
            )
        except Exception:
            bot.send_message(chat_id, "⚠️ সঠিক ২এফএ সিক্রেট কী দিন।")

    elif state == "fb_wait_uid":
        if not is_valid_fb_uid(text):
            bot.send_message(
                chat_id,
                "❌ <b>ইউআইডিটি সঠিক নয়!</b>\n\nইউআইডি অবশ্যই শুধুমাত্র সংখ্যা হতে হবে এবং এটি গ্রহণ করা হয়নি। অনুগ্রহ করে আপনার সঠিক ফেসবুক <b>UID</b> টি পুনরায় পাঠান:"
            )
            return

        user_states[user_id]["uid"] = text
        user_states[user_id]["step"] = "fb_wait_cookie"
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("🍪 কুকিস সেন্ড করুন", callback_data="fb_click_cookie_btn"),
            types.InlineKeyboardButton("❌ বাতিল", callback_data="cancel_task")
        )
        bot.send_message(chat_id, "✅ UID সফলভাবে গ্রহণ করা হয়েছে! কুকিস পাঠাতে নিচের বাটনে চাপ দিন:", reply_markup=keyboard)

    elif state == "fb_wait_cookie":
        if not is_valid_fb_cookie(text):
            bot.send_message(
                chat_id,
                "❌ <b>কুকিটি অরিজিনাল বা সঠিক নয়!</b>\n\nএটি ফেসবুকের অরিজিনাল কুকি ডাটা হিসেবে মিলছে না। অনুগ্রহ করে সঠিক এবং অরিজিনাল <b>Cookie</b> টি পেস্ট করে পাঠান:"
            )
            return

        user_states[user_id]["cookie"] = text
        user_states[user_id]["step"] = "none"

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("✅ অ্যাকাউন্ট খোলা শেষ", callback_data="fb_finish"),
            types.InlineKeyboardButton("❌ বাতিল", callback_data="cancel_task")
        )
        bot.send_message(chat_id, "✅ অরিজিনাল কুকিস সফলভাবে গ্রহণ করা হয়েছে! কাজ শেষে নিচের বাটনে ক্লিক করুন:", reply_markup=keyboard)

    elif state == "withdraw_amount":
        if not text.isdigit():
            bot.send_message(chat_id, "❌ শুধুমাত্র সঠিক সংখ্যা লিখুন।")
            return
        
        amount = float(text)
        if amount < 30:
            bot.send_message(chat_id, "❌ সর্বনিম্ন উইথড্র ৩০ টাকা।")
            return

        user_data = get_user(user_id)
        if user_data[2] < amount:
            bot.send_message(chat_id, f"❌ আপনার পর্যাপ্ত ব্যালেন্স নেই। বর্তমান ব্যালেন্স: {user_data[2]:.2f} BDT")
            del user_states[user_id]
            return

        user_states[user_id]["amount"] = amount
        user_states[user_id]["step"] = "withdraw_address"
        bot.send_message(chat_id, "📍 <b>আপনার সঠিক USDT (BEP20) অ্যাড্রেসটি এখানে প্রদান করুন:</b>")

    elif state == "withdraw_address":
        amount = user_states[user_id]["amount"]
        address = text
        net_amount = amount - 5.0

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, user_id))
        cur.execute("INSERT INTO withdrawals (user_id, amount, net_amount, address) VALUES (?, ?, ?, ?)",
                    (user_id, amount, net_amount, address))
        w_id = cur.lastrowid
        conn.commit()
        conn.close()

        bot.send_message(
            chat_id,
            f"⏳ <b>আপনার উইথড্র রিকুয়েস্টটি বর্তমানে পেন্ডিংয়ে রয়েছে!</b>\n\n💳 পরিমাণ: {amount} BDT\n⛽ চার্জ কেটে পাবেন: {net_amount} BDT\n📍 অ্যাড্রেস: <code>{address}</code>\n\nঅ্যাডমিন এটি ভেরিফাই করার পর আপনার উইথড্রটি কনফার্ম করবে।"
        )
        
        bot.send_message(
            ADMIN_ID,
            f"🚨 <b>নতুন উইথড্র রিকুয়েস্ট #{w_id}</b>\nUser: <code>{user_id}</code>\nAmount: {amount} BDT\nNet: {net_amount} BDT\nAddress: <code>{address}</code>\n\nঅ্যাপ্রুভ করতে: `/approve_w {w_id}`"
        )
        del user_states[user_id]

# ==============================
# ADMIN COMMANDS
# ==============================
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tasks WHERE status='pending'")
    p_tasks = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'")
    p_withdraws = cur.fetchone()[0]
    conn.close()

    msg = f"""
👑 <b>ADMIN PANEL</b>

📌 পেন্ডিং টাস্ক: {p_tasks} টি
📌 পেন্ডিং উইথড্র: {p_withdraws} টি

<b>কমান্ড:</b>
1. টাস্ক দেখতে: `/tasks`
2. টাস্ক অ্যাপ্রুভ: `/approve_t <task_id>`
3. উইথড্র অ্যাপ্রুভ: `/approve_w <withdraw_id>`
"""
    bot.send_message(ADMIN_ID, msg)

@bot.message_handler(commands=["tasks"])
def view_pending_tasks(message):
    if message.from_user.id != ADMIN_ID:
        return

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, task_type, proof_data, reward FROM tasks WHERE status='pending' LIMIT 5")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        bot.send_message(ADMIN_ID, "✅ কোনো পেন্ডিং টাস্ক নেই।")
        return

    for r in rows:
        bot.send_message(
            ADMIN_ID,
            f"🆔 <b>Task #{r[0]}</b>\nUser: <code>{r[1]}</code>\nType: {r[2]}\nReward: {r[4]} BDT\nProof: <code>{r[3]}</code>\n\nঅ্যাপ্রুভ করতে: `/approve_t {r[0]}`"
        )

@bot.message_handler(commands=["approve_t"])
def approve_task_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        bot.send_message(ADMIN_ID, "উপায়: `/approve_t <task_id>`")
        return

    task_id = int(args[1])
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute("SELECT user_id, reward, status FROM tasks WHERE id=?", (task_id,))
    task = cur.fetchone()

    if not task or task[2] != 'pending':
        bot.send_message(ADMIN_ID, "❌ টাস্ক পাওয়া যায়নি বা ইতোমধ্যে অ্যাপ্রুভড।")
        conn.close()
        return

    u_id, reward = task[0], task[1]
    cur.execute("UPDATE tasks SET status='approved' WHERE id=?", (task_id,))
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (reward, u_id))
    
    cur.execute("SELECT referred_by FROM users WHERE user_id=?", (u_id,))
    ref_row = cur.fetchone()
    if ref_row and ref_row[0]:
        ref_id = ref_row[0]
        ref_bonus = reward * 0.10
        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (ref_bonus, ref_id))
        try:
            bot.send_message(ref_id, f"🎉 <b>রেফারেল বোনাস!</b> আপনার ১০% কমিশন (<b>+{ref_bonus:.2f} BDT</b>) যোগ হয়েছে।")
        except Exception:
            pass

    conn.commit()
    conn.close()

    bot.send_message(ADMIN_ID, f"✅ Task #{task_id} Approved!")
    try:
        bot.send_message(u_id, f"🎉 আপনার টাস্ক #{task_id} অ্যাপ্রুভ হয়েছে এবং <b>{reward:.2f} BDT</b> ব্যালেন্সে যোগ হয়েছে!")
    except Exception:
        pass

@bot.message_handler(commands=["approve_w"])
def approve_withdraw_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        bot.send_message(ADMIN_ID, "উপায়: `/approve_w <withdraw_id>`")
        return

    w_id = int(args[1])
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute("SELECT user_id, net_amount, address, status FROM withdrawals WHERE id=?", (w_id,))
    w_data = cur.fetchone()

    if not w_data or w_data[3] != 'pending':
        bot.send_message(ADMIN_ID, "❌ উইথড্র ডাটা পাওয়া যায়নি বা অ্যাপ্রুভড।")
        conn.close()
        return

    u_id, net_amount, address = w_data[0], w_data[1], w_data[2]
    cur.execute("UPDATE withdrawals SET status='approved' WHERE id=?", (w_id,))
    conn.commit()
    conn.close()

    bot.send_message(ADMIN_ID, f"✅ Withdraw #{w_id} Confirmed!")
    try:
        bot.send_message(
            u_id,
            f"🎉 <b>আপনার উইথড্রটি সাকসেস করা হয়েছে!</b>\n\nআপনার <b>{net_amount:.2f} BDT</b> নিচের USDT (BEP20) অ্যাড্রেসে পাঠানো হয়েছে:\n📍 <code>{address}</code>"
        )
    except Exception:
        pass

# ==============================
# MAIN LOOP WITH AUTO RECONNECT
# ==============================
if __name__ == "__main__":
    init_db()
    print("================================")
    print("🤖 UPDATED TASK BOT IS RUNNING")
    print("================================")
    
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5, skip_pending=True)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
