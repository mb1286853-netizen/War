"""
🏆 ربات Warzone - نسخه Railway اصلاح شده
قسمت 1 از 5
"""

import asyncio
import logging
import sqlite3
import random
import time
import os
import json
import shutil
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import aiohttp
from pathlib import Path

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
)
from dotenv import load_dotenv

# ==================== CONFIG ====================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DEVELOPER_ID = os.getenv("DEVELOPER_ID", "")  # آیدی شما برای پشتیبانی

# تنظیمات logging برای Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# ==================== DATABASE CLASS ====================
# main.py - بخش Database تصحیح شده
class Database:
    def __init__(self):
        self.db_path = "warzone.db"
        self.backup_dir = "backups"
        self.setup_database()
        self.start_backup_scheduler()
    
    def setup_database(self):
        """ایجاد دیتابیس و جدول‌ها"""
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # جدول کاربران
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                zone_coin INTEGER DEFAULT 1000,
                zone_gem INTEGER DEFAULT 0,  -- تغییر: کاربران عادی جم ندارند
                zone_point INTEGER DEFAULT 500,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                is_admin BOOLEAN DEFAULT 0,
                miner_level INTEGER DEFAULT 1,
                last_miner_claim INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول موشک‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_missiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                missile_name TEXT,
                quantity INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # جدول ترکیب‌های ساخته شده
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_combos (
                combo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                combo_name TEXT,
                missiles TEXT,  -- JSON list of missiles
                damage_multiplier REAL DEFAULT 1.0,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # جدول پشتیبانی
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS support_tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                status TEXT DEFAULT 'open',
                admin_reply TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # جدول حملات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attacks (
                attack_id INTEGER PRIMARY KEY AUTOINCREMENT,
                attacker_id INTEGER,
                target_id INTEGER,
                damage INTEGER,
                missile_type TEXT,
                combo_type TEXT,
                custom_combo_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول لاگ برای عیب‌یابی Railway
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS railway_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ دیتابیس راه‌اندازی شد")
        self.log_event("database_setup", "Database initialized successfully")
# ==================== BOT INIT ====================
bot = Bot(token=TOKEN)
dp = Dispatcher()
db = Database()

# ==================== COMBO SYSTEM ====================
class ComboSystem:
    """سیستم ساخت ترکیب‌های شخصی"""
    
    @staticmethod
    def get_combo_requirements(combo_type: str):
        """نیازمندی‌های هر ترکیب"""
        requirements = {
            "basic": {"name": "ترکیب پایه", "missiles": 2, "damage_multiplier": 1.3},
            "advanced": {"name": "ترکیب پیشرفته", "missiles": 3, "damage_multiplier": 1.7},
            "elite": {"name": "ترکیب نخبه", "missiles": 4, "damage_multiplier": 2.2},
            "ultimate": {"name": "ترکیب نهایی", "missiles": 5, "damage_multiplier": 3.0}
        }
        return requirements.get(combo_type)
    
    @staticmethod
    def create_combo_keyboard():
        """کیبورد سیستم ترکیب"""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔧 ساخت ترکیب جدید", callback_data="create_combo")],
                [InlineKeyboardButton(text="📋 ترکیب‌های من", callback_data="my_combos")],
                [InlineKeyboardButton(text="⚔️ استفاده از ترکیب", callback_data="use_combo")],
                [InlineKeyboardButton(text="🗑️ حذف ترکیب", callback_data="delete_combo")],
                [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main")]
            ]
        )

# ==================== KEYBOARD FUNCTIONS ====================
def get_main_keyboard():
    """کیبورد اصلی"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 پنل جنگجو"), KeyboardButton(text="⚔️ حمله")],
            [KeyboardButton(text="🏦 بازار جنگ"), KeyboardButton(text="⛏️ معدن‌چی")],
            [KeyboardButton(text="🔧 سیستم ترکیب"), KeyboardButton(text="🎁 جعبه‌ها")],
            [KeyboardButton(text="🏆 رده‌بندی"), KeyboardButton(text="🛡️ پایگاه")],
            [KeyboardButton(text="📞 پشتیبانی"), KeyboardButton(text="ℹ️ راهنما")]
        ],
        resize_keyboard=True
    )

def get_support_keyboard():
    """کیبورد پشتیبانی"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📩 ارسال پیام به پشتیبانی", callback_data="send_support")],
            [InlineKeyboardButton(text="📨 پیام‌های من", callback_data="my_tickets")],
            [InlineKeyboardButton(text="📋 قوانین", callback_data="support_rules")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main")]
        ]
    )

# ادامه در قسمت بعدی...
# ادامه از قسمت 1...

def get_warrior_keyboard():
    """کیبورد پنل جنگجو"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 کیف پول", callback_data="wallet")],
            [InlineKeyboardButton(text="🚀 زرادخانه", callback_data="arsenal")],
            [InlineKeyboardButton(text="🔧 ترکیب‌ها", callback_data="combos")],
            [InlineKeyboardButton(text="🛡️ دفاع", callback_data="defense")],
            [InlineKeyboardButton(text="📊 آمار من", callback_data="stats")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main")]
        ]
    )

def get_market_keyboard():
    """کیبورد بازار"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 موشک‌های سریع", callback_data="market_fast")],
            [InlineKeyboardButton(text="💀 موشک‌های آخرالزمانی", callback_data="market_apocalypse")],
            [InlineKeyboardButton(text="🛩️ جنگنده‌ها", callback_data="market_fighters")],
            [InlineKeyboardButton(text="🏰 ارتقای پایگاه", callback_data="market_base")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main")]
        ]
    )

def get_miner_keyboard():
    """کیبورد معدن‌چی"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⛏️ برداشت ZP", callback_data="miner_claim")],
            [InlineKeyboardButton(text="⬆️ ارتقای ماینر", callback_data="miner_upgrade")],
            [InlineKeyboardButton(text="📊 اطلاعات ماینر", callback_data="miner_info")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main")]
        ]
    )

def get_back_keyboard():
    """دکمه بازگشت"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main")]
        ]
    )

# ==================== GAME DATA ====================
MISSILES = {
    "fast": [
        {"name": "شهاب (Meteor)", "damage": 50, "price": 200, "level": 1},
        {"name": "تگرگ (Hailstorm)", "damage": 70, "price": 500, "level": 2},
        {"name": "سیل (Torrent)", "damage": 90, "price": 1000, "level": 3},
        {"name": "توفان (Tempest)", "damage": 110, "price": 2000, "level": 4},
        {"name": "آذرخش (Thunderbolt)", "damage": 130, "price": 5000, "level": 5}
    ],
    "apocalypse": [
        {"name": "ارمغدن (Armageddon)", "damage": 500, "price": 50000, "gems": 15, "level": 15},
        {"name": "اپوکالیپس (Apocalypse)", "damage": 400, "price": 40000, "gems": 12, "level": 12},
        {"name": "رگناروک (Ragnarok)", "damage": 350, "price": 35000, "gems": 10, "level": 10},
        {"name": "هارمجدون (Harmagedon)", "damage": 300, "price": 30000, "gems": 8, "level": 8},
        {"name": "آتنا (Athena)", "damage": 250, "price": 25000, "gems": 5, "level": 6}
    ]
}

FIGHTERS = [
    {"name": "فانتوم (Phantom)", "bonus": 20, "price": 3000},
    {"name": "سوخو ۳۵ (Sukhoi 35)", "bonus": 30, "price": 6000},
    {"name": "رپتور (Raptor)", "bonus": 35, "price": 8000},
    {"name": "میگ ۲۹ (MiG-29)", "bonus": 25, "price": 4000},
    {"name": "کایت (Kite)", "bonus": 40, "price": 10000}
]

# ==================== HANDLERS ====================
@dp.message(CommandStart())
async def start_command(message: Message):
    """دستور /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "ندارد"
    full_name = message.from_user.full_name
    
    # ایجاد کاربر جدید (بدون جم)
    db.create_user(user_id, username, full_name)
    
    welcome_text = f"""
🎮 **به جنگ‌زون خوش آمدی، {full_name}!** 🚀

🛡️ **تو رهبر نظامی یک پایگاه هستی!**
🎯 **مأموریت:** گسترش قلمرو، ساخت ترکیب‌های مرگبار!

📊 **وضعیت اولیه:**
💰 سکه: 1,000
💎 جم: 0 (فقط از طریق جعبه یا ادمین)
🎯 ZP: 500

🔧 **قابلیت جدید:** ساخت ترکیب شخصی!
📞 **پشتیبانی:** دکمه پایین
"""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())
    db.log_event("user_started", f"{user_id} - {full_name}")

@dp.message(Command("help"))
async def help_command(message: Message):
    """دستور /help"""
    help_text = """
📚 **راهنمای ربات:**

🎮 **پنل جنگجو:** وضعیت و تجهیزات
⚔️ **حمله:** حمله به کاربران دیگر
🔧 **سیستم ترکیب:** ساخت ترکیب شخصی
🏦 **بازار جنگ:** خرید موشک
⛏️ **معدن‌چی:** کسب درآمد ZP
🎁 **جعبه‌ها:** شانس برنده شدن جم
📞 **پشتیبانی:** ارتباط با ادمین

💡 **نکته مهم:** کاربران عادی جم ندارند!
جم فقط از طریق:
1. جعبه‌های رمزی (شانس کم)
2. ادمین (هدیه)
3. برنده شدن در رویدادها
"""
    await message.answer(help_text)

@dp.message(F.text == "🎮 پنل جنگجو")
async def warrior_panel(message: Message):
    """منوی پنل جنگجو"""
    panel_text = """
🎮 **پنل جنگجو**

در این بخش می‌توانی:
• موجودی منابع را ببینی
• زرادخانه موشک‌ها را مدیریت کنی
• ترکیب‌های شخصی بسازی
• سیستم دفاعی را ارتقا دهی
• آمار کامل خود را مشاهده کنی
"""
    await message.answer(panel_text, reply_markup=get_warrior_keyboard())

@dp.message(F.text == "🔧 سیستم ترکیب")
async def combo_system_panel(message: Message):
    """منوی سیستم ترکیب"""
    combo_text = """
🔧 **سیستم ترکیب‌سازی**

🎯 **ساخت ترکیب شخصی:**
می‌توانی با موشک‌های مختلف، ترکیب‌های منحصربفرد بسازی!

📊 **انواع ترکیب:**
• **پایه:** 2 موشک - 1.3x damage
• **پیشرفته:** 3 موشک - 1.7x damage  
• **نخبه:** 4 موشک - 2.2x damage
• **نهایی:** 5 موشک - 3.0x damage

💡 **نکته:** هر ترکیب damage مخصوص خودش را دارد!
"""
    await message.answer(combo_text, reply_markup=ComboSystem.create_combo_keyboard())

@dp.message(F.text == "📞 پشتیبانی")
async def support_panel(message: Message):
    """منوی پشتیبانی"""
    support_text = """
📞 **سیستم پشتیبانی**

🤝 **برای ارتباط با ادمین:**
• پیام خود را ارسال کن
• در سریع‌ترین زمان پاسخ می‌گیری
• فقط موارد مهم و باگ‌ها

📋 **قوانین پشتیبانی:**
1. احترام متقابل
2. عدم ارسال اسپم
3. توضیح کامل مشکل
4. صبر برای پاسخ

⚠️ **توجه:** فقط پیام‌های مهم را ارسال کنید!
"""
    await message.answer(support_text, reply_markup=get_support_keyboard())

@dp.message(F.text == "🏦 بازار جنگ")
async def war_market(message: Message):
    """منوی بازار جنگ"""
    market_text = """
🏦 **بازار جنگ**

💎 **تغییر مهم:** کاربران عادی جم ندارند!

🔥 **موشک‌های سریع:** فقط با سکه
💀 **موشک‌های آخرالزمانی:** سکه + جم
🛩️ **جنگنده‌ها:** افزایش damage
🏰 **ارتقای پایگاه:** تقویت دفاع

🎯 **جم فقط از طریق:**
• جعبه‌های رمزی
• ادمین
• رویدادهای ویژه
"""
    await message.answer(market_text, reply_markup=get_market_keyboard())

@dp.message(F.text == "⛏️ معدن‌چی")
async def miner_panel(message: Message):
    """منوی معدن‌چی"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if user:
        miner_level = user[10]
        income_per_hour = miner_level * 100
        
        miner_text = f"""
⛏️ **معدن‌چی ZP**

📊 **وضعیت ماینر:**
• سطح: {miner_level}
• درآمد ساعتی: {income_per_hour} ZP
• برداشت بعدی: هر 1 ساعت

💰 **هزینه ارتقا:** {miner_level * 200} سکه
📈 **درآمد بعدی:** {(miner_level + 1) * 100} ZP/ساعت
"""
    else:
        miner_text = "⚠️ ابتدا با /start ثبت‌نام کن!"
    
    await message.answer(miner_text, reply_markup=get_miner_keyboard())

@dp.message(F.text == "⚔️ حمله")
async def attack_panel(message: Message):
    """منوی حمله"""
    attack_text = """
⚔️ **سیستم حمله**

🎯 **انواع حمله:**

⚡ **حمله سریع:** با یک موشک
💥 **ترکیب ۱:** 1.5x damage
🔥 **ترکیب ۲:** 2.0x damage  
💀 **ترکیب ۳:** 3.0x damage
🔧 **ترکیب شخصی:** damage متغیر

📝 **نحوه حمله:**
1. روی پیام کاربر ریپلای کن
2. دکمه حمله را بزن
3. نوع حمله را انتخاب کن
4. حمله انجام می‌شود!

⚠️ **جم نیاز نیست!** فقط موشک لازم است.
"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ سریع", callback_data="attack_fast")],
            [InlineKeyboardButton(text="💥 ترکیب ۱", callback_data="attack_combo1")],
            [InlineKeyboardButton(text="🔥 ترکیب ۲", callback_data="attack_combo2")],
            [InlineKeyboardButton(text="💀 ترکیب ۳", callback_data="attack_combo3")],
            [InlineKeyboardButton(text="🔧 ترکیب شخصی", callback_data="attack_custom")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main")]
        ]
    )
    await message.answer(attack_text, reply_markup=keyboard)

@dp.message(F.text == "🎁 جعبه‌های رمزی")
async def mystery_boxes(message: Message):
    """منوی جعبه‌های رمزی"""
    boxes_text = """
🎁 **جعبه‌های رمزی**

💎 **تنها راه کاربران برای دریافت جم!**

1. 📦 **باکس سکه** - 500 سکه
   • جایزه: 100-2,000 سکه

2. 💎 **باکس جم** - 1,000 سکه  
   • جایزه: 1-5 جم (شانس 30%)
   • شانس برنده شدن کم است!

3. 🎯 **باکس ZP** - 1,500 سکه
   • جایزه: 50-500 ZP

4. 🏆 **باکس افسانه‌ای** - 2,000 سکه
   • جایزه: 1-3 جم + سکه

5. 🆓 **باکس رایگان** - روزی 1 بار
   • جایزه: تصادفی

⚡ برای خرید، عدد جعبه را بفرست
"""
    await message.answer(boxes_text, reply_markup=get_back_keyboard())

@dp.message(F.text == "🏆 رده‌بندی")
async def rankings(message: Message):
    """رده‌بندی کاربران"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT username, zone_point, level, zone_gem 
        FROM users 
        WHERE username IS NOT NULL 
        ORDER BY zone_point DESC 
        LIMIT 10
    ''')
    
    top_users = cursor.fetchall()
    conn.close()
    
    if not top_users:
        await message.answer("هنوز کاربری در سیستم وجود ندارد!")
        return
    
    ranking_text = "🏆 **رده‌بندی برترین‌ها**\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, user in enumerate(top_users[:10]):
        username = user[0] or "ناشناس"
        zp = user[1]
        level = user[2]
        gems = user[3]
        
        if i < 3:
            ranking_text += f"{medals[i]} **{username}**\n"
        else:
            ranking_text += f"{i+1}. **{username}**\n"
        
        ranking_text += f"   🎯 ZP: {zp:,} | 📊 لول: {level} | 💎 جم: {gems}\n\n"
    
    ranking_text += "💡 **نکته:** کاربران با ZP بیشتر در رده بالاتر هستند!"
    
    await message.answer(ranking_text, reply_markup=get_back_keyboard())

# ادامه در قسمت بعدی...
# ادامه از قسمت 2...

@dp.message(F.text == "🛡️ پایگاه من")
async def my_base(message: Message):
    """اطلاعات پایگاه کاربر"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("⚠️ ابتدا با /start ثبت‌نام کن!")
        return
    
    # محاسبه زمان باقی‌مانده برای برداشت
    last_claim = user[11]
    current_time = int(time.time())
    
    if last_claim == 0:
        claim_status = "✅ آماده برداشت"
    elif (current_time - last_claim) < 3600:
        remaining = 3600 - (current_time - last_claim)
        minutes = remaining // 60
        seconds = remaining % 60
        claim_status = f"⏳ {minutes}:{seconds:02d} دیگر"
    else:
        claim_status = "✅ آماده برداشت"
    
    base_text = f"""
🛡️ **پایگاه {message.from_user.full_name}**

📊 **وضعیت کلی:**
• 🎯 سطح: {user[6]}
• ⭐ XP: {user[7]}/1000
• 💎 جم: {user[4]:,} (کاربران عادی ندارند)
• 💰 سکه: {user[3]:,}
• 🎯 ZP: {user[5]:,}

⛏️ **معدن:**
• سطح ماینر: {user[10]}
• درآمد ساعتی: {user[10] * 100} ZP
• وضعیت برداشت: {claim_status}

🔧 **ترکیب‌های ساخته شده:**
برای مشاهده به بخش سیستم ترکیب بروید
"""
    
    await message.answer(base_text, reply_markup=get_back_keyboard())

@dp.message(F.text == "ℹ️ راهنما")
async def help_menu(message: Message):
    """منوی راهنما"""
    help_text = """
ℹ️ **راهنمای کامل ربات**

🎮 **تغییرات مهم:**
1. کاربران عادی **جم ندارند**
2. جم فقط از جعبه‌ها یا ادمین
3. سیستم ترکیب‌سازی اضافه شد
4. پشتیبانی مستقیم با ادمین

⚔️ **حمله:**
• روی پیام کاربر ریپلای کن
• نوع حمله را انتخاب کن
• از ترکیب‌های شخصی استفاده کن

🔧 **ترکیب‌سازی:**
• موشک‌های مختلف ترکیب کن
• damage multiplier دریافت کن
• ترکیب‌های منحصربفرد بساز

💰 **اقتصاد:**
• هر ساعت از ماینر برداشت کن
• با ZP در رده‌بندی صعود کن
• از جعبه‌ها شانس ببر

📞 **پشتیبانی:** دکمه پایین
🤖 **توسعه‌دهنده:** @{DEVELOPER_ID}
"""
    await message.answer(help_text, reply_markup=get_back_keyboard())

# ==================== CALLBACK HANDLERS ====================
@dp.callback_query(F.data == "main")
async def back_to_main(callback: CallbackQuery):
    """بازگشت به منوی اصلی"""
    try:
        await callback.message.delete()
    except:
        pass
    await callback.message.answer("🏠 منوی اصلی:", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "wallet")
async def show_wallet(callback: CallbackQuery):
    """نمایش کیف پول"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("⚠️ ابتدا ثبت‌نام کن!", show_alert=True)
        return
    
    wallet_text = f"""
💰 **کیف پول شما**

🪙 **سکه:** {user[3]:,}
💎 **جم:** {user[4]:,} 
🎯 **ZP:** {user[5]:,}

📊 **وضعیت:**
• سطح: {user[6]}
• XP: {user[7]}/1000
• ماینر: سطح {user[10]}

⚠️ **نکته:** کاربران عادی جم ندارند!
💎 جم فقط از طریق:
• 🎁 جعبه‌های رمزی (شانس کم)
• 👑 ادمین (هدیه)
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 جعبه‌ها", callback_data="boxes")],
            [InlineKeyboardButton(text="⛏️ معدن", callback_data="miner")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="warrior")]
        ]
    )
    
    await callback.message.edit_text(wallet_text, reply_markup=keyboard)
    await callback.answer()

# ==================== COMBO SYSTEM HANDLERS ====================
@dp.callback_query(F.data == "combos")
async def show_combos_menu(callback: CallbackQuery):
    """منوی ترکیب‌ها"""
    combo_text = """
🔧 **سیستم ترکیب‌سازی**

🎯 **با موشک‌های مختلف ترکیب بساز!**

📊 **انواع ترکیب:**
1. **پایه:** 2 موشک → 1.3x damage
2. **پیشرفته:** 3 موشک → 1.7x damage  
3. **نخبه:** 4 موشک → 2.2x damage
4. **نهایی:** 5 موشک → 3.0x damage

💡 **نکته:** هر ترکیب یک damage multiplier دارد!
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛠️ ساخت ترکیب", callback_data="create_combo")],
            [InlineKeyboardButton(text="📋 ترکیب‌های من", callback_data="my_combos")],
            [InlineKeyboardButton(text="⚔️ استفاده در حمله", callback_data="use_combo_attack")],
            [InlineKeyboardButton(text="🗑️ حذف ترکیب", callback_data="delete_combo_menu")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="warrior")]
        ]
    )
    
    await callback.message.edit_text(combo_text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "create_combo")
async def create_combo_step1(callback: CallbackQuery):
    """مرحله اول ساخت ترکیب"""
    user_id = callback.from_user.id
    
    # چک کردن تعداد موشک‌های کاربر
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT missile_name, quantity FROM user_missiles WHERE user_id = ? AND quantity > 0', 
                  (user_id,))
    user_missiles = cursor.fetchall()
    conn.close()
    
    if len(user_missiles) < 2:
        await callback.answer("❌ حداقل 2 نوع موشک مختلف نیاز داری!", show_alert=True)
        return
    
    combo_text = """
🛠️ **ساخت ترکیب جدید**

🎯 **انتخاب نوع ترکیب:**

1. 🔧 **پایه** (2 موشک)
   • Damage: 1.3x
   • نیاز: 2 موشک مختلف

2. ⚙️ **پیشرفته** (3 موشک)
   • Damage: 1.7x  
   • نیاز: 3 موشک مختلف

3. 🛡️ **نخبه** (4 موشک)
   • Damage: 2.2x
   • نیاز: 4 موشک مختلف

4. 👑 **نهایی** (5 موشک)
   • Damage: 3.0x
   • نیاز: 5 موشک مختلف

انتخاب کن:
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔧 ترکیب پایه", callback_data="combo_type_basic")],
            [InlineKeyboardButton(text="⚙️ ترکیب پیشرفته", callback_data="combo_type_advanced")],
            [InlineKeyboardButton(text="🛡️ ترکیب نخبه", callback_data="combo_type_elite")],
            [InlineKeyboardButton(text="👑 ترکیب نهایی", callback_data="combo_type_ultimate")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="combos")]
        ]
    )
    
    await callback.message.edit_text(combo_text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("combo_type_"))
async def create_combo_step2(callback: CallbackQuery):
    """مرحله دوم - انتخاب موشک‌ها"""
    combo_type = callback.data.replace("combo_type_", "")
    
    requirements = ComboSystem.get_combo_requirements(combo_type)
    if not requirements:
        await callback.answer("❌ نوع ترکیب نامعتبر!", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    # دریافت موشک‌های کاربر
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT missile_name, quantity 
        FROM user_missiles 
        WHERE user_id = ? AND quantity > 0
        ORDER BY missile_name
    ''', (user_id,))
    
    user_missiles = cursor.fetchall()
    conn.close()
    
    if len(user_missiles) < requirements["missiles"]:
        await callback.answer(f"❌ حداقل {requirements['missiles']} موشک مختلف نیاز داری!", show_alert=True)
        return
    
    # ایجاد دکمه‌های موشک‌ها
    buttons = []
    for missile in user_missiles:
        missile_name = missile[0]
        quantity = missile[1]
        btn_text = f"{missile_name} ({quantity} عدد)"
        btn_data = f"select_missile_{combo_type}_{missile_name}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=btn_data)])
    
    buttons.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="create_combo")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    combo_text = f"""
🛠️ **ساخت ترکیب {requirements['name']}**

📊 **مشخصات:**
• نوع: {requirements['name']}
• نیاز: {requirements['missiles']} موشک مختلف
• Damage: {requirements['damage_multiplier']}x

🎯 **موشک‌های موجود:**
انتخاب کن (حداقل {requirements['missiles']} موشک):
"""
    
    await callback.message.edit_text(combo_text, reply_markup=keyboard)
    await callback.answer()

# ==================== SUPPORT SYSTEM HANDLERS ====================
@dp.callback_query(F.data == "send_support")
async def send_support_message(callback: CallbackQuery):
    """ارسال پیام به پشتیبانی"""
    support_text = """
📩 **ارسال پیام به پشتیبانی**

✍️ **لطفاً پیام خود را بنویسید:**
• مشکل یا سوال خود را کامل توضیح دهید
• در صورت باگ، تصویر ارسال کنید
• شماره کاربری: {user_id}

⚠️ **توجه:**
• فقط پیام‌های مهم را ارسال کنید
• اسپم = مسدود شدن
• پاسخ ممکن است زمان‌بر باشد

💬 پیام خود را همین حالا بنویس...
"""
    
    user_id = callback.from_user.id
    support_text = support_text.replace("{user_id}", str(user_id))
    
    await callback.message.edit_text(support_text, reply_markup=get_back_keyboard())
    await callback.answer("پیام خود را بنویسید...")

@dp.callback_query(F.data == "my_tickets")
async def show_my_tickets(callback: CallbackQuery):
    """نمایش تیکت‌های کاربر"""
    user_id = callback.from_user.id
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ticket_id, message, status, admin_reply, created_at 
        FROM support_tickets 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 5
    ''', (user_id,))
    
    tickets = cursor.fetchall()
    conn.close()
    
    if not tickets:
        tickets_text = """
📨 **پیام‌های پشتیبانی**

📭 **هیچ پیامی نداری!**

برای ارسال پیام جدید:
📞 پشتیبانی → 📩 ارسال پیام
"""
    else:
        tickets_text = "📨 **پیام‌های پشتیبانی شما**\n\n"
        
        for ticket in tickets:
            ticket_id = ticket[0]
            message = ticket[1][:50] + "..." if len(ticket[1]) > 50 else ticket[1]
            status = ticket[2]
            admin_reply = ticket[3]
            created_at = ticket[4]
            
            status_icon = "✅" if status == "closed" else "🟡" if status == "answered" else "🔴"
            
            tickets_text += f"**#{ticket_id}** {status_icon}\n"
            tickets_text += f"📝 {message}\n"
            
            if admin_reply:
                tickets_text += f"📨 پاسخ: {admin_reply[:50]}...\n"
            
            tickets_text += f"⏰ {created_at[:10]}\n\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📩 پیام جدید", callback_data="send_support")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="support")]
        ]
    )
    
    await callback.message.edit_text(tickets_text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "support_rules")
async def show_support_rules(callback: CallbackQuery):
    """نمایش قوانین پشتیبانی"""
    rules_text = """
📋 **قوانین پشتیبانی**

✅ **مجاز:**
• گزارش باگ و خطا
• سوال درباره قابلیت‌ها
• پیشنهاد برای بهبود
• مشکلات فنی

❌ **ممنوع:**
• ارسال اسپم
• درخواست هک و تقلب
• توهین و بی‌احترامی
• درخواست منابع رایگان

⏰ **زمان پاسخگویی:**
• معمولاً 24-48 ساعت
• موارد فوری: سریع‌تر
• آخر هفته: ممکن است تاخیر داشته باشد

👤 **توسعه‌دهنده:** @{DEVELOPER_ID}
"""
    
    rules_text = rules_text.replace("{DEVELOPER_ID}", DEVELOPER_ID or "WarzoneSupport")
    
    await callback.message.edit_text(rules_text, reply_markup=get_back_keyboard())
    await callback.answer()

# ==================== SUPPORT MESSAGE HANDLER ====================
@dp.message(F.text & ~F.text.startswith("/"))
async def handle_support_message(message: Message):
    """پردازش پیام‌های پشتیبانی"""
    # چک کردن اگر کاربر در حالت پشتیبانی است
    user_id = message.from_user.id
    
    # اگر پیام طولانی‌تر از یک کلمه است و شامل کلمات کلیدی پشتیبانی
    if len(message.text.split()) > 3 and any(keyword in message.text.lower() for keyword in 
                                          ["باگ", "خطا", "مشکل", "سوال", "پشتیبانی", "help"]):
        
        # ذخیره پیام در دیتابیس
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO support_tickets (user_id, message, status)
            VALUES (?, ?, 'open')
        ''', (user_id, message.text))
        
        ticket_id = cursor.lastrowid
        conn.commit()
        
        # اطلاع به ادمین (شما)
        if DEVELOPER_ID:
            try:
                admin_message = f"""
📩 **پیام پشتیبانی جدید**

🆔 **کاربر:** {user_id}
👤 **نام:** {message.from_user.full_name}
📝 **پیام:** {message.text[:200]}...
🎫 **تیکت:** #{ticket_id}

برای پاسخ: /reply_{ticket_id}
"""
                await bot.send_message(int(DEVELOPER_ID), admin_message)
            except:
                pass
        
        conn.close()
        
        # پاسخ به کاربر
        await message.answer(f"""
✅ **پیام شما ثبت شد!**

🎫 **شماره تیکت:** #{ticket_id}
⏰ **پاسخ:** طی 24-48 ساعت
📞 **وضعیت:** در انتظار پاسخ

برای مشاهده وضعیت:
📞 پشتیبانی → 📨 پیام‌های من
""")
        
        db.log_event("support_ticket", f"User {user_id} created ticket #{ticket_id}")

# ادامه در قسمت بعدی...
# ادامه از قسمت 3...

# ==================== MINER SYSTEM ====================
@dp.callback_query(F.data == "miner_claim")
async def claim_miner(callback: CallbackQuery):
    """برداشت از ماینر"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("⚠️ ابتدا ثبت‌نام کن!", show_alert=True)
        return
    
    current_time = int(time.time())
    last_claim = user[11]
    miner_level = user[10]
    
    # چک کردن زمان برداشت
    if last_claim > 0 and (current_time - last_claim) < 3600:
        remaining = 3600 - (current_time - last_claim)
        minutes = remaining // 60
        seconds = remaining % 60
        
        await callback.answer(
            f"⏳ {minutes} دقیقه و {seconds} ثانیه دیگر می‌توانی برداشت کنی!",
            show_alert=True
        )
        return
    
    # محاسبه درآمد
    income = miner_level * 100
    new_zp = user[5] + income
    
    # بروزرسانی دیتابیس
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users 
        SET zone_point = ?, last_miner_claim = ? 
        WHERE user_id = ?
    ''', (new_zp, current_time, user_id))
    
    conn.commit()
    conn.close()
    
    claim_text = f"""
⛏️ **برداشت موفق!**

✅ **درآمد:** +{income} ZP
📊 **کل ZP:** {new_zp:,}
💰 **ماینر:** سطح {miner_level}
⏰ **برداشت بعدی:** 1 ساعت دیگر

⚡ برای درآمد بیشتر ماینر را ارتقا بده!
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬆️ ارتقای ماینر", callback_data="miner_upgrade")],
            [InlineKeyboardButton(text="📊 اطلاعات", callback_data="miner_info")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main")]
        ]
    )
    
    await callback.message.edit_text(claim_text, reply_markup=keyboard)
    await callback.answer("✅ برداشت شد!")
    db.log_event("miner_claim", f"User {user_id} claimed {income} ZP")

@dp.callback_query(F.data == "miner_upgrade")
async def upgrade_miner(callback: CallbackQuery):
    """ارتقای ماینر"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("⚠️ ابتدا ثبت‌نام کن!", show_alert=True)
        return
    
    miner_level = user[10]
    coins = user[3]
    upgrade_cost = miner_level * 200
    
    if coins < upgrade_cost:
        await callback.answer(f"❌ سکه کافی نیست! نیاز: {upgrade_cost} سکه", show_alert=True)
        return
    
    # بروزرسانی دیتابیس
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # کم کردن سکه
    cursor.execute('UPDATE users SET zone_coin = zone_coin - ? WHERE user_id = ?', 
                  (upgrade_cost, user_id))
    # افزایش سطح ماینر
    cursor.execute('UPDATE users SET miner_level = miner_level + 1 WHERE user_id = ?', 
                  (user_id,))
    
    conn.commit()
    
    # دریافت اطلاعات جدید
    cursor.execute('SELECT zone_coin, miner_level FROM users WHERE user_id = ?', (user_id,))
    new_data = cursor.fetchone()
    new_coins = new_data[0]
    new_level = new_data[1]
    
    conn.close()
    
    upgrade_text = f"""
⬆️ **ارتقای موفق!**

✅ ماینر به سطح {new_level} ارتقا یافت!
💰 هزینه: {upgrade_cost} سکه
💎 باقی‌مانده: {new_coins} سکه
📈 درآمد جدید: {new_level * 100} ZP/ساعت

🎉 حالا درآمد بیشتری داری!
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⛏️ برداشت", callback_data="miner_claim")],
            [InlineKeyboardButton(text="📊 اطلاعات", callback_data="miner_info")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main")]
        ]
    )
    
    await callback.message.edit_text(upgrade_text, reply_markup=keyboard)
    await callback.answer("✅ ماینر ارتقا یافت!")
    db.log_event("miner_upgrade", f"User {user_id} upgraded to level {new_level}")

# ==================== MARKET SYSTEM ====================
@dp.callback_query(F.data == "market_fast")
async def market_fast_missiles(callback: CallbackQuery):
    """موشک‌های سریع در بازار"""
    market_text = """
🔥 **موشک‌های سریع**

💰 **فقط با سکه قابل خرید!**

"""
    
    buttons = []
    for missile in MISSILES["fast"]:
        btn_text = f"{missile['name']} - {missile['price']} سکه"
        btn_data = f"buy_fast_{missile['name']}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=btn_data)])
    
    buttons.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="market")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    for missile in MISSILES["fast"]:
        market_text += f"• **{missile['name']}**\n"
        market_text += f"  ⚡ Damage: {missile['damage']}\n"
        market_text += f"  💰 قیمت: {missile['price']} سکه\n"
        market_text += f"  📊 سطح مورد نیاز: {missile['level']}\n\n"
    
    await callback.message.edit_text(market_text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_fast_"))
async def buy_fast_missile(callback: CallbackQuery):
    """خرید موشک سریع"""
    missile_name = callback.data.replace("buy_fast_", "")
    
    # پیدا کردن موشک
    missile_data = None
    for missile in MISSILES["fast"]:
        if missile["name"] == missile_name:
            missile_data = missile
            break
    
    if not missile_data:
        await callback.answer("❌ موشک یافت نشد!", show_alert=True)
        return
    
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("⚠️ ابتدا ثبت‌نام کن!", show_alert=True)
        return
    
    # چک کردن سطح
    if user[6] < missile_data["level"]:
        await callback.answer(f"❌ سطح شما کافی نیست! نیاز: سطح {missile_data['level']}", show_alert=True)
        return
    
    # چک کردن سکه
    if user[3] < missile_data["price"]:
        await callback.answer(f"❌ سکه کافی نیست! نیاز: {missile_data['price']} سکه", show_alert=True)
        return
    
    # خرید موشک
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # کم کردن سکه
    cursor.execute('UPDATE users SET zone_coin = zone_coin - ? WHERE user_id = ?', 
                  (missile_data["price"], user_id))
    
    # اضافه کردن موشک به کاربر
    cursor.execute('''
        INSERT INTO user_missiles (user_id, missile_name, quantity)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, missile_name) 
        DO UPDATE SET quantity = quantity + 1
    ''', (user_id, missile_name))
    
    conn.commit()
    
    # دریافت اطلاعات جدید
    cursor.execute('SELECT zone_coin FROM users WHERE user_id = ?', (user_id,))
    new_coins = cursor.fetchone()[0]
    
    cursor.execute('SELECT quantity FROM user_missiles WHERE user_id = ? AND missile_name = ?', 
                  (user_id, missile_name))
    result = cursor.fetchone()
    missile_count = result[1] if result else 1
    
    conn.close()
    
    buy_text = f"""
✅ **خرید موفق!**

🎯 **{missile_name}** خریداری شد!
⚡ Damage: {missile_data["damage"]}
💰 هزینه: {missile_data["price"]} سکه
📦 تعداد: {missile_count} عدد
💎 باقی‌مانده: {new_coins} سکه

🔧 می‌توانی از این موشک در ترکیب‌ها استفاده کنی!
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 بیشتر بخر", callback_data="market_fast")],
            [InlineKeyboardButton(text="🔧 ساخت ترکیب", callback_data="create_combo")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="market")]
        ]
    )
    
    await callback.message.edit_text(buy_text, reply_markup=keyboard)
    await callback.answer("✅ خرید موفق!")
    db.log_event("missile_purchase", f"User {user_id} bought {missile_name}")

# ==================== BOX SYSTEM ====================
@dp.message(lambda message: message.text.isdigit() and 1 <= int(message.text) <= 5)
async def handle_box_purchase(message: Message):
    """پردازش خرید جعبه"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("⚠️ ابتدا با /start ثبت‌نام کن!")
        return
    
    box_number = int(message.text)
    boxes_info = {
        1: {"name": "باکس سکه", "price": 500, "type": "coin"},
        2: {"name": "باکس جم", "price": 1000, "type": "gem"},
        3: {"name": "باکس ZP", "price": 1500, "type": "zp"},
        4: {"name": "باکس افسانه‌ای", "price": 2000, "type": "legendary"},
        5: {"name": "باکس رایگان", "price": 0, "type": "free"}
    }
    
    box_info = boxes_info.get(box_number)
    if not box_info:
        await message.answer("❌ شماره جعبه نامعتبر!")
        return
    
    # چک کردن باکس رایگان (یک بار در روز)
    if box_number == 5:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM purchases 
            WHERE user_id = ? AND item_type = 'free_box' 
            AND DATE(timestamp) = DATE('now')
        ''', (user_id,))
        
        free_today = cursor.fetchone()[0]
        conn.close()
        
        if free_today > 0:
            await message.answer("❌ باکس رایگان امروز رو قبلاً گرفتی!")
            return
    
    # چک کردن سکه
    if user[3] < box_info["price"]:
        await message.answer(f"❌ سکه کافی نیست! نیاز: {box_info['price']} سکه")
        return
    
    # محاسبه جایزه
    reward = 0
    reward_type = ""
    reward_text = ""
    
    if box_info["type"] == "coin":
        reward = random.randint(100, 2000)
        reward_type = "سکه"
        reward_text = f"💰 **{reward:,} سکه**"
        
    elif box_info["type"] == "gem":
        # شانس 30% برای بردن جم
        if random.random() < 0.3:
            reward = random.randint(1, 5)
            reward_type = "جم"
            reward_text = f"💎 **{reward} جم** (شانس کم!)"
        else:
            reward = random.randint(50, 500)
            reward_type = "سکه"
            reward_text = f"💰 **{reward:,} سکه** (جم نبردید)"
            
    elif box_info["type"] == "zp":
        reward = random.randint(50, 500)
        reward_type = "ZP"
        reward_text = f"🎯 **{reward} ZP**"
        
    elif box_info["type"] == "legendary":
        # شانس برای ترکیبی
        rand = random.random()
        if rand < 0.1:  # 10% شانس جم
            reward = random.randint(1, 3)
            reward_type = "جم"
            reward_text = f"💎 **{reward} جم** + 500 سکه"
            coin_bonus = 500
        elif rand < 0.4:  # 30% شانس ZP
            reward = random.randint(100, 300)
            reward_type = "ZP"
            reward_text = f"🎯 **{reward} ZP** + 300 سکه"
            coin_bonus = 300
        else:  # 60% شانس سکه
            reward = random.randint(500, 1500)
            reward_type = "سکه"
            reward_text = f"💰 **{reward:,} سکه**"
            coin_bonus = 0
            
    elif box_info["type"] == "free":
        rewards = [
            (random.randint(10, 100), "سکه", "💰"),
            (random.randint(1, 50), "ZP", "🎯"),
            (1 if random.random() < 0.1 else 0, "جم", "💎")  # 10% شانس 1 جم
        ]
        
        reward_amount, reward_type, reward_icon = random.choice(rewards)
        reward_text = f"{reward_icon} **{reward_amount} {reward_type}**"
    
    # بروزرسانی دیتابیس
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # کم کردن سکه (اگر باکس رایگان نیست)
    if box_info["price"] > 0:
        cursor.execute('UPDATE users SET zone_coin = zone_coin - ? WHERE user_id = ?', 
                      (box_info["price"], user_id))
    
    # اضافه کردن جایزه
    if reward_type == "سکه":
        cursor.execute('UPDATE users SET zone_coin = zone_coin + ? WHERE user_id = ?', 
                      (reward, user_id))
        if box_info["type"] == "legendary" and coin_bonus > 0:
            cursor.execute('UPDATE users SET zone_coin = zone_coin + ? WHERE user_id = ?', 
                          (coin_bonus, user_id))
            
    elif reward_type == "جم":
        cursor.execute('UPDATE users SET zone_gem = zone_gem + ? WHERE user_id = ?', 
                      (reward, user_id))
        if box_info["type"] == "legendary" and coin_bonus > 0:
            cursor.execute('UPDATE users SET zone_coin = zone_coin + ? WHERE user_id = ?', 
                          (coin_bonus, user_id))
            
    elif reward_type == "ZP":
        cursor.execute('UPDATE users SET zone_point = zone_point + ? WHERE user_id = ?', 
                      (reward, user_id))
        if box_info["type"] == "legendary" and coin_bonus > 0:
            cursor.execute('UPDATE users SET zone_coin = zone_coin + ? WHERE user_id = ?', 
                          (coin_bonus, user_id))
    
    # ثبت خرید
    cursor.execute('''
        INSERT INTO purchases (user_id, item_type, item_name, quantity, price)
        VALUES (?, 'box', ?, 1, ?)
    ''', (user_id, box_info["name"], box_info["price"]))
    
    conn.commit()
    conn.close()
    
    # ایجاد متن نتیجه
    box_result = f"""
🎁 **جعبه باز شد!**

📦 **جعبه:** {box_info['name']}
{'💰 **هزینه:** ' + str(box_info['price']) + ' سکه' if box_info['price'] > 0 else '🆓 **رایگان!**'}

🎉 **جایزه شما:** {reward_text}

✨ **شانس آوردی!** {'💎' if reward_type == 'جم' else ''}
"""
    
    await message.answer(box_result, reply_markup=get_back_keyboard())
    
    # لاگ کردن
    if reward_type == "جم":
        db.log_event("gem_won", f"User {user_id} won {reward} gems from box")

# ==================== ADMIN REPLY SYSTEM ====================
@dp.message(Command("reply"))
async def admin_reply_to_ticket(message: Message):
    """پاسخ ادمین به تیکت"""
    user_id = message.from_user.id
    
    if str(user_id) != DEVELOPER_ID and user_id not in ADMIN_IDS:
        await message.answer("⛔ دسترسی ممنوع!")
        return
    
    # استخراج شماره تیکت از پیام
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("⚠️ فرمت صحیح: /reply <شماره_تیکت> <پیام>")
        return
    
    try:
        ticket_id = int(parts[1].replace("/reply_", ""))
        reply_text = " ".join(parts[2:])
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # دریافت اطلاعات تیکت
        cursor.execute('SELECT user_id, message FROM support_tickets WHERE ticket_id = ?', 
                      (ticket_id,))
        ticket = cursor.fetchone()
        
        if not ticket:
            await message.answer("❌ تیکت یافت نشد!")
            conn.close()
            return
        
        target_user_id = ticket[0]
        original_message = ticket[1]
        
        # بروزرسانی تیکت
        cursor.execute('''
            UPDATE support_tickets 
            SET status = 'answered', admin_reply = ? 
            WHERE ticket_id = ?
        ''', (reply_text, ticket_id))
        
        conn.commit()
        conn.close()
        
        # ارسال پیام به کاربر
        try:
            reply_message = f"""
📨 **پاسخ پشتیبانی**

🎫 **تیکت:** #{ticket_id}
📝 **پیام شما:** {original_message[:100]}...
👤 **ادمین:** {message.from_user.full_name}

💬 **پاسخ:** {reply_text}

✅ این تیکت بسته شد.
"""
            await bot.send_message(target_user_id, reply_message)
            await message.answer(f"✅ پاسخ به کاربر {target_user_id} ارسال شد!")
            
        except Exception as e:
            await message.answer(f"❌ نتوانستم به کاربر پیام بدم: {e}")
        
        db.log_event("admin_reply", f"Ticket #{ticket_id} answered")
        
    except ValueError:
        await message.answer("❌ شماره تیکت نامعتبر!")
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")

# ادامه در قسمت آخر...
# ادامه از قسمت 4...

# ==================== RAILWAY HEALTH CHECK ====================
@dp.message(Command("status"))
async def bot_status(message: Message):
    """بررسی وضعیت ربات"""
    user_id = message.from_user.id
    
    # فقط ادمین و توسعه‌دهنده
    if str(user_id) != DEVELOPER_ID and user_id not in ADMIN_IDS:
        await message.answer("⛔ دسترسی ممنوع!")
        return
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # آمار سیستم
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM railway_logs WHERE DATE(timestamp) = DATE("now")')
    today_logs = cursor.fetchone()[0]
    
    cursor.execute('SELECT event, timestamp FROM railway_logs ORDER BY timestamp DESC LIMIT 5')
    recent_logs = cursor.fetchall()
    
    conn.close()
    
    # وضعیت حافظه و زمان
    import psutil
    import datetime
    
    memory = psutil.virtual_memory()
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.datetime.now() - boot_time
    
    status_text = f"""
🖥️ **وضعیت سیستم ربات**

📊 **آمار:**
• 👥 کاربران: {total_users}
• 📝 لاگ امروز: {today_logs}
• 🕒 آپتایم: {uptime.days} روز, {uptime.seconds//3600} ساعت
• 💾 حافظه: {memory.percent}% استفاده شده

📈 **آخرین رویدادها:**
"""
    
    for log in recent_logs:
        event, timestamp = log
        status_text += f"• {event} - {timestamp[:19]}\n"
    
    status_text += f"""
🔧 **سیستم‌ها:**
• ✅ دیتابیس: فعال
• ✅ Backup: هر 6 ساعت  
• ✅ پشتیبانی: فعال
• ✅ ترکیب‌سازی: فعال

👨‍💻 **توسعه‌دهنده:** @{DEVELOPER_ID}
"""
    
    await message.answer(status_text)
    db.log_event("status_check", f"Admin {user_id} checked status")

# ==================== ADMIN GIFT SYSTEM ====================
@dp.message(Command("gift"))
async def admin_gift_command(message: Message):
    """هدیه دادن به کاربر توسط ادمین"""
    user_id = message.from_user.id
    
    if str(user_id) != DEVELOPER_ID and user_id not in ADMIN_IDS:
        await message.answer("⛔ دسترسی ممنوع!")
        return
    
    parts = message.text.split()
    if len(parts) < 4:
        await message.answer("""
⚠️ **فرمت صحیح:**
`/gift <آیدی_کاربر> <نوع> <مقدار>`

**انواع:**
• coin - سکه
• gem - جم (فقط ادمین می‌تواند بدهد)
• zp - ZP

**مثال:**
`/gift 123456789 coin 1000`
`/gift 123456789 gem 5`
""")
        return
    
    try:
        target_id = int(parts[1])
        resource_type = parts[2].lower()
        amount = int(parts[3])
        
        # محدودیت‌ها
        if resource_type == "gem" and amount > 50:
            await message.answer("❌ حداکثر 50 جم می‌توانی هدیه بدهی!")
            return
        
        if amount <= 0:
            await message.answer("❌ مقدار باید مثبت باشد!")
            return
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # چک کردن وجود کاربر
        cursor.execute('SELECT username FROM users WHERE user_id = ?', (target_id,))
        user = cursor.fetchone()
        
        if not user:
            await message.answer("❌ کاربر یافت نشد!")
            conn.close()
            return
        
        # بروزرسانی منابع کاربر
        if resource_type == "coin":
            cursor.execute('UPDATE users SET zone_coin = zone_coin + ? WHERE user_id = ?', 
                          (amount, target_id))
            resource_name = "سکه"
            emoji = "💰"
            
        elif resource_type == "gem":
            cursor.execute('UPDATE users SET zone_gem = zone_gem + ? WHERE user_id = ?', 
                          (amount, target_id))
            resource_name = "جم"
            emoji = "💎"
            
        elif resource_type == "zp":
            cursor.execute('UPDATE users SET zone_point = zone_point + ? WHERE user_id = ?', 
                          (amount, target_id))
            resource_name = "ZP"
            emoji = "🎯"
            
        else:
            await message.answer("❌ نوع منبع نامعتبر!")
            conn.close()
            return
        
        conn.commit()
        conn.close()
        
        # اطلاع به ادمین
        await message.answer(f"""
✅ **هدیه ارسال شد!**

{emoji} **نوع:** {resource_name}
📊 **مقدار:** {amount:,}
👤 **به کاربر:** {target_id}
👨‍💼 **توسط:** {message.from_user.full_name}
""")
        
        # اطلاع به کاربر (سعی کن)
        try:
            gift_notice = f"""
🎁 **هدیه دریافت کردی!**

{emoji} **{amount:,} {resource_name}**
👨‍💼 **از طرف ادمین**
📅 **زمان:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}

✨ از هدیه استفاده بهینه کن!
"""
            await bot.send_message(target_id, gift_notice)
        except:
            pass  # اگر نتوانستیم پیام بفرستیم
        
        db.log_event("admin_gift", f"Admin {user_id} gifted {amount} {resource_type} to {target_id}")
        
    except ValueError:
        await message.answer("❌ مقدار نامعتبر!")
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")

# ==================== FIX FOR RAILWAY CRASH ====================
async def railway_keep_alive():
    """سیستم نگه‌داری ربات در Railway"""
    try:
        # ایجاد یک درخواست ساده به خودمان
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('127.0.0.1', 8080))
        sock.close()
        
        if result == 0:
            db.log_event("railway_ping", "Railway ping successful")
        else:
            db.log_event("railway_ping", "Railway ping failed")
            
    except Exception as e:
        db.log_event("railway_ping_error", str(e))

# ==================== ERROR HANDLER ====================
@dp.errors()
async def error_handler(exception, message: Message):
    """مدیریت خطاها"""
    error_msg = f"""
❌ **خطا در ربات:**

**نوع:** {type(exception).__name__}
**پیام:** {str(exception)}
**کاربر:** {message.from_user.id if message else 'Unknown'}
**زمان:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    # لاگ در دیتابیس
    db.log_event("bot_error", f"{type(exception).__name__}: {str(exception)[:100]}")
    
    # اطلاع به توسعه‌دهنده
    if DEVELOPER_ID:
        try:
            await bot.send_message(int(DEVELOPER_ID), error_msg[:4000])
        except:
            pass
    
    # پاسخ به کاربر
    if message:
        try:
            await message.answer("⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.")
        except:
            pass

# ==================== BOT MAINTENANCE ====================
@dp.message(Command("maintenance"))
async def maintenance_mode(message: Message):
    """حالت تعمیر و نگهداری"""
    user_id = message.from_user.id
    
    if str(user_id) != DEVELOPER_ID:
        await message.answer("⛔ فقط توسعه‌دهنده!")
        return
    
    maintenance_text = """
🔧 **حالت تعمیر و نگهداری**

برای ری‌استارت ربات:
/restart - ری‌استارت نرم
/shutdown - خاموش کردن
/logs - مشاهده لاگ‌ها
/backup - ایجاد Backup دستی
/cleanup - پاک‌سازی دیتابیس
"""
    await message.answer(maintenance_text)

@dp.message(Command("restart"))
async def soft_restart(message: Message):
    """ری‌استارت نرم ربات"""
    user_id = message.from_user.id
    
    if str(user_id) != DEVELOPER_ID:
        await message.answer("⛔ فقط توسعه‌دهنده!")
        return
    
    await message.answer("🔄 در حال ری‌استارت...")
    
    # ایجاد لاگ
    db.log_event("bot_restart", "Soft restart initiated")
    
    # راه‌اندازی مجدد polling
    await dp.stop_polling()
    await main()

# ==================== MAIN FUNCTION WITH RAILWAY FIX ====================
async def main():
    """تابع اصلی اجرای ربات"""
    logger.info("🚀 Starting Warzone Bot with Railway fixes...")
    
    # تست اتصال به تلگرام
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot connected: @{bot_info.username}")
        db.log_event("bot_start", f"Connected as @{bot_info.username}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Telegram: {e}")
        db.log_event("bot_start_failed", str(e))
        return
    
    # حذف webhook قدیمی
    await bot.delete_webhook(drop_pending_updates=True)
    
    # شروع سیستم‌های background
    async def background_tasks():
        """وظایف پس‌زمینه برای Railway"""
        while True:
            try:
                # هر 5 دقیقه Railway را فعال نگه دار
                await railway_keep_alive()
                
                # هر 1 ساعت لاگ وضعیت
                db.log_event("bot_heartbeat", "Bot is running")
                
                await asyncio.sleep(300)  # 5 دقیقه
                
            except Exception as e:
                logger.error(f"❌ Background task error: {e}")
                await asyncio.sleep(60)
    
    # شروع tasks پس‌زمینه
    asyncio.create_task(background_tasks())
    
    # پیام شروع به توسعه‌دهنده
    if DEVELOPER_ID:
        try:
            await bot.send_message(int(DEVELOPER_ID), 
                                 "✅ ربات Warzone با موفقیت راه‌اندازی شد!\n" +
                                 f"🕒 زمان: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        except:
            pass
    
    logger.info("📱 Bot is running with Railway support...")
    
    try:
        # شروع polling با timeout بیشتر برای Railway
        await dp.start_polling(bot, 
                             allowed_updates=dp.resolve_used_update_types(),
                             timeout=60,
                             relax=1)
    except Exception as e:
        logger.error(f"❌ Polling error: {e}")
        db.log_event("polling_error", str(e))
        
        # تلاش مجدد بعد از 10 ثانیه
        await asyncio.sleep(10)
        await main()  # بازگشت به تابع اصلی

# ==================== ENTRY POINT WITH RAILWAY SUPPORT ====================
if __name__ == "__main__":
    # تنظیمات برای Railway
    import sys
    
    # اضافه کردن پوشه فعلی به مسیر
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    # تنظیم encoding
    if sys.platform == "win32":
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # اجرای اصلی با try-excatch
    try:
        # ایجاد فایل PID برای Railway
        with open("/tmp/bot.pid", "w") as f:
            f.write(str(os.getpid()))
        
        logger.info("=" * 50)
        logger.info("🏆 Warzone Bot Starting...")
        logger.info(f"👨‍💻 Developer: {DEVELOPER_ID}")
        logger.info(f"📅 Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 50)
        
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user (Ctrl+C)")
        db.log_event("bot_stop", "Stopped by user")
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        db.log_event("fatal_error", str(e))
        
        # تلاش مجدد بعد از 30 ثانیه
        import time
        time.sleep(30)
        
        # restart
        os.execv(sys.executable, [sys.executable] + sys.argv)
    
    finally:
        # پاک‌سازی
        try:
            os.remove("/tmp/bot.pid")
        except:
            pass
        
        logger.info("👋 Bot shutdown complete")
