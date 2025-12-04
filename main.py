"""
🏆 ربات Warzone - نسخه نهایی
با سیستم Backup روزانه قابل انتقال
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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import aiohttp
import schedule

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
import pytz

# ==================== CONFIG ====================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
PORT = int(os.getenv("PORT", 8080))
KEEP_ALIVE_URL = os.getenv("KEEP_ALIVE_URL", "")

# زمان ایران
IRAN_TZ = pytz.timezone('Asia/Tehran')

# ==================== DATABASE SETUP ====================
class Database:
    def __init__(self):
        self.db_path = "warzone.db"
        self.backup_dir = "backups"
        self.setup_database()
        self.setup_backup_system()
    
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
                last_miner_claim INTEGER,
                cyber_tower_level INTEGER DEFAULT 0,
                defense_missile_level INTEGER DEFAULT 0,
                defense_electronic_level INTEGER DEFAULT 0,
                defense_antifighter_level INTEGER DEFAULT 0,
                total_defense_bonus REAL DEFAULT 0.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_backup_date DATE DEFAULT CURRENT_DATE
            )
        ''')
        
        # جدول موشک‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_missiles (
                user_id INTEGER,
                missile_name TEXT,
                quantity INTEGER DEFAULT 0,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, missile_name),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
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
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (attacker_id) REFERENCES users(user_id),
                FOREIGN KEY (target_id) REFERENCES users(user_id)
            )
        ''')
        
        # جدول لاگ Backup
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backup_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_date DATE,
                backup_file TEXT,
                file_size INTEGER,
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logging.info("✅ دیتابیس راه‌اندازی شد")
    
    def setup_backup_system(self):
        """ایجاد سیستم Backup خودکار"""
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs("data/backups", exist_ok=True)
        
        # زمان‌بندی Backup روزانه (ساعت 2 شب به وقت ایران)
        def daily_backup():
            self.create_backup()
        
        schedule.every().day.at("02:00").do(daily_backup)
        
        # اجرای scheduler در ترد جداگانه
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)
        
        thread = threading.Thread(target=run_scheduler, daemon=True)
        thread.start()
        logging.info("✅ سیستم Backup روزانه راه‌اندازی شد")
    
    def create_backup(self):
        """ایجاد Backup از دیتابیس"""
        try:
            timestamp = datetime.now(IRAN_TZ).strftime("%Y-%m-%d_%H%M%S")
            backup_file = f"{self.backup_dir}/warzone_{timestamp}.db"
            backup_file2 = f"data/backups/warzone_{timestamp}.db"
            
            # کپی دیتابیس
            shutil.copy2(self.db_path, backup_file)
            shutil.copy2(self.db_path, backup_file2)
            
            # ثبت در لاگ
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            file_size = os.path.getsize(backup_file)
            
            cursor.execute('''
                INSERT INTO backup_logs (backup_date, backup_file, file_size, status)
                VALUES (DATE('now'), ?, ?, 'success')
            ''', (backup_file, file_size))
            
            conn.commit()
            conn.close()
            
            # نگه داشتن فقط 7 Backup اخیر
            self.clean_old_backups()
            
            logging.info(f"✅ Backup ایجاد شد: {backup_file}")
            return backup_file
            
        except Exception as e:
            logging.error(f"❌ خطا در Backup: {e}")
            return None
    
    def clean_old_backups(self, keep_last=7):
        """حذف Backup های قدیمی"""
        try:
            backup_files = sorted(
                [f for f in os.listdir(self.backup_dir) if f.endswith('.db')],
                key=lambda x: os.path.getctime(os.path.join(self.backup_dir, x))
            )
            
            if len(backup_files) > keep_last:
                for old_file in backup_files[:-keep_last]:
                    os.remove(os.path.join(self.backup_dir, old_file))
                    logging.info(f"🗑️ Backup قدیمی حذف شد: {old_file}")
                    
        except Exception as e:
            logging.error(f"❌ خطا در پاک‌سازی Backup: {e}")
    
    def get_connection(self):
        """ایجاد اتصال به دیتابیس"""
        return sqlite3.connect(self.db_path)
    
    def restore_backup(self, backup_file: str):
        """بازیابی دیتابیس از Backup"""
        try:
            shutil.copy2(backup_file, self.db_path)
            logging.info(f"✅ دیتابیس بازیابی شد از: {backup_file}")
            return True
        except Exception as e:
            logging.error(f"❌ خطا در بازیابی: {e}")
            return False
    
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

# ==================== BOT SETUP ====================
bot = Bot(token=TOKEN)
dp = Dispatcher()
db = Database()

# ==================== MISSILE DATA ====================
MISSILES = {
    "fast": [
        {"name": "شهاب (Meteor)", "persian": "شهاب", "damage": 50, "price": 200, "level": 1, "type": "fast"},
        {"name": "تگرگ (Hailstorm)", "persian": "تگرگ", "damage": 70, "price": 500, "level": 2, "type": "fast"},
        {"name": "سیل (Torrent)", "persian": "سیل", "damage": 90, "price": 1000, "level": 3, "type": "fast"},
        {"name": "توفان (Tempest)", "persian": "توفان", "damage": 110, "price": 2000, "level": 4, "type": "fast"},
        {"name": "آذرخش (Thunderbolt)", "persian": "آذرخش", "damage": 130, "price": 5000, "level": 5, "type": "fast"}
    ],
    "apocalypse": [
        {"name": "ارمغدن (Armageddon)", "persian": "ارمغدن", "damage": 500, "price": 50000, "gems": 5, "level": 10, "type": "apocalypse"},
        {"name": "اپوکالیپس (Apocalypse)", "persian": "اپوکالیپس", "damage": 400, "price": 40000, "gems": 4, "level": 9, "type": "apocalypse"},
        {"name": "رگناروک (Ragnarok)", "persian": "رگناروک", "damage": 350, "price": 35000, "gems": 3, "level": 8, "type": "apocalypse"},
        {"name": "هارمجدون (Harmagedon)", "persian": "هارمجدون", "damage": 300, "price": 30000, "gems": 2, "level": 7, "type": "apocalypse"},
        {"name": "آتنا (Athena)", "persian": "آتنا", "damage": 250, "price": 25000, "gems": 1, "level": 6, "type": "apocalypse"}
    ]
}

FIGHTERS = {
    "fighters": [
        {"name": "فانتوم (Phantom)", "persian": "فانتوم", "damage_bonus": 20, "price": 3000, "type": "fighter"},
        {"name": "سوخو ۳۵ (Sukhoi 35)", "persian": "سوخو ۳۵", "damage_bonus": 30, "price": 6000, "type": "fighter"},
        {"name": "رپتور (Raptor)", "persian": "رپتور", "damage_bonus": 35, "price": 8000, "type": "fighter"},
        {"name": "میگ ۲۹ (MiG-29)", "persian": "میگ ۲۹", "damage_bonus": 25, "price": 4000, "type": "fighter"},
        {"name": "کایت (Kite)", "persian": "کایت", "damage_bonus": 40, "price": 1000, "type": "fighter"}
            ]
}

# ==================== KEYBOARDS ====================
def get_main_keyboard():
    """کیبورد اصلی"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 پنل جنگجو"), KeyboardButton(text="⚔️ حمله")],
            [KeyboardButton(text="🏦 بازار جنگ"), KeyboardButton(text="⛏️ معدن‌چی")],
            [KeyboardButton(text="🎁 جعبه‌های رمزی"), KeyboardButton(text="🏆 رده‌بندی")],
            [KeyboardButton(text="🛡️ پایگاه من"), KeyboardButton(text="ℹ️ راهنما")]
        ],
        resize_keyboard=True,
        input_field_placeholder="دستور مورد نظر را انتخاب کن..."
    )
    return keyboard

def get_warrior_panel_keyboard():
    """پنل جنگجو"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 کیف پول", callback_data="wallet")],
            [InlineKeyboardButton(text="🚀 زرادخانه", callback_data="arsenal")],
            [InlineKeyboardButton(text="🛡️ دفاع", callback_data="defense")],
            [InlineKeyboardButton(text="📊 آمار من", callback_data="mystats")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main_menu")]
        ]
    )

def get_market_keyboard():
    """بازار جنگ"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 موشک‌های سریع", callback_data="market_fast")],
            [InlineKeyboardButton(text="💀 موشک‌های آخرالزمانی", callback_data="market_apocalypse")],
            [InlineKeyboardButton(text="🛩️ جنگنده‌ها", callback_data="market_fighters")],
            [InlineKeyboardButton(text="🏰 ارتقای پایگاه", callback_data="market_base")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main_menu")]
        ]
    )

def get_miner_keyboard():
    """معدن‌چی"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⛏️ برداشت ZP", callback_data="miner_claim")],
            [InlineKeyboardButton(text="⬆️ ارتقای ماینر", callback_data="miner_upgrade")],
            [InlineKeyboardButton(text="📈 اطلاعات ماینر", callback_data="miner_info")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main_menu")]
        ]
    )

def get_attack_keyboard():
    """حمله"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ حمله سریع", callback_data="attack_fast")],
            [InlineKeyboardButton(text="💥 حمله ترکیبی ۱", callback_data="attack_combo1")],
            [InlineKeyboardButton(text="🔥 حمله ترکیبی ۲", callback_data="attack_combo2")],
            [InlineKeyboardButton(text="💀 حمله ترکیبی ۳", callback_data="attack_combo3")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main_menu")]
        ]
    )

def get_back_keyboard():
    """دکمه بازگشت"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="main_menu")]
        ]
    )

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
💰 سکه: 1000
💎 جم: 10
🎯 ZP: 500

دکمه‌های زیر را برای شروع استفاده کن:
"""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

@dp.message(F.text == "🎮 پنل جنگجو")
async def warrior_panel(message: Message):
    """پنل جنگجو"""
    text = """
🎮 **پنل جنگجو**

در این بخش می‌تونی:
• موجودی منابعت رو ببینی
• زرادخانه موشک‌هات رو چک کنی
• سیستم دفاعی رو مدیریت کنی
• آمار کاملت رو مشاهده کنی
"""
    await message.answer(text, reply_markup=get_warrior_panel_keyboard())

@dp.message(F.text == "🏦 بازار جنگ")
async def war_market(message: Message):
    """بازار جنگ"""
    text = """
🏦 **بازار جنگ**

اینجا می‌تونی تجهیزات نظامی بخری:
• موشک‌های سریع و قدرتمند
• جنگنده‌های پیشرفته
• سیستم‌های دفاعی
• ارتقای پایگاه
"""
    await message.answer(text, reply_markup=get_market_keyboard())

@dp.message(F.text == "⛏️ معدن‌چی")
async def miner_panel(message: Message):
    """معدن‌چی"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if user:
        miner_level = user[10]  # miner_level
        
        text = f"""
⛏️ **معدن‌چی ZP**

سطح ماینر شما: **{miner_level}**
درآمد ساعتی: **{miner_level * 100} ZP**

دکمه «برداشت ZP» را هر 1 ساعت بزن!
"""
    else:
        text = "⚠️ ابتدا با دستور /start ثبت‌نام کن!"
    
    await message.answer(text, reply_markup=get_miner_keyboard())

@dp.message(F.text == "⚔️ حمله")
async def attack_panel(message: Message):
    """پنل حمله"""
    text = """
⚔️ **سیستم حمله**

انتخاب نوع حمله:

⚡ **حمله سریع:** با یک موشک
💥 **ترکیب ۱:** 1.5x damage (موشک + جنگنده)
🔥 **ترکیب ۲:** 2.0x damage (موشک + جنگنده + پهپاد)
💀 **ترکیب ۳:** 5.0x damage (موشک هسته‌ای + جم)

📝 **روش حمله:** روی پیام کاربر ریپلای کن و این منو رو باز کن!
"""
    await message.answer(text, reply_markup=get_attack_keyboard())

@dp.message(F.text == "🎁 جعبه‌های رمزی")
async def mystery_boxes(message: Message):
    """جعبه‌های رمزی"""
    text = """
🎁 **جعبه‌های رمزی**

1. 📦 باکس سکه - 500 سکه
   جایزه: 100-2000 سکه

2. 💎 باکس جم - 1000 سکه  
   جایزه: 1-10 جم

3. 🎯 باکس ZP - 1500 سکه
   جایزه: 50-500 ZP

4. 🏆 باکس افسانه‌ای - 5 جم
   جایزه: ترکیبی + شانس 10%

5. 🆓 باکس رایگان - 1 بار در روز
   جایزه: 10-100 (تصادفی)

⚡ برای خرید، عدد جعبه را بفرست (مثلاً: 1)
"""
    await message.answer(text, reply_markup=get_back_keyboard())

@dp.message(F.text == "🏆 رده‌بندی")
async def rankings(message: Message):
    """رده‌بندی"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # دریافت 10 کاربر برتر
    cursor.execute('''
        SELECT username, zone_point, level 
        FROM users 
        ORDER BY zone_point DESC 
        LIMIT 10
    ''')
    
    top_users = cursor.fetchall()
    conn.close()
    
    text = "🏆 **رده‌بندی برترین‌ها**\n\n"
    
    for i, user in enumerate(top_users, 1):
        username = user[0] or "ناشناس"
        zp = user[1]
        level = user[2]
        text += f"{i}. **{username}**\n   ZP: {zp} | لول: {level}\n"
    
    if not top_users:
        text += "هنوز کاربری در سیستم نیست!"
    
    await message.answer(text, reply_markup=get_back_keyboard())

@dp.message(F.text == "🛡️ پایگاه من")
async def my_base(message: Message):
    """پایگاه من"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if user:
        text = f"""
🛡️ **پایگاه {message.from_user.full_name}**

📊 **وضعیت کلی:**
• سطح: {user[6]}
• XP: {user[7]}/1000
• ZP: {user[5]}

⚔️ **سیستم دفاعی:**
• برج سایبری: سطح {user[11]}
• موشک دفاعی: سطح {user[12]}
• جنگ‌الکترونیک: سطح {user[13]}
• ضدجنگنده: سطح {user[14]}
• بونوس دفاع: +{user[15]}%

⛏️ **معدن:**
• سطح ماینر: {user[10]}
• درآمد ساعتی: {user[10] * 100} ZP
"""
    else:
        text = "⚠️ ابتدا با دستور /start ثبت‌نام کن!"
    
    await message.answer(text, reply_markup=get_back_keyboard())
@dp.message(F.text == "ℹ️ راهنما")
async def help_menu(message: Message):
    """راهنما"""
    text = """
ℹ️ **راهنمای کامل Warzone**

🎮 **پنل جنگجو:** مشاهده وضعیت و تجهیزات
⚔️ **حمله:** حمله به دیگر کاربران (با ریپلای)
🏦 **بازار:** خرید موشک و جنگنده
⛏️ **معدن‌چی:** کسب درآمد ZP
🎁 **جعبه‌ها:** شانس برای جایزه
🏆 **رده‌بندی:** مقایسه با دیگران
🛡️ **پایگاه:** مدیریت دفاع و ارتقا

💡 **نکات مهم:**
1. هر 1 ساعت از ماینر برداشت کن
2. با ZP بیشتر، در رده‌بندی بالاتر برو
3. دفاعت را قوی کن تا کمتر آسیب ببینی
4. از حملات ترکیبی استفاده کن

📞 **پشتیبانی:** @WarzoneSupport
"""
    await message.answer(text, reply_markup=get_back_keyboard())
    await message.answer(text, reply_markup=get_back_keyboard())

# ==================== CALLBACK HANDLERS ====================
@dp.callback_query(F.data == "wallet")
async def wallet_callback(callback: CallbackQuery):
    """کیف پول"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if user:
        text = f"""
💰 **کیف پول شما**

🪙 **سکه:** {user[3]:,}
💎 **جم:** {user[4]:,}
🎯 **ZP:** {user[5]:,}

💡 ZP برای رده‌بندی و ارتقا مهمه!
"""
    else:
        text = "⚠️ اطلاعات یافت نشد!"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "miner_claim")
async def miner_claim(callback: CallbackQuery):
    """برداشت از ماینر"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("⚠️ ابتدا ثبت‌نام کن!", show_alert=True)
        return
    
    current_time = int(time.time())
    last_claim = user[11]  # last_miner_claim
    
    if last_claim and (current_time - last_claim) < 3600:
        remaining = 3600 - (current_time - last_claim)
        minutes = remaining // 60
        await callback.answer(f"⏳ {minutes} دقیقه دیگر مجاز به برداشت!", show_alert=True)
        return
    
    # محاسبه درآمد
    miner_level = user[10]  # miner_level
    income = miner_level * 100
    
    # بروزرسانی دیتابیس
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users 
        SET zone_point = zone_point + ?, last_miner_claim = ? 
        WHERE user_id = ?
    ''', (income, current_time, user_id))
    
    conn.commit()
    conn.close()
    
    text = f"""
⛏️ **برداشت موفق!**

✅ **درآمد شما:** +{income} ZP
📊 **کل ZP شما:** {user[5] + income:,}
⏰ **برداشت بعدی:** 1 ساعت دیگر

ماینرت رو ارتقا بده تا درآمدت بیشتر شه!
"""
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer("✅ برداشت شد!")

@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    """بازگشت به منو اصلی"""
    await callback.message.edit_text("🔰 منوی اصلی", reply_markup=None)
    await callback.message.answer("منوی اصلی:", reply_markup=get_main_keyboard())
    await callback.answer()

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
            [InlineKeyboardButton(text="💾 Backup دستی", callback_data="admin_backup")],
            [InlineKeyboardButton(text="📈 مدیریت کاربر", callback_data="admin_manage")],
            [InlineKeyboardButton(text="🔄 راه‌اندازی مجدد", callback_data="admin_restart")]
        ]
    )
    
    text = """
🔐 **پنل مدیریت ادمین**

انتخاب عملیات:
"""
    await message.answer(text, reply_markup=keyboard)

@dp.callback_query(F.data == "admin_backup")
async def admin_backup_callback(callback: CallbackQuery):
    """ایجاد Backup دستی"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ دسترسی ممنوع!", show_alert=True)
        return
    
    backup_file = db.create_backup()
    
    if backup_file:
        text = f"""
✅ **Backup دستی ایجاد شد**

📁 فایل: `{backup_file}`
📏 حجم: {os.path.getsize(backup_file):,} بایت
⏰ زمان: {datetime.now(IRAN_TZ).strftime('%H:%M:%S')}

🔗 این فایل قابل انتقال به هر سرور دیگری است!
"""
    else:
        text = "❌ خطا در ایجاد Backup!"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()

# ==================== KEEP ALIVE ====================
async def keep_alive():
    """ارسال درخواست Keep-Alive"""
    if KEEP_ALIVE_URL:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(KEEP_ALIVE_URL) as response:
                    logging.info(f"✅ Keep-Alive sent: {response.status}")
        except Exception as e:
            logging.error(f"❌ Keep-Alive error: {e}")

# ==================== MAIN ====================
async def main():
    """تابع اصلی"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    logging.info("🚀 شروع ربات Warzone...")
    
    # شروع Keep-Alive
    async def keep_alive_loop():
        while True:
            await keep_alive()
            await asyncio.sleep(300)  # هر 5 دقیقه
    
    asyncio.create_task(keep_alive_loop())
    
    # حذف webhook و شروع polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
