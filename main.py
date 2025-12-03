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

# ✅ تعریف DB_PATH قبل از استفاده
DB_PATH = '/app/data/warzone.db'
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ✅ ساخت bot با روش جدید
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

def get_connection():
    """اتصال به دیتابیس"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """راه‌اندازی دیتابیس"""
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

def is_admin(user_id: int) -> bool:
    """چک کردن ادمین بودن"""
    user = get_user(user_id)
    return user and (user['is_admin'] == 1 or user_id in ADMIN_IDS)

# ==================== توابع ماینر ====================

def calculate_zp_accumulated(user_id: int, miner_level: int, last_claim_time: str) -> int:
    """محاسبه ZP انباشته شده"""
    if not last_claim_time:
        return 0
    
    miner_info = MINER_LEVELS.get(miner_level, MINER_LEVELS[1])
    zp_per_hour = miner_info["zp_per_hour"]
    
    try:
        last_claim = datetime.fromisoformat(last_claim_time)
    except:
        return 0
    
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
    
    welcome_text = "🚀 **به WarZone خوش آمدید!**\n\n🪐 ربات بازی جنگی پیشرفته"
    
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
    
    await message.answer(text)

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

@dp.message(F.text == "👑 پنل ادمین")
async def admin_panel_handler(message: types.Message):
    """پنل ادمین"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ شما ادمین نیستید!")
        return
    
    admin_text = (
        "👑 **پنل ادمین WarZone**\n\n"
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

# ==================== دستورات ادمین ====================

@dp.message(Command("addcoin"))
async def addcoin_command(message: types.Message, command: CommandObject):
    """اضافه کردن سکه"""
    if not is_admin(message.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await message.answer("⚠️ فرمت: `/addcoin آیدی مقدار`")
        return
    
    try:
        user_id = int(args[0])
        amount = int(args[1])
        
        update_user_coins(user_id, amount)
        await message.answer(f"✅ {amount:,} سکه به کاربر {user_id} اضافه شد.")
        
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
    """اضافه کردن جم"""
    if not is_admin(message.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await message.answer("⚠️ فرمت: `/addgem آیدی مقدار`")
        return
    
    try:
        user_id = int(args[0])
        amount = int(args[1])
        
        update_user_gems(user_id, amount)
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
    """اضافه کردن ZP"""
    if not is_admin(message.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await message.answer("⚠️ فرمت: `/addzp آیدی مقدار`")
        return
    
    try:
        user_id = int(args[0])
        amount = int(args[1])
        
        update_user_zp(user_id, amount)
        await message.answer(f"✅ {amount:,} ZP به کاربر {user_id} اضافه شد.")
        
        try:
            await bot.send_message(
                user_id,
                f"🪙 **هدیه از ادمین!**\n\n"
                f"⛏️ **{amount:,} ZP** دریافت کردید!"
            )
        except:
            pass
            
    except:
        await message.answer("❌ خطا! فرمت درست: `/addzp 123456789 1000`")

@dp.message(Command("setlevel"))
async def setlevel_command(message: types.Message, command: CommandObject):
    """تغییر سطح کاربر"""
    if not is_admin(message.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await message.answer("⚠️ فرمت: `/setlevel آیدی سطح`")
        return
    
    try:
        user_id = int(args[0])
        level = int(args[1])
        
        if level < 1 or level > 100:
            await message.answer("⚠️ سطح باید بین 1 تا 100 باشد.")
            return
        
        conn = get_connection()
        c = conn.cursor()
        c.execute('UPDATE users SET level = ? WHERE user_id = ?', (level, user_id))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ سطح کاربر {user_id} به {level} تغییر یافت.")
        
        try:
            await bot.send_message(
                user_id,
                f"🎯 **سطح شما تغییر کرد!**\n\n"
                f"🆙 **سطح جدید:** {level}"
            )
        except:
            pass
            
    except:
        await message.answer("❌ خطا! فرمت درست: `/setlevel 123456789 10`")

@dp.message(Command("giftall"))
async def giftall_command(message: types.Message, command: CommandObject):
    """هدیه به همه کاربران"""
    if not is_admin(message.from_user.id):
        return
    
    args = command.args.split() if command.args else []
    if len(args) < 1:
        await message.answer("⚠️ فرمت: `/giftall سکه [جم] [zp]`")
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
        
        await message.answer(
            f"✅ هدیه ارسال شد!\n\n"
            f"💰 سکه به هر نفر: {coins:,}\n"
            f"💎 جم به هر نفر: {gems}\n"
            f"🪙 ZP به هر نفر: {zp:,}"
        )
        
    except:
        await message.answer("❌ خطا! فرمت درست: `/giftall 1000 5 100`")

@dp.message(Command("broadcast"))
async def broadcast_command(message: types.Message, command: CommandObject):
    """پیام همگانی"""
    if not is_admin(message.from_user.id):
        return
    
    if not command.args:
        await message.answer("⚠️ فرمت: `/broadcast متن پیام`")
        return
    
    text = command.args
    await message.answer(f"📣 پیام به همه کاربران ارسال شد:\n\n{text}")

@dp.message(F.text == "📊 آمار")
async def stats_handler(message: types.Message):
    """آمار ربات"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    total = c.fetchone()[0]
    conn.close()
    
    await message.answer(f"📊 **آمار ربات**\n\n👥 کاربران: {total}\n✅ آنلاین: بله")

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

# ==================== اجرای اصلی ====================

async def main():
    """تابع اصلی اجرای ربات"""
    print("🚀 Starting WarZone Bot...")
    
    # راه‌اندازی وب سرور
    web_runner = await start_web_server()
    
    try:
        # راه‌اندازی ربات
        print("🤖 Bot is running...")
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        print(f"❌ Error in bot: {e}")
    finally:
        await web_runner.cleanup()

if __name__ == '__main__':
    # اجرای ربات
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
