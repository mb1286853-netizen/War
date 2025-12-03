import os
import asyncio
import sqlite3
import random
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
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

DB_PATH = '/app/data/warzone.db'
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# ==================== داده‌های بازی ====================

MISSILES = {
    "موشک ۱ تنی": {"damage": 50, "price": 200, "min_level": 1},
    "موشک ۵ تنی": {"damage": 70, "price": 500, "min_level": 2},
    "موشک ۱۰ تنی": {"damage": 90, "price": 1000, "min_level": 3},
    "موشک ۲۰ تنی": {"damage": 110, "price": 2000, "min_level": 4},
    "موشک ۵۰ تنی": {"damage": 130, "price": 5000, "min_level": 5},
}

FIGHTERS = {
    "F-16 Falcon": {"bonus": 80, "price": 5000, "min_level": 3},
    "F-22 Raptor": {"bonus": 150, "price": 12000, "min_level": 6},
    "Su-57 Felon": {"bonus": 220, "price": 25000, "min_level": 9},
    "B-2 Spirit": {"bonus": 300, "price": 50000, "min_level": 12},
}

DRONES = {
    "MQ-9 Reaper": {"bonus": 100, "price": 8000, "min_level": 4},
    "RQ-4 Global Hawk": {"bonus": 180, "price": 18000, "min_level": 7},
    "X-47B": {"bonus": 250, "price": 35000, "min_level": 10},
    "Avenger": {"bonus": 350, "price": 60000, "min_level": 13},
}

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

# ==================== کیبوردها ====================

def user_keyboard():
    """کیبورد کاربران عادی"""
    keyboard = [
        [KeyboardButton(text="👤 پروفایل")],
        [KeyboardButton(text="🛒 فروشگاه"), KeyboardButton(text="💥 حمله")],
        [KeyboardButton(text="⛏️ ماینر ZP"), KeyboardButton(text="🎁 باکس")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def admin_keyboard():
    """کیبورد ادمین"""
    keyboard = [
        [KeyboardButton(text="👑 پنل ادمین"), KeyboardButton(text="📊 آمار کامل")],
        [KeyboardButton(text="📣 پیام همگانی"), KeyboardButton(text="🎁 هدیه همگانی")],
        [KeyboardButton(text="💰 +سکه"), KeyboardButton(text="💎 +جم")],
        [KeyboardButton(text="🪙 +ZP"), KeyboardButton(text="🆙 تغییر لول")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def shop_keyboard():
    """کیبورد فروشگاه"""
    keyboard = [
        [KeyboardButton(text="💣 موشک‌ها"), KeyboardButton(text="🚁 جنگنده‌ها")],
        [KeyboardButton(text="🛸 پهپادها"), KeyboardButton(text="🛡️ پدافند")],
        [KeyboardButton(text="🎁 باکس‌ها"), KeyboardButton(text="🔙 بازگشت")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def back_keyboard():
    """کیبورد بازگشت"""
    keyboard = [[KeyboardButton(text="🔙 بازگشت")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# ==================== دیتابیس ====================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            is_admin BOOLEAN DEFAULT 0,
            miner_level INTEGER DEFAULT 1,
            last_miner_claim TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول موشک‌های کاربر
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_missiles (
            user_id INTEGER,
            missile_name TEXT,
            quantity INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, missile_name)
        )
    ''')
    
    # جدول آمار ربات
    c.execute('''
        CREATE TABLE IF NOT EXISTS bot_stats (
            total_users INTEGER DEFAULT 0,
            total_coins BIGINT DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('INSERT OR IGNORE INTO bot_stats (total_users, total_coins) VALUES (0, 0)')
    
    conn.commit()
    conn.close()
    print("✅ دیتابیس راه‌اندازی شد")

def get_user(user_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return dict(user) if user else None

def create_user(user_id: int, username: str, full_name: str):
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
        
        # آپدیت آمار
        c.execute('UPDATE bot_stats SET total_users = total_users + 1')
        
        conn.commit()
        print(f"✅ کاربر جدید: {user_id}")
    
    conn.close()

def is_admin(user_id: int) -> bool:
    user = get_user(user_id)
    return user and (user['is_admin'] == 1 or user_id in ADMIN_IDS)

# ==================== دستورات اصلی ====================

@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name
    
    init_db()
    create_user(user_id, username, full_name)
    
    welcome_text = (
        "🚀 **به WarZone خوش آمدید!**\n\n"
        "🪐 ربات بازی جنگی پیشرفته\n"
        "✅ همیشه آنلاین 24/7\n"
        "✅ سیستم کامل بازی\n\n"
        "👇 از کیبورد زیر استفاده کنید:"
    )
    
    if is_admin(user_id):
        await message.answer(welcome_text, reply_markup=admin_keyboard())
    else:
        await message.answer(welcome_text, reply_markup=user_keyboard())

@dp.message(F.text == "👤 پروفایل")
async def profile_handler(message: types.Message):
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
        f"⛏️ **ماینر:** سطح {user['miner_level']}\n"
        f"📅 **عضویت:** {user['created_at'][:10]}"
    )
    
    await message.answer(profile_text)

@dp.message(F.text == "🛒 فروشگاه")
async def shop_handler(message: types.Message):
    shop_text = (
        "🛒 **فروشگاه WarZone**\n\n"
        "**دسته‌بندی محصولات:**\n"
        "• 💣 موشک‌ها (آسیب مستقیم)\n"
        "• 🚁 جنگنده‌ها (تقویت حمله)\n"
        "• 🛸 پهپادها (پشتیبانی)\n"
        "• 🛡️ پدافند (سیستم دفاعی)\n"
        "• 🎁 باکس‌ها (شانسی)\n\n"
        "👇 دسته مورد نظر را انتخاب کنید:"
    )
    
    await message.answer(shop_text, reply_markup=shop_keyboard())

@dp.message(F.text == "💣 موشک‌ها")
async def missiles_handler(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    text = "💣 **موشک‌ها**\n\n"
    
    for name, info in MISSILES.items():
        if user['level'] >= info['min_level']:
            text += f"• **{name}**\n"
            text += f"  ⚔️ آسیب: {info['damage']}\n"
            text += f"  💰 قیمت: {info['price']:,} سکه\n"
            text += f"  🆙 نیاز به سطح: {info['min_level']}\n\n"
    
    await message.answer(text, reply_markup=back_keyboard())

@dp.message(F.text == "🚁 جنگنده‌ها")
async def fighters_handler(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    text = "🚁 **جنگنده‌ها**\n\n"
    
    for name, info in FIGHTERS.items():
        if user['level'] >= info['min_level']:
            text += f"• **{name}**\n"
            text += f"  ✨ تقویت: +{info['bonus']} آسیب\n"
            text += f"  💰 قیمت: {info['price']:,} سکه\n"
            text += f"  🆙 نیاز به سطح: {info['min_level']}\n\n"
    
    await message.answer(text, reply_markup=back_keyboard())

@dp.message(F.text == "🛸 پهپادها")
async def drones_handler(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    text = "🛸 **پهپادها**\n\n"
    
    for name, info in DRONES.items():
        if user['level'] >= info['min_level']:
            text += f"• **{name}**\n"
            text += f"  ✨ تقویت: +{info['bonus']} آسیب\n"
            text += f"  💰 قیمت: {info['price']:,} سکه\n"
            text += f"  🆙 نیاز به سطح: {info['min_level']}\n\n"
    
    await message.answer(text, reply_markup=back_keyboard())

@dp.message(F.text == "⛏️ ماینر ZP")
async def miner_handler(message: types.Message):
    user = get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ کاربر یافت نشد!")
        return
    
    miner_level = user['miner_level']
    miner_info = MINER_LEVELS[miner_level]
    last_claim = user['last_miner_claim']
    
    # محاسبه ZP انباشته
    accumulated_zp = 0
    if last_claim:
        try:
            last_claim_time = datetime.fromisoformat(last_claim)
            now = datetime.now()
            hours_passed = (now - last_claim_time).total_seconds() / 3600
            accumulated_zp = min(hours_passed * miner_info["zp_per_hour"], miner_info["zp_per_hour"] * 24)
        except:
            pass
    
    text = (
        f"⛏️ **ماینر ZP**\n\n"
        f"🔄 **سطح:** {miner_level} ({miner_info['name']})\n"
        f"📊 **تولید:** {miner_info['zp_per_hour']:,} ZP/ساعت\n"
        f"💳 **موجودی ZP:** {user['zone_point']:,}\n"
        f"📈 **انباشته:** {int(accumulated_zp):,} ZP\n"
    )
    
    if miner_level < 15:
        upgrade_cost = miner_info['upgrade_cost']
        text += f"\n💰 **ارتقا به سطح {miner_level + 1}:** {upgrade_cost:,} ZP"
    
    await message.answer(text, reply_markup=back_keyboard())

@dp.message(F.text == "🎁 باکس")
async def boxes_handler(message: types.Message):
    text = (
        "🎁 **باکس‌های شانسی**\n\n"
        "**انواع باکس:**\n"
        "• 🟢 باکس سکه (500 سکه)\n"
        "• 🔵 باکس ZP (1000 ZP)\n"
        "• 🟡 باکس ویژه (10 جم)\n"
        "• 🔴 باکس افسانه‌ای (50 جم)\n\n"
        "👇 برای خرید دستور زیر را وارد کنید:\n"
        "`/buybox [نوع باکس]`\n\n"
        "مثال: `/buybox coin`"
    )
    
    await message.answer(text, reply_markup=back_keyboard())

@dp.message(F.text == "💥 حمله")
async def attack_handler(message: types.Message):
    text = (
        "💥 **سیستم حمله**\n\n"
        "**انواع حمله:**\n"
        "• ⚔️ حمله تکی (یک موشک)\n"
        "• 🧩 حمله ترکیبی ۱ (۲ موشک + ۱ جنگنده + ۱ پهپاد)\n"
        "• 🧩 حمله ترکیبی ۲ (۳ موشک + ۲ جنگنده)\n"
        "• 🧩 حمله ترکیبی ۳ (۴ موشک + ۱ جنگنده + ۲ پهپاد)\n\n"
        "👇 برای حمله دستور زیر را وارد کنید:\n"
        "`/attack [نوع] [هدف]`\n\n"
        "مثال: `/attack single 123456789`"
    )
    
    await message.answer(text, reply_markup=back_keyboard())

# ==================== پنل ادمین ====================

@dp.message(F.text == "👑 پنل ادمین")
async def admin_panel_handler(message: types.Message):
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
        "• `/addcoin 123456789 50000`\n"
        "• `/addgem 123456789 50`\n"
        "• `/addzp 123456789 1000`\n"
        "• `/setlevel 123456789 10`\n"
        "• `/giftall 1000 5 100`\n"
        "• `/broadcast متن پیام`\n\n"
        "👇 از دکمه‌های زیر استفاده کنید"
    )
    
    await message.answer(admin_text, reply_markup=admin_keyboard())

@dp.message(F.text == "📊 آمار کامل")
async def full_stats_handler(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ شما ادمین نیستید!")
        return
    
    conn = get_connection()
    c = conn.cursor()
    
    # آمار کاربران
    c.execute('SELECT COUNT(*) as total, SUM(zone_coin) as total_coins FROM users')
    stats = c.fetchone()
    
    # کاربران امروز
    c.execute('SELECT COUNT(*) FROM users WHERE date(created_at) = date("now")')
    new_today = c.fetchone()[0]
    
    conn.close()
    
    stats_text = (
        "📊 **آمار کامل ربات**\n\n"
        f"👥 **کل کاربران:** {stats['total']}\n"
        f"🆕 **کاربران امروز:** {new_today}\n"
        f"💰 **کل سکه‌ها:** {stats['total_coins']:,}\n"
        f"🕐 **زمان سرور:** {datetime.now().strftime('%H:%M')}\n"
        f"✅ **وضعیت:** آنلاین"
    )
    
    await message.answer(stats_text)

@dp.message(F.text == "📣 پیام همگانی")
async def broadcast_button(message: types.Message):
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

@dp.message(F.text == "💰 +سکه")
async def addcoin_button(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "💰 **افزودن سکه**\n\n"
        "فرمت:\n"
        "`/addcoin آیدی_کاربر مقدار`\n\n"
        "مثال:\n"
        "`/addcoin 123456789 50000`"
    )

@dp.message(F.text == "💎 +جم")
async def addgem_button(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "💎 **افزودن جم**\n\n"
        "فرمت:\n"
        "`/addgem آیدی_کاربر مقدار`\n\n"
        "مثال:\n"
        "`/addgem 123456789 50`"
    )

@dp.message(F.text == "🪙 +ZP")
async def addzp_button(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "🪙 **افزودن ZP**\n\n"
        "فرمت:\n"
        "`/addzp آیدی_کاربر مقدار`\n\n"
        "مثال:\n"
        "`/addzp 123456789 1000`"
    )

@dp.message(F.text == "🆙 تغییر لول")
async def setlevel_button(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "🆙 **تغییر سطح کاربر**\n\n"
        "فرمت:\n"
        "`/setlevel آیدی_کاربر سطح`\n\n"
        "مثال:\n"
        "`/setlevel 123456789 10`"
    )

@dp.message(F.text == "🔙 بازگشت")
async def back_handler(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("🔙 به پنل ادمین بازگشتید.", reply_markup=admin_keyboard())
    else:
        await message.answer("🔙 به منوی اصلی بازگشتید.", reply_markup=user_keyboard())

# ==================== دستورات ادمین ====================

@dp.message(Command("addcoin"))
async def addcoin_command(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await message.answer("⚠️ فرمت: `/addcoin آیدی مقدار`")
        return
    
    try:
        user_id = int(args[0])
        amount = int(args[1])
        
        conn = get_connection()
        c = conn.cursor()
        c.execute('UPDATE users SET zone_coin = zone_coin + ? WHERE user_id = ?', (amount, user_id))
        
        # آپدیت آمار
        c.execute('UPDATE bot_stats SET total_coins = total_coins + ?', (amount,))
        
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ {amount:,} سکه به کاربر {user_id} اضافه شد.")
        
        # اطلاع به کاربر
        try:
            await bot.send_message(
                user_id,
                f"🎉 **هدیه از ادمین!**\n\n"
                f"💰 **{amount:,} سکه** دریافت کردید!"
            )
        except:
            pass
            
    except:
        await message.answer("❌ خطا! فرمت درست: `/addcoin 123456789 50000`")

@dp.message(Command("addgem"))
async def addgem_command(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await message.answer("⚠️ فرمت: `/addgem آیدی مقدار`")
        return
    
    try:
        user_id = int(args[0])
        amount = int(args[1])
        
        conn = get_connection()
        c = conn.cursor()
        c.execute('UPDATE users SET zone_gem = zone_gem + ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ {amount} جم به کاربر {user_id} اضافه شد.")
        
        try:
            await bot.send_message(
                user_id,
                f"💎 **هدیه از ادمین!**\n\n"
                f"✨ **{amount} جم** دریافت کردید!"
            )
        except:
            pass
            
    except:
        await message.answer("❌ خطا! فرمت درست: `/addgem 123456789 50`")

@dp.message(Command("addzp"))
async def addzp_command(message: types.Message, command: CommandObject):
    if not is_admin(me
