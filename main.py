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
from aiogram.client.default import DefaultBotProperties  # <-- اضافه کن
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

# ✅ اصلاح خطا: استفاده از DefaultBotProperties
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
    keyboard = [
        [KeyboardButton(text="👤 پروفایل"), KeyboardButton(text="🛒 فروشگاه")],
        [KeyboardButton(text="⛏️ ماینر ZP"), KeyboardButton(text="💥 حمله")],
        [KeyboardButton(text="🎁 باکس"), KeyboardButton(text="📊 آمار")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def admin_keyboard():
    keyboard = [
        [KeyboardButton(text="👑 پنل ادمین")],
        [KeyboardButton(text="📣 پیام همه"), KeyboardButton(text="🎁 هدیه همه")],
        [KeyboardButton(text="💰 +سکه"), KeyboardButton(text="💎 +جم")],
        [KeyboardButton(text="🪙 +ZP"), KeyboardButton(text="🆙 تغییر لول")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# ==================== دیتابیس ====================

DB_PATH = '/app/data/warzone.db'

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
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
        
        conn.commit()
        print(f"✅ کاربر جدید: {user_id}")
    
    conn.close()

def update_user_coins(user_id: int, amount: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET zone_coin = zone_coin + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def update_user_gems(user_id: int, amount: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET zone_gem = zone_gem + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def update_user_zp(user_id: int, amount: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET zone_point = zone_point + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
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
    
    if is_admin(user_id):
        await message.answer("👑 به پنل ادمین خوش آمدید!", reply_markup=admin_keyboard())
    else:
        await message.answer("🚀 به WarZone خوش آمدید!", reply_markup=user_keyboard())

@dp.message(F.text == "👤 پروفایل")
async def profile_handler(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ کاربر یافت نشد!")
        return
    
    admin_badge = "👑 " if user['is_admin'] == 1 else ""
    coins = "∞" if user['is_admin'] == 1 else f"{user['zone_coin']:,}"
    gems = "∞" if user['is_admin'] == 1 else f"{user['zone_gem']}"
    
    text = (
        f"{admin_badge}**پروفایل**\n\n"
        f"💰 سکه: {coins}\n"
        f"💎 جم: {gems}\n"
        f"🪙 ZP: {user['zone_point']:,}\n"
        f"🆙 سطح: {user['level']}\n"
        f"⭐ XP: {user['xp']:,}\n"
        f"⛏️ ماینر: سطح {user['miner_level']}"
    )
    await message.answer(text)

@dp.message(F.text == "⛏️ ماینر ZP")
async def miner_handler(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    miner_level = user['miner_level']
    miner_info = MINER_LEVELS[miner_level]
    
    text = (
        f"⛏️ **ماینر سطح {miner_level}**\n\n"
        f"📊 تولید: {miner_info['zp_per_hour']:,} ZP/ساعت\n"
        f"💳 موجودی: {user['zone_point']:,} ZP\n"
        f"💰 ارتقا: {miner_info['upgrade_cost']:,} ZP"
    )
    
    await message.answer(text)

@dp.message(F.text == "👑 پنل ادمین")
async def admin_panel_handler(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ شما ادمین نیستید!")
        return
    
    await message.answer(
        "👑 **پنل ادمین**\n\n"
        "دستورات:\n"
        "• /addcoin آیدی مقدار\n"
        "• /addgem آیدی مقدار\n"
        "• /addzp آیدی مقدار\n"
        "• /setlevel آیدی سطح\n"
        "• /giftall سکه جم zp\n"
        "• /broadcast متن",
        reply_markup=admin_keyboard()
    )

# ==================== دستورات ادمین ====================

@dp.message(Command("addcoin"))
async def addcoin_command(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await message.answer("⚠️ فرمت: /addcoin آیدی مقدار")
        return
    
    try:
        user_id = int(args[0])
        amount = int(args[1])
        
        update_user_coins(user_id, amount)
        await message.answer(f"✅ {amount:,} سکه به کاربر {user_id} اضافه شد.")
        
    except:
        await message.answer("❌ خطا!")

@dp.message(Command("addgem"))
async def addgem_command(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await message.answer("⚠️ فرمت: /addgem آیدی مقدار")
        return
    
    try:
        user_id = int(args[0])
        amount = int(args[1])
        
        update_user_gems(user_id, amount)
        await message.answer(f"✅ {amount} جم به کاربر {user_id} اضافه شد.")
        
    except:
        await message.answer("❌ خطا!")

@dp.message(Command("addzp"))
async def addzp_command(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await message.answer("⚠️ فرمت: /addzp آیدی مقدار")
        return
    
    try:
        user_id = int(args[0])
        amount = int(args[1])
        
        update_user_zp(user_id, amount)
        await message.answer(f"✅ {amount:,} ZP به کاربر {user_id} اضافه شد.")
        
    except:
        await message.answer("❌ خطا!")

@dp.message(Command("setlevel"))
async def setlevel_command(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await message.answer("⚠️ فرمت: /setlevel آیدی سطح")
        return
    
    try:
        user_id = int(args[0])
        level = int(args[1])
        
        conn = get_connection()
        c = conn.cursor()
        c.execute('UPDATE users SET level = ? WHERE user_id = ?', (level, user_id))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ سطح کاربر {user_id} به {level} تغییر یافت.")
        
    except:
        await message.answer("❌ خطا!")

@dp.message(Command("giftall"))
async def giftall_command(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) < 1:
        await message.answer("⚠️ فرمت: /giftall سکه [جم] [zp]")
        return
    
    try:
        coins = int(args[0])
        gems = int(args[1]) if len(args) > 1 else 0
        zp = int(args[2]) if len(args) > 2 else 0
        
        conn = get_connection()
        c = conn.cursor()
        c.execute('UPDATE users SET zone_coin = zone_coin + ?, zone_gem = zone_gem + ?, zone_point = zone_point + ?',
                 (coins, gems, zp))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ هدیه به همه ارسال شد!")
        
    except:
        await message.answer("❌ خطا!")

@dp.message(Command("broadcast"))
async def broadcast_command(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    
    if not command.args:
        await message.answer("⚠️ فرمت: /broadcast متن")
        return
    
    await message.answer(f"📣 پیام ارسال شد:\n{command.args}")

# ==================== وب سرور ====================

async def health_handler(request):
    return web.Response(text='Bot is running!')

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"🌐 Web server started on port {PORT}")
    return runner

async def main():
    print("🚀 Starting WarZone Bot...")
    web_runner = await start_web_server()
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await web_runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())
