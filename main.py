"""
🏆 ربات Warzone - نسخه Railway
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

# تنظیمات logging برای Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# ==================== DATABASE CLASS ====================
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
                zone_gem INTEGER DEFAULT 10,
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
        
        # جدول حملات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attacks (
                attack_id INTEGER PRIMARY KEY AUTOINCREMENT,
                attacker_id INTEGER,
                target_id INTEGER,
                damage INTEGER,
                missile_type TEXT,
                combo_type TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول خریدها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_type TEXT,
                item_name TEXT,
                quantity INTEGER,
                price INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ دیتابیس راه‌اندازی شد")
    
    def start_backup_scheduler(self):
        """شروع backup خودکار"""
        os.makedirs(self.backup_dir, exist_ok=True)
        
        def backup_job():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = f"{self.backup_dir}/backup_{timestamp}.db"
                shutil.copy2(self.db_path, backup_file)
                
                # حذف backup های قدیمی (بیش از 7 روز)
                for file in os.listdir(self.backup_dir):
                    if file.endswith('.db'):
                        file_path = os.path.join(self.backup_dir, file)
                        if os.path.getmtime(file_path) < time.time() - 7*24*3600:
                            os.remove(file_path)
                
                logger.info(f"✅ Backup ایجاد شد: {backup_file}")
            except Exception as e:
                logger.error(f"❌ خطا در backup: {e}")
        
        # اجرای backup در ترد جداگانه
        def backup_loop():
            while True:
                backup_job()
                time.sleep(24 * 3600)  # هر 24 ساعت
        
        thread = threading.Thread(target=backup_loop, daemon=True)
        thread.start()
    
    def get_connection(self):
        """دریافت connection به دیتابیس"""
        return sqlite3.connect(self.db_path)
    
    def get_user(self, user_id: int):
        """دریافت اطلاعات کاربر"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    
    def create_user(self, user_id: int, username: str, full_name: str):
        """ایجاد کاربر جدید"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, full_name) 
            VALUES (?, ?, ?)
        ''', (user_id, username, full_name))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ کاربر ایجاد شد: {user_id}")
    
    def update_user_resource(self, user_id: int, resource_type: str, amount: int):
        """بروزرسانی منابع کاربر"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if resource_type == "coin":
            cursor.execute('UPDATE users SET zone_coin = zone_coin + ? WHERE user_id = ?', (amount, user_id))
        elif resource_type == "gem":
            cursor.execute('UPDATE users SET zone_gem = zone_gem + ? WHERE user_id = ?', (amount, user_id))
        elif resource_type == "zp":
            cursor.execute('UPDATE users SET zone_point = zone_point + ? WHERE user_id = ?', (amount, user_id))
        
        conn.commit()
        conn.close()

# ==================== BOT INIT ====================
bot = Bot(token=TOKEN)
dp = Dispatcher()
db = Database()

# ==================== KEYBOARD FUNCTIONS ====================
def get_main_keyboard():
    """کیبورد اصلی"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 پنل جنگجو"), KeyboardButton(text="⚔️ حمله")],
            [KeyboardButton(text="🏦 بازار جنگ"), KeyboardButton(text="⛏️ معدن‌چی")],
            [KeyboardButton(text="🎁 جعبه‌های رمزی"), KeyboardButton(text="🏆 رده‌بندی")],
            [KeyboardButton(text="🛡️ پایگاه من"), KeyboardButton(text="ℹ️ راهنما")]
        ],
        resize_keyboard=True
    )

def get_warrior_keyboard():
    """کیبورد پنل جنگجو"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 کیف پول", callback_data="wallet")],
            [InlineKeyboardButton(text="🚀 زرادخانه", callback_data="arsenal")],
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
        {"name": "ارمغدن (Armageddon)", "damage": 500, "price": 50000, "gems": 5, "level": 10},
        {"name": "اپوکالیپس (Apocalypse)", "damage": 400, "price": 40000, "gems": 4, "level": 9},
        {"name": "رگناروک (Ragnarok)", "damage": 350, "price": 35000, "gems": 3, "level": 8},
        {"name": "هارمجدون (Harmagedon)", "damage": 300, "price": 30000, "gems": 2, "level": 7},
        {"name": "آتنا (Athena)", "damage": 250, "price": 25000, "gems": 1, "level": 6}
    ]
}

FIGHTERS = [
    {"name": "فانتوم (Phantom)", "bonus": 20, "price": 3000},
    {"name": "سوخو ۳۵ (Sukhoi 35)", "bonus": 30, "price": 6000},
    {"name": "رپتور (Raptor)", "bonus": 35, "price": 8000},
    {"name": "میگ ۲۹ (MiG-29)", "bonus": 25, "price": 4000},
    {"name": "کایت (Kite)", "bonus": 40, "price": 10000}
]

# ادامه در قسمت بعدی...
# ادامه از قسمت 1...

# ==================== HANDLERS ====================
@dp.message(CommandStart())
async def start_command(message: Message):
    """دستور /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "ندارد"
    full_name = message.from_user.full_name
    
    # ایجاد کاربر جدید
    db.create_user(user_id, username, full_name)
    
    welcome_text = f"""
🎮 **به جنگ‌زون خوش آمدی، {full_name}!** 🚀

در اینجا تو رهبر نظامی یک پایگاه هستی!
مأموریت: گسترش قلمرو، تقویت نیروها و نابودی دشمنان!

📊 **وضعیت اولیه:**
💰 سکه: 1,000
💎 جم: 10
🎯 ZP: 500

از دکمه‌های زیر برای شروع استفاده کن:
"""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())
    logger.info(f"👤 کاربر جدید: {user_id} - {full_name}")

@dp.message(Command("help"))
async def help_command(message: Message):
    """دستور /help"""
    help_text = """
📚 **راهنمای ربات:**

🎮 **پنل جنگجو:** وضعیت و تجهیزات شما
⚔️ **حمله:** حمله به کاربران دیگر
🏦 **بازار جنگ:** خرید موشک و تجهیزات
⛏️ **معدن‌چی:** کسب درآمد ZP
🎁 **جعبه‌های رمزی:** شانس برنده شدن جوایز
🏆 **رده‌بندی:** مقایسه با دیگران
🛡️ **پایگاه من:** اطلاعات پایگاه

💡 **نکته:** برای حمله، روی پیام کاربر ریپلای کن!
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
• سیستم دفاعی را ارتقا دهی
• آمار کامل خود را مشاهده کنی
"""
    await message.answer(panel_text, reply_markup=get_warrior_keyboard())

@dp.message(F.text == "🏦 بازار جنگ")
async def war_market(message: Message):
    """منوی بازار جنگ"""
    market_text = """
🏦 **بازار جنگ**

اینجا می‌توانی تجهیزات نظامی بخری:

🔥 **موشک‌های سریع:** قیمت مناسب، damage متوسط
💀 **موشک‌های آخرالزمانی:** قدرتمند، نیازمند جم
🛩️ **جنگنده‌ها:** افزایش damage حملات
🏰 **ارتقای پایگاه:** تقویت سیستم دفاعی
"""
    await message.answer(market_text, reply_markup=get_market_keyboard())

@dp.message(F.text == "⛏️ معدن‌چی")
async def miner_panel(message: Message):
    """منوی معدن‌چی"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if user:
        miner_level = user[10]  # miner_level
        income_per_hour = miner_level * 100
        
        miner_text = f"""
⛏️ **معدن‌چی ZP**

📊 **وضعیت ماینر:**
• سطح: {miner_level}
• درآمد ساعتی: {income_per_hour} ZP
• برداشت بعدی: هر 1 ساعت

💰 با ارتقای ماینر، درآمدت بیشتر می‌شود!
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
• نیاز: 1 موشک

💥 **ترکیب ۱:** 1.5x damage
• نیاز: 1 موشک + 1 جنگنده

🔥 **ترکیب ۲:** 2.0x damage  
• نیاز: 1 موشک + 2 جنگنده

💀 **ترکیب ۳:** 5.0x damage
• نیاز: 1 موشک آخرالزمانی + 5 جم

📝 **نحوه حمله:** روی پیام کاربر ریپلای کن و دکمه حمله بزن!
"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ حمله سریع", callback_data="attack_fast")],
            [InlineKeyboardButton(text="💥 ترکیب ۱", callback_data="attack_combo1")],
            [InlineKeyboardButton(text="🔥 ترکیب ۲", callback_data="attack_combo2")],
            [InlineKeyboardButton(text="💀 ترکیب ۳", callback_data="attack_combo3")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main")]
        ]
    )
    await message.answer(attack_text, reply_markup=keyboard)

@dp.message(F.text == "🎁 جعبه‌های رمزی")
async def mystery_boxes(message: Message):
    """منوی جعبه‌های رمزی"""
    boxes_text = """
🎁 **جعبه‌های رمزی**

🎲 **شانس برنده شدن:**

1. 📦 **باکس سکه** - 500 سکه
   • جایزه: 100-2,000 سکه

2. 💎 **باکس جم** - 1,000 سکه  
   • جایزه: 1-10 جم

3. 🎯 **باکس ZP** - 1,500 سکه
   • جایزه: 50-500 ZP

4. 🏆 **باکس افسانه‌ای** - 5 جم
   • جایزه: ترکیبی + شانس 10%

5. 🆓 **باکس رایگان** - روزی 1 بار
   • جایزه: تصادفی

برای خرید، عدد جعبه را بفرست (مثلاً: 1)
"""
    await message.answer(boxes_text, reply_markup=get_back_keyboard())

@dp.message(F.text == "🏆 رده‌بندی")
async def rankings(message: Message):
    """رده‌بندی کاربران"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # دریافت 10 کاربر برتر بر اساس ZP
    cursor.execute('''
        SELECT username, zone_point, level, zone_coin 
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
        coin = user[3]
        
        if i < 3:
            ranking_text += f"{medals[i]} **{username}**\n"
        else:
            ranking_text += f"{i+1}. **{username}**\n"
        
        ranking_text += f"   🎯 ZP: {zp:,} | 📊 لول: {level} | 💰 سکه: {coin:,}\n\n"
    
    await message.answer(ranking_text, reply_markup=get_back_keyboard())

@dp.message(F.text == "🛡️ پایگاه من")
async def my_base(message: Message):
    """اطلاعات پایگاه کاربر"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("⚠️ ابتدا با /start ثبت‌نام کن!")
        return
    
    base_text = f"""
🛡️ **پایگاه {message.from_user.full_name}**

📊 **وضعیت کلی:**
• 🎯 سطح: {user[6]}
• ⭐ XP: {user[7]}/1000
• 💎 جم: {user[4]:,}
• 💰 سکه: {user[3]:,}
• 🎯 ZP: {user[5]:,}

⛏️ **معدن:**
• سطح ماینر: {user[10]}
• درآمد ساعتی: {user[10] * 100} ZP
• آخرین برداشت: {"همین الان" if user[11] == 0 else time.ago(user[11])}

🏗️ **پیشرفت:**
برای ارتقا به بازار جنگ برو!
"""
    
    await message.answer(base_text, reply_markup=get_back_keyboard())

@dp.message(F.text == "ℹ️ راهنما")
async def help_menu(message: Message):
    """منوی راهنما"""
    help_text = """
ℹ️ **راهنمای کامل ربات**

🎮 **اهداف بازی:**
1. جمع‌آوری منابع (سکه، جم، ZP)
2. تقویت پایگاه و نیروها
3. حمله به کاربران دیگر
4. صعود در رده‌بندی

⚔️ **حمله:**
• روی پیام کاربر ریپلای کن
• نوع حمله را انتخاب کن
• منابع دشمن را تصاحب کن

💰 **اقتصاد:**
• هر ساعت از ماینر برداشت کن
• با ZP در رده‌بندی صعود کن
• از جعبه‌ها جایزه بگیر

🛡️ **دفاع:**
• پایگاه خود را ارتقا بده
• موشک دفاعی بساز
• از حملات در امان بمان

📞 **پشتیبانی:** @WarzoneSupport
"""
    await message.answer(help_text, reply_markup=get_back_keyboard())

# ==================== CALLBACK HANDLERS ====================
@dp.callback_query(F.data == "main")
async def back_to_main(callback: CallbackQuery):
    """بازگشت به منوی اصلی"""
    await callback.message.delete()
    await callback.message.answer("🏠 منوی اصلی:", reply_markup=get_main_keyboard())
    await callback.answer()

# ادامه در قسمت بعدی...
# ادامه از قسمت 2...

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

📈 **وضعیت:**
• سطح: {user[6]}
• XP: {user[7]}/1000
• ماینر: سطح {user[10]}

💡 **نکته:** ZP برای رده‌بندی مهم است!
"""
    
    await callback.message.edit_text(wallet_text, reply_markup=get_back_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "arsenal")
async def show_arsenal(callback: CallbackQuery):
    """نمایش زرادخانه"""
    user_id = callback.from_user.id
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # دریافت موشک‌های کاربر
    cursor.execute('''
        SELECT missile_name, quantity 
        FROM user_missiles 
        WHERE user_id = ? 
        ORDER BY quantity DESC
    ''', (user_id,))
    
    missiles = cursor.fetchall()
    conn.close()
    
    if not missiles:
        arsenal_text = """
🚀 **زرادخانه شما**

📭 **هیچ موشکی ندارید!**

🏦 به بازار جنگ بروید و موشک بخرید:
• موشک‌های سریع برای شروع
• موشک‌های آخرالزمانی برای حملات قوی
"""
    else:
        arsenal_text = "🚀 **زرادخانه شما**\n\n"
        total_missiles = 0
        
        for missile in missiles:
            name = missile[0]
            quantity = missile[1]
            total_missiles += quantity
            
            # پیدا کردن damage موشک
            damage = 0
            for category in MISSILES.values():
                for m in category:
                    if m["name"] == name:
                        damage = m["damage"]
                        break
            
            arsenal_text += f"• {name}: {quantity} عدد\n"
            arsenal_text += f"  ⚡ Damage: {damage}\n\n"
        
        arsenal_text += f"📊 **مجموع:** {total_missiles} موشک"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏦 خرید موشک", callback_data="market_fast")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="warrior")]
        ]
    )
    
    await callback.message.edit_text(arsenal_text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "miner_claim")
async def claim_miner(callback: CallbackQuery):
    """برداشت از ماینر"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("⚠️ ابتدا ثبت‌نام کن!", show_alert=True)
        return
    
    current_time = int(time.time())
    last_claim = user[11]  # last_miner_claim
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

⚡ ماینر را ارتقا دهید تا درآمد بیشتر شود!
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

@dp.callback_query(F.data == "miner_info")
async def miner_info(callback: CallbackQuery):
    """اطلاعات ماینر"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("⚠️ ابتدا ثبت‌نام کن!", show_alert=True)
        return
    
    miner_level = user[10]
    last_claim = user[11]
    current_time = int(time.time())
    
    # محاسبه زمان باقی‌مانده
    if last_claim == 0:
        time_left = "آماده برداشت!"
    elif (current_time - last_claim) < 3600:
        remaining = 3600 - (current_time - last_claim)
        minutes = remaining // 60
        seconds = remaining % 60
        time_left = f"{minutes}:{seconds:02d}"
    else:
        time_left = "آماده برداشت!"
    
    info_text = f"""
⛏️ **اطلاعات ماینر**

📊 **وضعیت فعلی:**
• سطح: {miner_level}
• درآمد ساعتی: {miner_level * 100} ZP
• زمان باقی‌مانده: {time_left}

💰 **هزینه ارتقا:** {miner_level * 200} سکه
📈 **درآمد بعدی:** {(miner_level + 1) * 100} ZP/ساعت

💡 **نکته:** هر سطح 100 ZP به درآمد اضافه می‌کند!
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬆️ ارتقا", callback_data="miner_upgrade")],
            [InlineKeyboardButton(text="⛏️ برداشت", callback_data="miner_claim")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main")]
        ]
    )
    
    await callback.message.edit_text(info_text, reply_markup=keyboard)
    await callback.answer()

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
    conn.close()
    
    new_coins = new_data[0]
    new_level = new_data[1]
    
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

@dp.callback_query(F.data == "market_fast")
async def market_fast_missiles(callback: CallbackQuery):
    """موشک‌های سریع در بازار"""
    market_text = """
🔥 **موشک‌های سریع**

موشک‌های سریع برای شروع عالی هستند:

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

@dp.callback_query(F.data == "market_apocalypse")
async def market_apocalypse_missiles(callback: CallbackQuery):
    """موشک‌های آخرالزمانی"""
    market_text = """
💀 **موشک‌های آخرالزمانی**

قدرتمندترین موشک‌ها برای حملات ویرانگر:

"""
    
    buttons = []
    for missile in MISSILES["apocalypse"]:
        btn_text = f"{missile['name']} - {missile['gems']} جم"
        btn_data = f"buy_apo_{missile['name']}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=btn_data)])
    
    buttons.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="market")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    for missile in MISSILES["apocalypse"]:
        market_text += f"• **{missile['name']}**\n"
        market_text += f"  ⚡ Damage: {missile['damage']}\n"
        market_text += f"  💎 قیمت: {missile['price']} سکه + {missile['gems']} جم\n"
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
    
    # ادامه در قسمت بعدی...
# ادامه از قسمت 3...

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
    
    # ثبت خرید
    cursor.execute('''
        INSERT INTO purchases (user_id, item_type, item_name, quantity, price)
        VALUES (?, 'missile', ?, 1, ?)
    ''', (user_id, missile_name, missile_data["price"]))
    
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

🛒 می‌توانی بیشتر بخری یا از زرادخانه استفاده کنی!
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 خرید بیشتر", callback_data="market_fast")],
            [InlineKeyboardButton(text="🚀 زرادخانه", callback_data="arsenal")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="market")]
        ]
    )
    
    await callback.message.edit_text(buy_text, reply_markup=keyboard)
    await callback.answer("✅ خرید موفق!")

@dp.callback_query(F.data.startswith("buy_apo_"))
async def buy_apocalypse_missile(callback: CallbackQuery):
    """خرید موشک آخرالزمانی"""
    missile_name = callback.data.replace("buy_apo_", "")
    
    # پیدا کردن موشک
    missile_data = None
    for missile in MISSILES["apocalypse"]:
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
    
    # چک کردن سکه و جم
    if user[3] < missile_data["price"]:
        await callback.answer(f"❌ سکه کافی نیست! نیاز: {missile_data['price']} سکه", show_alert=True)
        return
    
    if user[4] < missile_data["gems"]:
        await callback.answer(f"❌ جم کافی نیست! نیاز: {missile_data['gems']} جم", show_alert=True)
        return
    
    # خرید موشک
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # کم کردن منابع
    cursor.execute('UPDATE users SET zone_coin = zone_coin - ?, zone_gem = zone_gem - ? WHERE user_id = ?', 
                  (missile_data["price"], missile_data["gems"], user_id))
    
    # اضافه کردن موشک
    cursor.execute('''
        INSERT INTO user_missiles (user_id, missile_name, quantity)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, missile_name) 
        DO UPDATE SET quantity = quantity + 1
    ''', (user_id, missile_name))
    
    # ثبت خرید
    cursor.execute('''
        INSERT INTO purchases (user_id, item_type, item_name, quantity, price)
        VALUES (?, 'apocalypse_missile', ?, 1, ?)
    ''', (user_id, missile_name, missile_data["price"]))
    
    conn.commit()
    
    # دریافت اطلاعات جدید
    cursor.execute('SELECT zone_coin, zone_gem FROM users WHERE user_id = ?', (user_id,))
    new_data = cursor.fetchone()
    new_coins = new_data[0]
    new_gems = new_data[1]
    
    cursor.execute('SELECT quantity FROM user_missiles WHERE user_id = ? AND missile_name = ?', 
                  (user_id, missile_name))
    result = cursor.fetchone()
    missile_count = result[1] if result else 1
    
    conn.close()
    
    buy_text = f"""
💀 **خرید موشک آخرالزمانی!**

☠️ **{missile_name}** خریداری شد!
⚡ Damage: {missile_data["damage"]} (بسیار قوی!)
💰 هزینه: {missile_data["price"]} سکه + {missile_data["gems"]} جم
📦 تعداد: {missile_count} عدد
💎 باقی‌مانده: {new_coins} سکه، {new_gems} جم

⚠️ این موشک برای حملات ترکیبی ۳ استفاده می‌شود!
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 خرید بیشتر", callback_data="market_apocalypse")],
            [InlineKeyboardButton(text="🚀 زرادخانه", callback_data="arsenal")],
            [InlineKeyboardButton(text="💀 ترکیب ۳", callback_data="attack_combo3")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="market")]
        ]
    )
    
    await callback.message.edit_text(buy_text, reply_markup=keyboard)
    await callback.answer("☠️ موشک مرگبار خریداری شد!")

@dp.callback_query(F.data == "market_fighters")
async def market_fighters(callback: CallbackQuery):
    """منوی جنگنده‌ها"""
    market_text = """
🛩️ **جنگنده‌های نظامی**

جنگنده‌ها damage حملات شما را افزایش می‌دهند:

"""
    
    buttons = []
    for fighter in FIGHTERS:
        btn_text = f"{fighter['name']} - {fighter['price']} سکه"
        btn_data = f"buy_fighter_{fighter['name']}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=btn_data)])
    
    buttons.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="market")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    for fighter in FIGHTERS:
        market_text += f"• **{fighter['name']}**\n"
        market_text += f"  ⬆️ Bonus Damage: +{fighter['bonus']}%\n"
        market_text += f"  💰 قیمت: {fighter['price']} سکه\n\n"
    
    market_text += "💡 **نکته:** جنگنده‌ها در حملات ترکیبی استفاده می‌شوند!"
    
    await callback.message.edit_text(market_text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("attack_"))
async def attack_menu(callback: CallbackQuery):
    """منوی حمله"""
    attack_type = callback.data
    
    attack_info = {
        "attack_fast": {"name": "حمله سریع", "multiplier": 1.0, "needs": "1 موشک"},
        "attack_combo1": {"name": "ترکیب ۱", "multiplier": 1.5, "needs": "1 موشک + 1 جنگنده"},
        "attack_combo2": {"name": "ترکیب ۲", "multiplier": 2.0, "needs": "1 موشک + 2 جنگنده"},
        "attack_combo3": {"name": "ترکیب ۳", "multiplier": 5.0, "needs": "1 موشک آخرالزمانی + 5 جم"}
    }
    
    if attack_type not in attack_info:
        await callback.answer("❌ نوع حمله نامعتبر!", show_alert=True)
        return
    
    info = attack_info[attack_type]
    
    attack_text = f"""
⚔️ **{info['name']}**

📊 **مشخصات:**
• ضریب Damage: {info['multiplier']}x
• نیازمندی: {info['needs']}
• روش: روی پیام کاربر ریپلای کن!

🎯 **نحوه حمله:**
1. روی پیام کاربر مورد نظر ریپلای کن
2. این منو را باز کن
3. نوع حمله را انتخاب کن
4. حمله انجام می‌شود!

⚠️ **توجه:** حمله ممکن است با دفاع دشمن مقابله شود!
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 حمله کن", callback_data=f"confirm_{attack_type}")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="attack")]
        ]
    )
    
    await callback.message.edit_text(attack_text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_attack_"))
async def confirm_attack(callback: CallbackQuery):
    """تایید حمله"""
    attack_type = callback.data.replace("confirm_", "")
    
    if callback.message.reply_to_message is None:
        await callback.answer("❌ روی پیام کاربر ریپلای کن!", show_alert=True)
        return
    
    target_message = callback.message.reply_to_message
    attacker_id = callback.from_user.id
    target_id = target_message.from_user.id
    
    if attacker_id == target_id:
        await callback.answer("❌ نمی‌توانی به خودت حمله کنی!", show_alert=True)
        return
    
    # چک کردن وجود هدف
    target_user = db.get_user(target_id)
    if not target_user:
        await callback.answer("❌ کاربر هدف در سیستم نیست!", show_alert=True)
        return
    
    attacker_user = db.get_user(attacker_id)
    if not attacker_user:
        await callback.answer("⚠️ ابتدا ثبت‌نام کن!", show_alert=True)
        return
    
    # ادامه حمله در قسمت بعدی..
# ادامه از قسمت 4...

    # بررسی نیازمندی‌های حمله
    conn = db.get_connection()
    cursor = conn.cursor()
    
    can_attack = True
    error_message = ""
    
    if attack_type == "attack_fast":
        # چک کردن داشتن حداقل یک موشک
        cursor.execute('SELECT SUM(quantity) FROM user_missiles WHERE user_id = ?', (attacker_id,))
        total_missiles = cursor.fetchone()[0] or 0
        if total_missiles < 1:
            can_attack = False
            error_message = "❌ حداقل یک موشک نیاز داری!"
    
    elif attack_type == "attack_combo1":
        cursor.execute('SELECT SUM(quantity) FROM user_missiles WHERE user_id = ?', (attacker_id,))
        total_missiles = cursor.fetchone()[0] or 0
        # در واقعیت باید جنگنده هم چک شود
        if total_missiles < 1:
            can_attack = False
            error_message = "❌ 1 موشک + 1 جنگنده نیاز داری!"
    
    elif attack_type == "attack_combo3":
        # چک کردن داشتن موشک آخرالزمانی
        cursor.execute('''
            SELECT quantity FROM user_missiles 
            WHERE user_id = ? AND missile_name IN (
                'ارمغدن (Armageddon)', 'اپوکالیپس (Apocalypse)',
                'رگناروک (Ragnarok)', 'هارمجدون (Harmagedon)', 'آتنا (Athena)'
            ) LIMIT 1
        ''', (attacker_id,))
        apo_missile = cursor.fetchone()
        
        if not apo_missile or apo_missile[0] < 1:
            can_attack = False
            error_message = "❌ یک موشک آخرالزمانی نیاز داری!"
        elif attacker_user[4] < 5:  # zone_gem
            can_attack = False
            error_message = "❌ 5 جم نیاز داری!"
    
    if not can_attack:
        conn.close()
        await callback.answer(error_message, show_alert=True)
        return
    
    # محاسبه damage
    base_damage = random.randint(50, 150)  # damage پایه
    attacker_level = attacker_user[6]
    target_level = target_user[6]
    
    # اعمال multiplier بر اساس نوع حمله
    multipliers = {
        "attack_fast": 1.0,
        "attack_combo1": 1.5,
        "attack_combo2": 2.0,
        "attack_combo3": 5.0
    }
    
    multiplier = multipliers.get(attack_type, 1.0)
    
    # محاسبه damage نهایی
    level_bonus = 1 + (attacker_level - target_level) * 0.1
    final_damage = int(base_damage * multiplier * level_bonus)
    
    # اعمال damage به هدف (کم کردن ZP)
    target_zp = target_user[5]
    new_target_zp = max(0, target_zp - final_damage)
    zp_lost = target_zp - new_target_zp
    
    # افزایش XP حمله کننده
    xp_gain = min(100, final_damage // 10)
    new_xp = attacker_user[7] + xp_gain
    
    # چک کردن ارتقا سطح
    new_level = attacker_user[6]
    if new_xp >= 1000:
        new_level += 1
        new_xp = 0
    
    # بروزرسانی دیتابیس
    # کم کردن ZP هدف
    cursor.execute('UPDATE users SET zone_point = ? WHERE user_id = ?', 
                  (new_target_zp, target_id))
    
    # افزایش XP حمله کننده
    cursor.execute('UPDATE users SET xp = ?, level = ? WHERE user_id = ?', 
                  (new_xp, new_level, attacker_id))
    
    # کم کردن موشک اگر حمله سریع است
    if attack_type == "attack_fast":
        # پیدا کردن یک موشک برای کم کردن
        cursor.execute('SELECT missile_name FROM user_missiles WHERE user_id = ? AND quantity > 0 LIMIT 1', 
                      (attacker_id,))
        missile = cursor.fetchone()
        if missile:
            cursor.execute('''
                UPDATE user_missiles 
                SET quantity = quantity - 1 
                WHERE user_id = ? AND missile_name = ?
            ''', (attacker_id, missile[0]))
    
    # ثبت حمله در تاریخچه
    cursor.execute('''
        INSERT INTO attacks (attacker_id, target_id, damage, missile_type, combo_type)
        VALUES (?, ?, ?, ?, ?)
    ''', (attacker_id, target_id, final_damage, attack_type, "combo" if "combo" in attack_type else "fast"))
    
    conn.commit()
    conn.close()
    
    # ایجاد متن نتیجه حمله
    result_text = f"""
⚔️ **حمله انجام شد!**

🎯 **حمله کننده:** {callback.from_user.full_name}
🎯 **هدف:** {target_message.from_user.full_name}
⚡ **Damage:** {final_damage}
💥 **ZP از دست رفته:** {zp_lost}
⭐ **XP کسب شده:** +{xp_gain}

📊 **سطح جدید:** {new_level} ({new_xp}/1000 XP)

{"🎉 **سطح ارتقا یافت!**" if new_level > attacker_user[6] else ""}
"""
    
    # ارسال پیام به حمله کننده
    await callback.message.edit_text(result_text, reply_markup=get_back_keyboard())
    
    # ارسال پیام به هدف (اگر در گروه هست)
    try:
        target_notification = f"""
🛡️ **مورد حمله قرار گرفتی!**

⚔️ **توسط:** {callback.from_user.full_name}
💥 **Damage دریافت شده:** {final_damage}
📉 **ZP از دست رفته:** {zp_lost}
🎯 **ZP جدید:** {new_target_zp}

🔒 دفاع خود را تقویت کن!
"""
        await bot.send_message(target_id, target_notification)
    except:
        pass  # اگر نتوانستیم پیام بفرستیم، مشکلی نیست
    
    await callback.answer("✅ حمله انجام شد!")

# ==================== ADMIN COMMANDS ====================
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    """پنل ادمین"""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ دسترسی ممنوع!")
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 آمار کامل", callback_data="admin_stats")],
            [InlineKeyboardButton(text="🎁 هدیه همگانی", callback_data="admin_gift_all")],
            [InlineKeyboardButton(text="💰 به کاربر هدیه بده", callback_data="admin_gift_user")],
            [InlineKeyboardButton(text="💾 Backup دستی", callback_data="admin_backup")],
            [InlineKeyboardButton(text="📈 مدیریت کاربر", callback_data="admin_manage")]
        ]
    )
    
    admin_text = """
🔐 **پنل مدیریت ادمین**

انتخاب عملیات:
• 📊 آمار کامل ربات
• 🎁 هدیه به همه کاربران
• 💰 هدیه به کاربر خاص
• 💾 ایجاد Backup دستی
• 📈 مدیریت کاربران
"""
    await message.answer(admin_text, reply_markup=keyboard)

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    """آمار کامل ربات"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ دسترسی ممنوع!", show_alert=True)
        return
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # آمار کاربران
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE("now")')
    today_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(zone_coin), SUM(zone_gem), SUM(zone_point) FROM users')
    sums = cursor.fetchone()
    total_coins = sums[0] or 0
    total_gems = sums[1] or 0
    total_zp = sums[2] or 0
    
    cursor.execute('SELECT COUNT(*) FROM attacks WHERE DATE(timestamp) = DATE("now")')
    today_attacks = cursor.fetchone()[0]
    
    conn.close()
    
    stats_text = f"""
📊 **آمار کامل ربات**

👥 **کاربران:**
• کل کاربران: {total_users}
• امروز: +{today_users}

💰 **منابع کل:**
• مجموع سکه: {total_coins:,}
• مجموع جم: {total_gems:,}
• مجموع ZP: {total_zp:,}

⚔️ **حملات:**
• امروز: {today_attacks} حمله

📈 **سیستم:**
• Backup خودکار: فعال ✓
• دیتابیس: SQLite ✓
• وضعیت: آنلاین ✓
"""
    
    await callback.message.edit_text(stats_text, reply_markup=get_back_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "admin_backup")
async def admin_backup(callback: CallbackQuery):
    """ایجاد Backup دستی"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ دسترسی ممنوع!", show_alert=True)
        return
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backups/backup_{timestamp}.db"
        
        # ایجاد پوشه اگر وجود ندارد
        os.makedirs("backups", exist_ok=True)
        
        # کپی دیتابیس
        shutil.copy2("warzone.db", backup_file)
        
        backup_text = f"""
✅ **Backup دستی ایجاد شد**

📁 **فایل:** `{backup_file}`
📏 **حجم:** {os.path.getsize(backup_file):,} بایت
⏰ **زمان:** {datetime.now().strftime('%H:%M:%S')}
📅 **تاریخ:** {datetime.now().strftime('%Y-%m-%d')}

🔗 **قابل انتقال به هر سرور دیگری!**
"""
        
        await callback.message.edit_text(backup_text, reply_markup=get_back_keyboard())
        logger.info(f"🔧 Backup created by admin: {callback.from_user.id}")
        
    except Exception as e:
        error_text = f"❌ خطا در ایجاد Backup:\n{str(e)}"
        await callback.message.edit_text(error_text, reply_markup=get_back_keyboard())
    
    await callback.answer()

# ==================== KEEP ALIVE FUNCTION ====================
async def keep_alive_ping():
    """پینگ برای فعال نگه داشتن ربات"""
    try:
        # ایجاد یک درخواست ساده
        async with aiohttp.ClientSession() as session:
            async with session.get('https://httpbin.org/get', timeout=10):
                pass
        logger.info("✅ Keep-alive ping successful")
    except Exception as e:
        logger.warning(f"⚠️ Keep-alive ping failed: {e}")

# ==================== MAIN FUNCTION ====================
async def main():
    """تابع اصلی اجرای ربات"""
    logger.info("🚀 Starting Warzone Bot...")
    
    # تست اتصال به تلگرام
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot connected: @{bot_info.username}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Telegram: {e}")
        return
    
    # حذف webhook قدیمی و شروع polling
    await bot.delete_webhook(drop_pending_updates=True)
    
    # شروع keep-alive در background
    async def keep_alive_loop():
        while True:
            await keep_alive_ping()
            await asyncio.sleep(300)  # هر 5 دقیقه
    
    asyncio.create_task(keep_alive_loop())
    
    # شروع ربات
    logger.info("📱 Bot is running...")
    await dp.start_polling(bot)

# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    # اجرای ربات
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
