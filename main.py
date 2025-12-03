import os
import asyncio
import sqlite3
import random
import logging
from datetime import datetime, timedelta
from contextlib import closing

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
import aiohttp
from dotenv import load_dotenv

# ==================== تنظیمات ====================
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x]
PORT = int(os.getenv('PORT', 8080))
KEEP_ALIVE_URL = os.getenv('KEEP_ALIVE_URL', '')

if not BOT_TOKEN:
    print("❌ خطا: BOT_TOKEN تنظیم نشده!")
    exit(1)

# تنظیمات لاگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = '/app/data/warzone.db'
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ==================== کیبوردها ====================

def user_keyboard():
    """کیبورد کاربران عادی"""
    keyboard = [
        [KeyboardButton(text="👤 پروفایل"), KeyboardButton(text="🛒 فروشگاه")],
        [KeyboardButton(text="⛏️ ماینر ZP"), KeyboardButton(text="💥 حمله")],
        [KeyboardButton(text="🎁 باکس‌ها"), KeyboardButton(text="🛡️ دفاع")],
        [KeyboardButton(text="🔧 خرابکاری"), KeyboardButton(text="🆘 پشتیبانی")]
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
        [KeyboardButton(text="🛸 پهپادها"), KeyboardButton(text="🛡️ سیستم دفاعی")],
        [KeyboardButton(text="🎁 باکس‌ها"), KeyboardButton(text="🔙 بازگشت")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def attack_keyboard():
    """کیبورد حمله"""
    keyboard = [
        [KeyboardButton(text="⚔️ حمله تکی")],
        [KeyboardButton(text="🧩 حمله ترکیبی ۱"), KeyboardButton(text="🧩 حمله ترکیبی ۲")],
        [KeyboardButton(text="🧩 حمله ترکیبی ۳"), KeyboardButton(text="🔙 بازگشت")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def defense_keyboard():
    """کیبورد دفاع"""
    keyboard = [
        [KeyboardButton(text="🛡️ برج امنیت سایبری")],
        [KeyboardButton(text="🚫 پدافند موشکی"), KeyboardButton(text="📡 پدافند الکترونیک")],
        [KeyboardButton(text="✈️ پدافند ضد جنگنده"), KeyboardButton(text="🔙 بازگشت")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def box_keyboard():
    """کیبورد باکس‌ها"""
    keyboard = [
        [KeyboardButton(text="🎁 باکس سکه (500 سکه)"), KeyboardButton(text="🎁 باکس ZP (1000 سکه)")],
        [KeyboardButton(text="💎 باکس ویژه (5 جم)"), KeyboardButton(text="✨ باکس افسانه‌ای (10 جم)")],
        [KeyboardButton(text="🎫 باکس رایگان"), KeyboardButton(text="🔙 بازگشت")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def support_keyboard():
    """کیبورد پشتیبانی"""
    keyboard = [
        [KeyboardButton(text="📞 تماس با ادمین"), KeyboardButton(text="📖 راهنما")],
        [KeyboardButton(text="⚠️ گزارش مشکل"), KeyboardButton(text="🔙 بازگشت")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def back_keyboard():
    """کیبورد بازگشت"""
    keyboard = [[KeyboardButton(text="🔙 بازگشت")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# ==================== حالت‌های FSM ====================
class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirmation = State()

class GiftStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_type = State()

class AttackStates(StatesGroup):
    waiting_for_target = State()
    waiting_for_attack_type = State()

class SupportStates(StatesGroup):
    waiting_for_message = State()

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

DEFENSES = {
    "پدافند موشکی": {"bonus": 0.15, "price": 3000, "upgrade_cost": 1500, "level": 1},
    "پدافند الکترونیک": {"bonus": 0.10, "price": 2000, "upgrade_cost": 1000, "level": 1},
    "پدافند ضد جنگنده": {"bonus": 0.12, "price": 2500, "upgrade_cost": 1200, "level": 1},
    "برج امنیت سایبری": {"bonus": 0.50, "price": 10000, "upgrade_cost": 5000, "level": 1},
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

BOXES = {
    "سکه": {"name": "باکس سکه", "price": 500, "reward_type": "coin", "min": 100, "max": 2000},
    "zp": {"name": "باکس ZP", "price": 1000, "reward_type": "zp", "min": 50, "max": 500},
    "ویژه": {"name": "باکس ویژه", "price_gem": 5, "reward_type": "gem", "min": 1, "max": 20},
    "افسانه‌ای": {"name": "باکس افسانه‌ای", "price_gem": 10, "reward_type": "all", "chance": 0.1},
    "رایگان": {"name": "باکس رایگان", "price": 0, "reward_type": "random", "min": 10, "max": 100},
}

# ==================== دیتابیس ====================
class Database:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.init()
        return cls._instance
    
    def init(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
    
    def create_tables(self):
        c = self.conn.cursor()
        
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
                last_miner_claim INTEGER,
                cyber_tower_level INTEGER DEFAULT 0,
                defense_missile_level INTEGER DEFAULT 0,
                defense_electronic_level INTEGER DEFAULT 0,
                defense_antifighter_level INTEGER DEFAULT 0,
                total_defense_bonus REAL DEFAULT 0.0,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        # جدول موشک‌ها
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_missiles (
                user_id INTEGER,
                missile_name TEXT,
                quantity INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, missile_name),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # جدول جنگنده‌ها
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_fighters (
                user_id INTEGER,
                fighter_name TEXT,
                quantity INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, fighter_name),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # جدول پهپادها
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_drones (
                user_id INTEGER,
                drone_name TEXT,
                quantity INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, drone_name),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # جدول آمار
        c.execute('''
            CREATE TABLE IF NOT EXISTS bot_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_users INTEGER DEFAULT 0,
                total_coins BIGINT DEFAULT 0,
                last_updated INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        # جدول لاگ حمله‌ها
        c.execute('''
            CREATE TABLE IF NOT EXISTS attack_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attacker_id INTEGER,
                target_id INTEGER,
                damage INTEGER,
                loot_coins INTEGER,
                loot_zp INTEGER,
                attack_type TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        # جدول پیام‌های پشتیبانی
        c.execute('''
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                status TEXT DEFAULT 'open',
                admin_response TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        c.execute('INSERT OR IGNORE INTO bot_stats (id, total_users, total_coins) VALUES (1, 0, 0)')
        
        self.conn.commit()
        logger.info("✅ دیتابیس راه‌اندازی شد")
    
    def execute(self, query: str, params: tuple = ()):
        try:
            c = self.conn.cursor()
            c.execute(query, params)
            self.conn.commit()
            return c
        except sqlite3.Error as e:
            logger.error(f"❌ Database error: {e}")
            self.conn.rollback()
            raise
    
    def close(self):
        if self.conn:
            self.conn.close()

db = Database()

# ==================== توابع کمکی دیتابیس ====================
def get_user(user_id: int):
    try:
        c = db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
        return dict(user) if user else None
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None

def create_user(user_id: int, username: str, full_name: str):
    try:
        c = db.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
        exists = c.fetchone()
        
        if not exists:
            is_admin = 1 if user_id in ADMIN_IDS else 0
            coins = 999999999 if is_admin else 1000
            gems = 999999999 if is_admin else 10
            
            db.execute('''
                INSERT INTO users (user_id, username, full_name, zone_coin, zone_gem, is_admin)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, full_name, coins, gems, is_admin))
            
            # ایجاد مقادیر اولیه
            for missile in MISSILES:
                db.execute('''
                    INSERT OR IGNORE INTO user_missiles (user_id, missile_name, quantity)
                    VALUES (?, ?, ?)
                ''', (user_id, missile, 0))
            
            for fighter in FIGHTERS:
                db.execute('''
                    INSERT OR IGNORE INTO user_fighters (user_id, fighter_name, quantity)
                    VALUES (?, ?, ?)
                ''', (user_id, fighter, 0))
            
            for drone in DRONES:
                db.execute('''
                    INSERT OR IGNORE INTO user_drones (user_id, drone_name, quantity)
                    VALUES (?, ?, ?)
                ''', (user_id, drone, 0))
            
            db.execute('UPDATE bot_stats SET total_users = total_users + 1')
            
            logger.info(f"✅ کاربر جدید: {user_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ خطا در ایجاد کاربر {user_id}: {e}")
        return False

def is_admin(user_id: int) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    return user['is_admin'] == 1

def update_user_coins(user_id: int, amount: int):
    try:
        user = get_user(user_id)
        if not user:
            return False
        
        new_balance = user['zone_coin'] + amount
        if new_balance < 0:
            return False
        
        db.execute('UPDATE users SET zone_coin = ? WHERE user_id = ?', 
                  (new_balance, user_id))
        return True
    except Exception as e:
        logger.error(f"Error updating coins for {user_id}: {e}")
        return False

def update_user_gems(user_id: int, amount: int):
    try:
        user = get_user(user_id)
        if not user:
            return False
        
        new_balance = user['zone_gem'] + amount
        if new_balance < 0:
            return False
        
        db.execute('UPDATE users SET zone_gem = ? WHERE user_id = ?', 
                  (new_balance, user_id))
        return True
    except Exception as e:
        logger.error(f"Error updating gems for {user_id}: {e}")
        return False

def update_user_zp(user_id: int, amount: int):
    try:
        user = get_user(user_id)
        if not user:
            return False
        
        new_balance = user['zone_point'] + amount
        if new_balance < 0:
            return False
        
        db.execute('UPDATE users SET zone_point = ? WHERE user_id = ?', 
                  (new_balance, user_id))
        return True
    except Exception as e:
        logger.error(f"Error updating ZP for {user_id}: {e}")
        return False

# ==================== هندلرهای اصلی ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """دستور شروع"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name
    
    create_user(user_id, username, full_name)
    
    user = get_user(user_id)
    if not user:
        await message.answer("❌ خطا در ایجاد حساب کاربری!")
        return
    
    keyboard = admin_keyboard() if is_admin(user_id) else user_keyboard()
    
    await message.answer(
        f"🎮 <b>خوش آمدید به Warzone!</b>\n\n"
        f"👤 شناسه: <code>{user_id}</code>\n"
        f"💰 سکه: {user['zone_coin']:,}\n"
        f"💎 جم: {user['zone_gem']:,}\n"
        f"🪙 ZP: {user['zone_point']:,}\n"
        f"📊 لول: {user['level']}\n\n"
        f"از منوی پایین انتخاب کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )

@dp.message(F.text == "👤 پروفایل")
async def profile_handler(message: types.Message):
    """نمایش پروفایل کاربر"""
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ کاربر یافت نشد!")
        return
    
    # محاسبه زمان باقی مانده تا claim ماینر
    miner_info = ""
    if user['last_miner_claim']:
        next_claim = user['last_miner_claim'] + 3600
        now = int(datetime.now().timestamp())
        if now < next_claim:
            remaining = next_claim - now
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            miner_info = f"\n⏳ ماینر: {hours}:{minutes:02d} تا claim بعدی"
    
    await message.answer(
        f"👤 <b>پروفایل کاربری</b>\n\n"
        f"🆔 شناسه: <code>{user['user_id']}</code>\n"
        f"👤 نام: {user['full_name']}\n"
        f"📊 لول: {user['level']}\n"
        f"⭐ XP: {user['xp']}/1000\n\n"
        f"💰 <b>دارایی‌ها:</b>\n"
        f"• سکه: {user['zone_coin']:,}\n"
        f"• جم: {user['zone_gem']:,}\n"
        f"• ZP: {user['zone_point']:,}\n\n"
        f"🛡️ <b>سیستم دفاعی:</b>\n"
        f"• برج امنیت: سطح {user['cyber_tower_level']}\n"
        f"• پدافند موشکی: سطح {user['defense_missile_level']}\n"
        f"• پدافند الکترونیک: سطح {user['defense_electronic_level']}\n"
        f"• پدافند ضد جنگنده: سطح {user['defense_antifighter_level']}\n"
        f"{miner_info}",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text == "🛒 فروشگاه")
async def shop_handler(message: types.Message):
    """ورود به فروشگاه"""
    await message.answer(
        "🛒 <b>فروشگاه Warzone</b>\n\n"
        "لطفا بخش مورد نظر را انتخاب کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=shop_keyboard()
    )

@dp.message(F.text == "💣 موشک‌ها")
async def missiles_shop(message: types.Message):
    """فروشگاه موشک‌ها"""
    items_text = ""
    for name, data in MISSILES.items():
        items_text += f"\n• {name}: {data['damage']} damage - {data['price']:,} سکه (لول {data['min_level']}+)"
    
    await message.answer(
        f"💣 <b>فروشگاه موشک‌ها</b>{items_text}\n\n"
        f"برای خرید، نام موشک مورد نظر را ارسال کنید.",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )

@dp.message(F.text == "🚁 جنگنده‌ها")
async def fighters_shop(message: types.Message):
    """فروشگاه جنگنده‌ها"""
    items_text = ""
    for name, data in FIGHTERS.items():
        items_text += f"\n• {name}: +{data['bonus']}% damage - {data['price']:,} سکه (لول {data['min_level']}+)"
    
    await message.answer(
        f"🚁 <b>فروشگاه جنگنده‌ها</b>{items_text}",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )

@dp.message(F.text == "🛸 پهپادها")
async def drones_shop(message: types.Message):
    """فروشگاه پهپادها"""
    items_text = ""
    for name, data in DRONES.items():
        items_text += f"\n• {name}: +{data['bonus']}% damage - {data['price']:,} سکه (لول {data['min_level']}+)"
    
    await message.answer(
        f"🛸 <b>فروشگاه پهپادها</b>{items_text}",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
)
@dp.message(F.text == "🛡️ سیستم دفاعی")
async def defense_shop(message: types.Message):
    """فروشگاه سیستم دفاعی"""
    items_text = ""
    for name, data in DEFENSES.items():
        bonus_percent = data['bonus'] * 100
        items_text += f"\n• {name}: {bonus_percent}% دفاع - {data['price']:,} سکه"
    
    await message.answer(
        f"🛡️ <b>فروشگاه سیستم دفاعی</b>{items_text}\n\n"
        f"برای خرید یا ارتقاء، نام سیستم را ارسال کنید.",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )

@dp.message(F.text == "🎁 باکس‌ها")
async def boxes_handler(message: types.Message):
    """منوی باکس‌ها"""
    await message.answer(
        "🎁 <b>باکس‌های Warzone</b>\n\n"
        "باکس مورد نظر خود را انتخاب کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=box_keyboard()
    )

@dp.message(F.text == "💥 حمله")
async def attack_handler(message: types.Message):
    """منوی حمله"""
    await message.answer(
        "💥 <b>سیستم حمله</b>\n\n"
        "نوع حمله را انتخاب کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=attack_keyboard()
    )

@dp.message(F.text == "🛡️ دفاع")
async def defense_handler(message: types.Message):
    """منوی دفاع"""
    user = get_user(message.from_user.id)
    if not user:
        return
    
    await message.answer(
        f"🛡️ <b>سیستم دفاعی شما</b>\n\n"
        f"• 🏰 برج امنیت سایبری: سطح {user['cyber_tower_level']}\n"
        f"• 🚫 پدافند موشکی: سطح {user['defense_missile_level']}\n"
        f"• 📡 پدافند الکترونیک: سطح {user['defense_electronic_level']}\n"
        f"• ✈️ پدافند ضد جنگنده: سطح {user['defense_antifighter_level']}\n\n"
        f"برای ارتقاء سیستم دفاعی، از فروشگاه اقدام کنید.",
        parse_mode=ParseMode.HTML,
        reply_markup=defense_keyboard()
    )

@dp.message(F.text == "🛡️ برج امنیت سایبری")
async def cyber_tower_info(message: types.Message):
    """اطلاعات برج امنیت سایبری"""
    user = get_user(message.from_user.id)
    if not user:
        return
    
    current_level = user['cyber_tower_level']
    next_level = current_level + 1
    upgrade_cost = DEFENSES["برج امنیت سایبری"]["upgrade_cost"] * next_level
    
    await message.answer(
        f"🏰 <b>برج امنیت سایبری</b>\n\n"
        f"سطح فعلی: {current_level}\n"
        f"دفاع: {DEFENSES['برج امنیت سایبری']['bonus'] * 100}%\n\n"
        f"ارتقاء به سطح {next_level}:\n"
        f"هزینه: {upgrade_cost:,} سکه\n"
        f"دفاع جدید: {(DEFENSES['برج امنیت سایبری']['bonus'] * next_level) * 100}%",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )

@dp.message(F.text == "🔧 خرابکاری")
async def sabotage_handler(message: types.Message):
    """منوی خرابکاری"""
    await message.answer(
        "🔧 <b>سیستم خرابکاری</b>\n\n"
        "⚠️ این بخش در حال توسعه است...\n\n"
        "امکانات آینده:\n"
        "• هک سیستم دفاعی\n"
        "• قطع برق دشمن\n"
        "• سرقت اطلاعات\n"
        "• نفوذ به پایگاه",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )

@dp.message(F.text == "🆘 پشتیبانی")
async def support_handler(message: types.Message):
    """منوی پشتیبانی"""
    await message.answer(
        "🆘 <b>پشتیبانی Warzone</b>\n\n"
        "لطفا گزینه مورد نظر را انتخاب کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=support_keyboard()
    )

@dp.message(F.text == "📞 تماس با ادمین")
async def contact_admin(message: types.Message):
    """تماس با ادمین"""
    if not ADMIN_IDS:
        await message.answer("⛔ هیچ ادمینی یافت نشد!")
        return
    
    admins_text = ""
    for admin_id in ADMIN_IDS[:3]:
        admins_text += f"\n👑 Admin ID: {admin_id}"
    
    await message.answer(
        f"📞 <b>تماس با ادمین</b>\n\n"
        f"برای گزارش مشکل یا درخواست کمک، با ادمین‌های زیر تماس بگیرید:{admins_text}\n\n"
        f"یا از گزینه '⚠️ گزارش مشکل' استفاده کنید.",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )

@dp.message(F.text == "⚠️ گزارش مشکل")
async def report_problem(message: types.Message, state: FSMContext):
    """گزارش مشکل"""
    await message.answer(
        "⚠️ <b>گزارش مشکل</b>\n\n"
        "لطفا مشکل یا باگی که با آن مواجه شده‌اید را به طور کامل توضیح دهید:\n\n"
        "📌 مثال:\n"
        "• 'خرید انجام نمیشه'\n"
        "• 'ماینر کار نمی‌کنه'\n"
        "• 'ارور میده وقتی حمله می‌کنم'",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )
    await state.set_state(SupportStates.waiting_for_message)

@dp.message(SupportStates.waiting_for_message)
async def process_support_message(message: types.Message, state: FSMContext):
    """پردازش پیام پشتیبانی"""
    if message.text == "🔙 بازگشت":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=support_keyboard())
        return
    
    try:
        # ذخیره در دیتابیس
        db.execute('''
            INSERT INTO support_tickets (user_id, message)
            VALUES (?, ?)
        ''', (message.from_user.id, message.text))
        
        # اطلاع به ادمین‌ها
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"🆘 <b>گزارش مشکل جدید</b>\n\n"
                    f"👤 کاربر: {message.from_user.full_name}\n"
                    f"🆔 ID: {message.from_user.id}\n"
                    f"📝 پیام:\n{message.text}",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
        
        await message.answer(
            "✅ <b>گزارش شما ارسال شد!</b>\n\n"
            "مشکل شما توسط ادمین‌ها بررسی خواهد شد.\n"
            "پاسخ از طریق همین ربات ارسال می‌شود.",
            parse_mode=ParseMode.HTML,
            reply_markup=support_keyboard()
        )
    except Exception as e:
        logger.error(f"Error saving support ticket: {e}")
        await message.answer("❌ خطا در ارسال گزارش!")
    
    await state.clear()

@dp.message(F.text == "📖 راهنما")
async def help_guide(message: types.Message):
    """راهنمای ربات"""
    await message.answer(
        "📖 <b>راهنمای Warzone</b>\n\n"
        "🎮 <b>هدف بازی:</b>\n"
        "• جمع‌آوری منابع (سکه، جم، ZP)\n"
        "• ارتقاء سیستم دفاعی\n"
        "• حمله به دیگر بازیکنان\n"
        "• پیشرفت در لول‌ها\n\n"
        "🛒 <b>فروشگاه:</b>\n"
        "• موشک: برای حمله مستقیم\n"
        "• جنگنده: افزایش damage حمله\n"
        "• پهپاد: حمله هوایی\n"
        "• سیستم دفاعی: محافظت از پایگاه\n\n"
        "⛏️ <b>ماینر ZP:</b>\n"
        "• هر 1 ساعت ZP تولید می‌کند\n"
        "• با ارتقاء، تولید افزایش می‌یابد\n\n"
        "💥 <b>حمله:</b>\n"
        "• حمله تکی: یک نوع سلاح\n"
        "• حمله ترکیبی: ترکیب چند سلاح\n\n"
        "🎁 <b>باکس‌ها:</b>\n"
        "• با سکه یا جم خریداری می‌شوند\n"
        "• حاوی منابع مختلف هستند\n\n"
        "برای شروع، از منوی اصلی '👤 پروفایل' را ببینید.",
        parse_mode=ParseMode.HTML,
        reply_markup=support_keyboard()
    )

@dp.message(F.text == "⛏️ ماینر ZP")
async def miner_handler(message: types.Message):
    """سیستم ماینر"""
    user = get_user(message.from_user.id)
    if not user:
        return
    
    miner_level = user['miner_level']
    miner_data = MINER_LEVELS.get(miner_level, {})
    
    # محاسبه ZP قابل claim
    claimable_zp = 0
    if user['last_miner_claim']:
        now = int(datetime.now().timestamp())
        time_passed = now - user['last_miner_claim']
        hours_passed = time_passed / 3600
        
        if hours_passed >= 1:
            claimable_zp = int(miner_data.get('zp_per_hour', 100) * hours_passed)
    
    # اطلاعات ارتقاء
    next_level = miner_level + 1
    next_miner_data = MINER_LEVELS.get(next_level, {})
    
    upgrade_info = ""
    if next_miner_data:
        upgrade_cost = next_miner_data.get('upgrade_cost', 0)
        upgrade_info = f"\n\n🔼 <b>ارتقاء به سطح {next_level}:</b>\n"
        upgrade_info += f"هزینه: {upgrade_cost:,} سکه\n"
        upgrade_info += f"تولید جدید: {next_miner_data.get('zp_per_hour', 0)} ZP/ساعت"
    
    await message.answer(
        f"⛏️ <b>ماینر ZP</b>\n\n"
        f"📊 سطح فعلی: {miner_level}\n"
        f"🏷️ نام: {miner_data.get('name', 'ماینر پایه')}\n"
        f"⚡ تولید: {miner_data.get('zp_per_hour', 100)} ZP/ساعت\n"
        f"💰 قابل برداشت: {claimable_zp:,} ZP\n\n"
        f"برای برداشت ZP، دستور /claim را ارسال کنید.{upgrade_info}",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )

@dp.message(Command("claim"))
async def claim_miner(message: types.Message):
    """برداشت ZP از ماینر"""
    user = get_user(message.from_user.id)
    if not user:
        return
    
    miner_level = user['miner_level']
    miner_data = MINER_LEVELS.get(miner_level, {})
    
    if not user['last_miner_claim']:
        # اولین بار
        db.execute('UPDATE users SET last_miner_claim = ? WHERE user_id = ?',
                  (int(datetime.now().timestamp()), message.from_user.id))
        await message.answer("✅ ماینر فعال شد! 1 ساعت دیگر ZP تولید می‌کند.")
        return
    
    now = int(datetime.now().timestamp())
    time_passed = now - user['last_miner_claim']
    
    if time_passed < 3600:
        remaining = 3600 - time_passed
        minutes = remaining // 60
        await message.answer(f"⏳ {minutes} دقیقه دیگر می‌توانید ZP برداشت کنید.")
        return
    
    hours_passed = time_passed / 3600
    claimable_zp = int(miner_data.get('zp_per_hour', 100) * hours_passed)
    
    # بروزرسانی
    db.execute('UPDATE users SET zone_point = zone_point + ?, last_miner_claim = ? WHERE user_id = ?',
              (claimable_zp, now, message.from_user.id))
    
    await message.answer(
        f"✅ <b>{claimable_zp:,} ZP برداشت شد!</b>\n\n"
        f"تولید ماینر: {miner_data.get('zp_per_hour', 100)} ZP/ساعت\n"
        f"مجموع ZP شما: {user['zone_point'] + claimable_zp:,}",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text == "🔙 بازگشت")
async def back_handler(message: types.Message):
    """بازگشت به منوی اصلی"""
    user_id = message.from_user.id
    keyboard = admin_keyboard() if is_admin(user_id) else user_keyboard()
    
    await message.answer(
        "📋 <b>منوی اصلی</b>\n\n"
        "لطفا گزینه مورد نظر را انتخاب کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )

# ==================== سیستم Keep-Alive ====================
async def keep_alive_ping():
    """پینگ دوره‌ی به سرور برای جلوگیری از خوابیدن"""
    if not KEEP_ALIVE_URL:
        logger.warning("⚠️ KEEP_ALIVE_URL تنظیم نشده - سیستم keep-alive غیرفعال")
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(KEEP_ALIVE_URL) as response:
                if response.status == 200:
                    logger.info("✅ Keep-alive ping successful")
                else:
                    logger.warning(f"⚠️ Keep-alive failed: {response.status}")
    except Exception as e:
        logger.error(f"❌ Keep-alive error: {e}")

async def start_keep_alive():
    """شروع پینگ دوره‌ای هر 5 دقیقه"""
    while True:
        await asyncio.sleep(300)  # هر 5 دقیقه
        await keep_alive_ping()

async def web_server():
    """وب سرور ساده برای keep-alive"""
    async def handle(request):
        return web.Response(text='Bot is alive!')
    
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"🌐 Web server started on port {PORT}")

# ==================== تابع اصلی ====================
async def main():
    """تابع اصلی اجرای ربات"""
    try:
        # راه‌اندازی دیتابیس
        db.init()
        
        # شروع وب سرور برای keep-alive
        asyncio.create_task(web_server())
        
        # شروع پینگ دوره‌ای keep-alive
        if KEEP_ALIVE_URL:
            asyncio.create_task(start_keep_alive())
            logger.info("🚀 سیستم keep-alive فعال شد")
        
        # پاک کردن webhook و شروع polling
        await bot.delete_webhook(drop_pending_updates=True)
        
        logger.info("🤖 ربات Warzone شروع به کار کرد...")
        
        # شروع dispatcher
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ خطای اصلی: {e}")
    finally:
        # بستن اتصالات
        db.close()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
