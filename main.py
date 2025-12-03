"""
WarZone Bot - ربات کامل بازی جنگی
نسخه کامل با همه قابلیت‌های درخواستی
"""

import os
import asyncio
import sqlite3
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode
from aiohttp import web
from dotenv import load_dotenv

# ==================== تنظیمات ====================
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x]
PORT = int(os.getenv('PORT', 8080))

if not BOT_TOKEN:
    print("❌ خطا: BOT_TOKEN تنظیم نشده!")
    exit(1)

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ==================== داده‌های بازی ====================

# 💣 موشک‌های کلاسیک (غیرپولی)
MISSILES_CLASSIC = {
    "موشک ۱ تنی": {"damage": 50, "price": 200, "min_level": 1},
    "موشک ۵ تنی": {"damage": 70, "price": 500, "min_level": 2},
    "موشک ۱۰ تنی": {"damage": 90, "price": 1000, "min_level": 3},
    "موشک ۲۰ تنی": {"damage": 110, "price": 2000, "min_level": 4},
    "موشک ۵۰ تنی": {"damage": 130, "price": 5000, "min_level": 5},
}

# 💣 موشک‌های آخرالزمانی
MISSILES_APOCALYPSE = {
    "موشک ۱۰۰ تنی": {"damage": 200, "price": 10000, "min_level": 6},
    "موشک ۲۰۰ تنی": {"damage": 280, "price": 20000, "min_level": 7},
    "موشک ۵۰۰ تنی": {"damage": 350, "price": 35000, "min_level": 8},
    "موشک ۱۰۰۰ تنی": {"damage": 400, "price": 50000, "min_level": 9},
}

# 🚁 جنگنده‌ها
FIGHTERS = {
    "F-16 Falcon": {"bonus": 80, "price": 5000, "min_level": 3},
    "F-22 Raptor": {"bonus": 150, "price": 12000, "min_level": 6},
    "Su-57 Felon": {"bonus": 220, "price": 25000, "min_level": 9},
    "B-2 Spirit": {"bonus": 300, "price": 50000, "min_level": 12},
}

# 🛸 پهپادها
DRONES = {
    "MQ-9 Reaper": {"bonus": 100, "price": 8000, "min_level": 4},
    "RQ-4 Global Hawk": {"bonus": 180, "price": 18000, "min_level": 7},
    "X-47B": {"bonus": 250, "price": 35000, "min_level": 10},
    "Avenger": {"bonus": 350, "price": 60000, "min_level": 13},
}

# 🛡️ پدافندها
DEFENSES = {
    "پدافند موشکی": {"bonus": 0.15, "price": 3000, "upgrade_cost": 1500},
    "پدافند الکترونیک": {"bonus": 0.10, "price": 2000, "upgrade_cost": 1000},
    "پدافند ضد جنگنده": {"bonus": 0.12, "price": 2500, "upgrade_cost": 1200},
    "پدافند سایبری": {"bonus": 0.20, "price": 5000, "upgrade_cost": 2500},
}

# ⛏️ ماینر ZP
MINER_LEVELS = {
    1: {"zp_per_hour": 100, "upgrade_cost": 100, "name": "ماینر پایه"},
    2: {"zp_per_hour": 200, "upgrade_cost": 200, "name": "ماینر متوسط"},
    3: {"zp_per_hour": 300, "upgrade_cost": 300, "name": "ماینر پیشرفته"},
    4: {"zp_per_hour": 400, "upgrade_cost": 400, "name": "ماینر حرفه‌ای"},
    5: {"zp_per_hour": 500, "upgrade_cost": 500, "name": "ماینر فوق‌حرفه‌ای"},
    6: {"zp_per_hour": 600, "upgrade_cost": 600, "name": "ماینر صنعتی"},
    7: {"zp_per_hour": 700, "upgrade_cost": 700, "name": "ماینر فوق‌صنعتی"},
    8: {"zp_per_hour": 800, "upgrade_cost": 800, "name": "ماینر فضایی"},
    9: {"zp_per_hour": 900, "upgrade_cost": 900, "name": "ماینر کوانتومی"},
    10: {"zp_per_hour": 1000, "upgrade_cost": 10000, "name": "ماینر ستاره‌ای"},
    11: {"zp_per_hour": 1100, "upgrade_cost": 11000, "name": "ماینر افسانه‌ای"},
    12: {"zp_per_hour": 1200, "upgrade_cost": 12000, "name": "ماینر کهکشانی"},
    13: {"zp_per_hour": 1300, "upgrade_cost": 13000, "name": "ماینر کیهانی"},
    14: {"zp_per_hour": 1400, "upgrade_cost": 14000, "name": "ماینر مطلق"},
    15: {"zp_per_hour": 1500, "upgrade_cost": 0, "name": "ماینر خداگونه"},
}

# 🎁 باکس‌ها
BOXES = {
    "zona_box": {"name": "باکس زونا", "price": 1000, "reward_type": "zp", "min": 50, "max": 500},
    "coin_box": {"name": "باکس سکه", "price": 500, "reward_type": "coin", "min": 100, "max": 2000},
    "premium_box": {"name": "باکس ویژه", "price_gem": 10, "reward_type": "gem", "min": 1, "max": 50},
    "legendary_box": {"name": "باکس افسانه‌ای", "price_gem": 50, "reward_type": "all", "chance": 0.05},
}

# 🎯 ترکیب‌های حمله
COMBOS = {
    1: {"missiles": 2, "fighters": 1, "drones": 1, "damage_bonus": 1.5},
    2: {"missiles": 3, "fighters": 2, "drones": 0, "damage_bonus": 2.0},
    3: {"missiles": 4, "fighters": 1, "drones": 2, "damage_bonus": 2.5},
}

# ==================== کیبوردها ====================

def user_keyboard():
    """کیبورد کاربران عادی"""
    keyboard = [
        [KeyboardButton(text="👤 پروفایل"), KeyboardButton(text="🛒 فروشگاه")],
        [KeyboardButton(text="⛏️ ماینر ZP"), KeyboardButton(text="💥 حمله")],
        [KeyboardButton(text="🎁 باکس‌ها"), KeyboardButton(text="📊 آمار ربات")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def admin_keyboard():
    """کیبورد ادمین"""
    keyboard = [
        [KeyboardButton(text="👑 پنل ادمین")],
        [KeyboardButton(text="📣 پیام همگانی"), KeyboardButton(text="🎁 هدیه همگانی")],
        [KeyboardButton(text="➕ افزودن سکه"), KeyboardButton(text="💎 افزودن جم")],
        [KeyboardButton(text="➕ افزودن ZP"), KeyboardButton(text="🆙 تغییر لول")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def shop_keyboard():
    """کیبورد فروشگاه"""
    keyboard = [
        [KeyboardButton(text="💣 موشک‌ها")],
        [KeyboardButton(text="🚁 جنگنده‌ها"), KeyboardButton(text="🛸 پهپادها")],
        [KeyboardButton(text="🛡️ پدافند"), KeyboardButton(text="🎁 باکس‌ها")],
        [KeyboardButton(text="🔙 بازگشت")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def attack_keyboard():
    """کیبورد حمله"""
    keyboard = [
        [KeyboardButton(text="⚔️ حمله تکی")],
        [KeyboardButton(text="🧩 حمله ترکیبی ۱"), KeyboardButton(text="🧩 حمله ترکیبی ۲")],
        [KeyboardButton(text="🧩 حمله ترکیبی ۳"), KeyboardButton(text="🔙 بازگشت")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# ==================== دیتابیس ====================

DB_PATH = '/app/data/warzone.db'

def get_connection():
    """اتصال به دیتابیس"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """راه‌اندازی اولیه دیتابیس"""
    conn = get_connection()
    c = conn.cursor()
    
    # جدول کاربران
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            zone_coin INTEGER DEFAULT 1000,
            zone_gem INTEGER DEFAULT 10,
            zone_point INTEGER DEFAULT 500,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            power INTEGER DEFAULT 100,
            is_admin BOOLEAN DEFAULT 0,
            miner_level INTEGER DEFAULT 1,
            last_miner_claim TIMESTAMP,
            total_damage INTEGER DEFAULT 0,
            attacks_won INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول موشک‌ها
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_missiles (
            user_id INTEGER,
            missile_name TEXT,
            quantity INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, missile_name)
        )
    ''')
    
    # جدول جنگنده‌ها
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_fighters (
            user_id INTEGER,
            fighter_name TEXT,
            quantity INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, fighter_name)
        )
    ''')
    
    # جدول پهپادها
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_drones (
            user_id INTEGER,
            drone_name TEXT,
            quantity INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, drone_name)
        )
    ''')
    
    # جدول پدافندها
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_defenses (
            user_id INTEGER,
            defense_name TEXT,
            level INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, defense_name)
        )
    ''')
    
    # جدول باکس‌ها
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_boxes (
            user_id INTEGER,
            box_type TEXT,
            quantity INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, box_type)
        )
    ''')
    
    # جدول آمار
    c.execute('''
        CREATE TABLE IF NOT EXISTS bot_stats (
            total_users INTEGER DEFAULT 0,
            total_coins BIGINT DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # درج رکورد اولیه آمار
    c.execute('INSERT OR IGNORE INTO bot_stats (total_users, total_coins) VALUES (0, 0)')
    
    conn.commit()
    conn.close()
    print("✅ دیتابیس راه‌اندازی شد")

def get_user(user_id: int):
    """دریافت اطلاعات کاربر"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return dict(user) if user else None

def create_user(user_id: int, username: str, full_name: str):
    """ایجاد کاربر جدید"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
    exists = c.fetchone()
    
    if not exists:
        is_admin = 1 if user_id in ADMIN_IDS else 0
        coins = 999999999 if is_admin else 1000
        gems = 999999999 if is_admin else 10
        
        c.execute('''
            INSERT INTO users (user_id, username, full_name, zone_coin, zone_gem, is_admin)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, full_name, coins, gems, is_admin))
        
        # موشک‌های اولیه
        for missile in ["موشک ۱ تنی"]:
            c.execute('''
                INSERT OR REPLACE INTO user_missiles (user_id, missile_name, quantity)
                VALUES (?, ?, ?)
            ''', (user_id, missile, 5))
        
        # آپدیت آمار
        c.execute('UPDATE bot_stats SET total_users = total_users + 1')
        
        conn.commit()
        print(f"✅ کاربر جدید: {user_id}")
    
    conn.close()

def update_user_coins(user_id: int, amount: int):
    """به‌روزرسانی سکه کاربر"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET zone_coin = zone_coin + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def update_user_gems(user_id: int, amount: int):
    """به‌روزرسانی جم کاربر"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET zone_gem = zone_gem + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def update_user_zp(user_id: int, amount: int):
    """به‌روزرسانی ZP کاربر"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET zone_point = zone_point + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

# ==================== توابع کمکی ====================

def is_admin(user_id: int) -> bool:
    """چک کردن ادمین بودن"""
    user = get_user(user_id)
    return user and (user['is_admin'] == 1 or user_id in ADMIN_IDS)

def calculate_zp_accumulated(user_id: int, miner_level: int, last_claim_time: str) -> int:
    """محاسبه ZP انباشته شده در ماینر"""
    if not last_claim_time:
        return 0
    
    miner_info = MINER_LEVELS.get(miner_level, MINER_LEVELS[1])
    zp_per_hour = miner_info["zp_per_hour"]
    
    last_claim = datetime.fromisoformat(last_claim_time)
    now = datetime.now()
    hours_passed = (now - last_claim).total_seconds() / 3600
    
    accumulated = hours_passed * zp_per_hour
    max_capacity = zp_per_hour * 24  # حداکثر 24 ساعت ذخیره
    
    return int(min(accumulated, max_capacity))

# ==================== دستورات اصلی ====================

@dp.message(Command("start"))
async def start_command(message: types.Message):
    """دستور شروع ربات"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name
    
    init_db()
    create_user(user_id, username, full_name)
    
    welcome_text = (
        "🚀 **به WarZone خوش آمدید!**\n\n"
        "🪐 ربات بازی جنگی پیشرفته\n"
        "✅ همیشه آنلاین 24/7\n\n"
        "📋 **امکانات:**\n"
        "• سیستم حمله تکی و ترکیبی\n"
        "• ماینر ZP خودکار\n"
        "• فروشگاه کامل تجهیزات\n"
        "• باکس‌های مختلف\n"
        "• پنل ادمین پیشرفته\n\n"
        "👇 از کیبورد زیر استفاده کنید:"
    )
    
    if is_admin(user_id):
        await message.answer(welcome_text, reply_markup=admin_keyboard())
    else:
        await message.answer(welcome_text, reply_markup=user_keyboard())

@dp.message(F.text == "👤 پروفایل")
async def profile_handler(message: types.Message):
    """نمایش پروفایل"""
    user = get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ کاربر یافت نشد! /start بزنید")
        return
    
    admin_badge = "👑 " if user['is_admin'] == 1 else ""
    coins = "∞" if user['is_admin'] == 1 else f"{user['zone_coin']:,}"
    gems = "∞" if user['is_admin'] == 1 else f"{user['zone_gem']}"
    
    profile_text = (
        f"{admin_badge}**پروفایل کاربری**\n\n"
        f"👤 **نام:** {user['full_name']}\n"
        f"🆔 **آیدی:** `{user['user_id']}`\n"
        f"💰 **سکه:** {coins}\n"
        f"💎 **جم:** {gems}\n"
        f"🪙 **ZP:** {user['zone_point']:,}\n"
        f"⭐ **XP:** {user['xp']:,}\n"
        f"🆙 **سطح:** {user['level']}\n"
        f"💪 **قدرت:** {user['power']:,}\n"
        f"⛏️ **ماینر:** سطح {user['miner_level']}\n"
        f"📅 **عضویت:** {user['created_at'][:10]}"
    )
    
    await message.answer(profile_text)

@dp.message(F.text == "⛏️ ماینر ZP")
async def miner_handler(message: types.Message):
    """مدیریت ماینر"""
    user = get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ کاربر یافت نشد!")
        return
    
    miner_level = user['miner_level']
    miner_info = MINER_LEVELS[miner_level]
    last_claim = user['last_miner_claim']
    
    accumulated_zp = calculate_zp_accumulated(
        message.from_user.id,
        miner_level,
        last_claim
    )
    
    text = (
        f"⛏️ **ماینر ZP**\n\n"
        f"🔄 **سطح:** {miner_level} ({miner_info['name']})\n"
        f"📊 **تولید:** {miner_info['zp_per_hour']:,} ZP/ساعت\n"
        f"💳 **موجودی ZP:** {user['zone_point']:,}\n"
        f"📈 **انباشته:** {accumulated_zp:,} ZP\n"
    )
    
    if miner_level < 15:
        upgrade_cost = miner_info['upgrade_cost']
        text += f"\n💰 **ارتقا به سطح {miner_level + 1}:** {upgrade_cost:,} ZP"
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"💰 برداشت ({accumulated_zp:,} ZP)")],
            [KeyboardButton(text=f"⬆️ ارتقا ماینر")] if miner_level < 15 else [],
            [KeyboardButton(text="🔙 بازگشت")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(text, reply_markup=keyboard)

@dp.message(F.text.contains("برداشت"))
async def miner_claim_handler(message: types.Message):
    """برداشت ZP از ماینر"""
    user = get_user(message.from_user.id)
    if not user:
        return
    
    miner_level = user['miner_level']
    last_claim = user['last_miner_claim']
    
    accumulated_zp = calculate_zp_accumulated(
        message.from_user.id,
        miner_level,
        last_claim
    )
    
    if accumulated_zp < 100:
        await message.answer("❌ حداقل 100 ZP برای برداشت نیاز است!")
        return
    
    # بروزرسانی
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        'UPDATE users SET zone_point = zone_point + ?, last_miner_claim = ? WHERE user_id = ?',
        (accumulated_zp, datetime.now().isoformat(), message.from_user.id)
    )
    conn.commit()
    conn.close()
    
    await message.answer(
        f"✅ **{accumulated_zp:,} ZP** برداشت شد!\n"
        f"💰 موجودی جدید: {user['zone_point'] + accumulated_zp:,} ZP"
    )

@dp.message(F.text.contains("ارتقا ماینر"))
async def miner_upgrade_handler(message: types.Message):
    """ارتقای ماینر"""
    user = get_user(message.from_user.id)
    if not user:
        return
    
    miner_level = user['miner_level']
    if miner_level >= 15:
        await message.answer("🎉 ماینر شما در حداکثر سطح است!")
        return
    
    miner_info = MINER_LEVELS[miner_level]
    upgrade_cost = miner_info['upgrade_cost']
    
    if user['zone_point'] < upgrade_cost:
        await message.answer(
            f"❌ موجودی ZP کافی نیست!\n"
            f"💰 نیاز: {upgrade_cost:,} ZP\n"
            f"💳 موجودی: {user['zone_point']:,} ZP"
        )
        return
    
    # ارتقا
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        'UPDATE users SET zone_point = zone_point - ?, miner_level = miner_level + 1 WHERE user_id = ?',
        (upgrade_cost, message.from_user.id)
    )
    conn.commit()
    conn.close()
    
    new_level = miner_level + 1
    new_info = MINER_LEVELS[new_level]
    
    await message.answer(
        f"✅ **ماینر ارتقا یافت!**\n\n"
        f"🆙 **سطح جدید:** {new_level}\n"
        f"📊 **تولید جدید:** {new_info['zp_per_hour']:,} ZP/ساعت\n"
        f"💰 **هزینه پرداخت شده:** {upgrade_cost:,} ZP\n"
        f"🎮 **XP دریافت شده:** 50"
    )

# ==================== پنل ادمین ====================

@dp.message(F.text == "👑 پنل ادمین")
async def admin_panel_handler(message: types.Message):
    """پنل ادمین"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ شما ادمین نیستید!")
        return
    
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT total_users, total_coins FROM bot_stats')
    stats = c.fetchone()
    conn.close()
    
    admin_text = (
        "👑 **پنل ادمین WarZone**\n\n"
        f"👥 **کل کاربران:** {stats['total_users']}\n"
        f"💰 **کل سکه‌ها:** {stats['total_coins']:,}\n"
        f"🕐 **زمان:** {datetime.now().strftime('%H:%M')}\n\n"
        "**دستورات سریع:**\n"
        "• `/addcoin آیدی مقدار`\n"
        "• `/addgem آیدی مقدار`\n"
        "• `/addzp آیدی مقدار`\n"
        "• `/setlevel آیدی سطح`\n"
        "• `/giftall سکه جم zp`\n"
        "• `/broadcast متن`\n\n"
        "👇 از دکمه‌های زیر استفاده کنید"
    )
    
    await message.answer(admin_text, reply_markup=admin_keyboard())

@dp.message(F.text == "📣 پیام همگانی")
async def broadcast_button(message: types.Message):
    """دکمه پیام همگانی"""
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "📣 **پیام همگانی**\n\n"
        "برای ارسال پیام به همه کاربران:\n"
        "`/broadcast متن پیام`\n\n"
        "مثال:\n"
        "`/broadcast سلام کاربران عزیز!`"
    )

@dp.message(F.text == "🎁 هدیه همگانی")
async def giftall_button(message: types.Message):
    """دکمه هدیه همگانی"""
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "🎁 **هدیه همگانی**\n\n"
        "برای دادن هدیه به همه:\n"
        "`/giftall سکه جم zp`\n\n"
        "مثال:\n"
        "`/giftall 1000 5 100`\n"
        "این دستور 1000 سکه، 5 جم و 100 ZP به همه می‌دهد."
    )

@dp.message(F.text == "➕ افزودن سکه")
async def addcoin_button(message: types.Message):
    """دکمه افزودن سکه"""
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "💰 **افزودن سکه**\n\n"
        "فرمت:\n"
        "`/addcoin آیدی مقدار`\n\n"
        "مثال:\n"
        "`/addcoin 123456789 50000`\n"
        "این دستور 50,000 سکه اضافه می‌کند."
    )

@dp.message(F.text == "💎 افزودن جم")
async def addgem_button(message: types.Message):
    """دکمه افزودن جم"""
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "💎 **افزودن جم**\n\n"
        "فرمت:\n"
        "`/addgem آیدی مقدار`\n\n"
        "مثال:\n"
        "`/addgem 123456789 50`\n"
        "این دستور 50 جم اضافه می‌کند."
    )

@dp.message(F.text == "➕ افزودن ZP")
async def addzp_button(message: types.Message):
