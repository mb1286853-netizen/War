import os
import asyncio
import sqlite3
import random
import logging
from datetime import datetime, timedelta
from contextlib import closing

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
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

# ==================== کیبوردهای اصلی ====================

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

def admin_panel_keyboard():
    """پنل ادمین"""
    keyboard = [
        [KeyboardButton(text="👥 مدیریت کاربران"), KeyboardButton(text="📈 آمار پیشرفته")],
        [KeyboardButton(text="🎮 مدیریت بازی"), KeyboardButton(text="⚙️ تنظیمات ربات")],
        [KeyboardButton(text="📤 خروج از ادمین"), KeyboardButton(text="🔙 بازگشت")]
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
        [KeyboardButton(text="🎯 حمله تکی")],
        [KeyboardButton(text="💣 ترکیب ۱"), KeyboardButton(text="💥 ترکیب ۲")],
        [KeyboardButton(text="🔥 ترکیب ۳"), KeyboardButton(text="🔙 بازگشت")]
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
        [KeyboardButton(text="💰 باکس سکه"), KeyboardButton(text="🪙 باکس ZP")],
        [KeyboardButton(text="💎 باکس ویژه"), KeyboardButton(text="✨ باکس افسانه‌ای")],
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

def miner_keyboard():
    """کیبورد ماینر"""
    keyboard = [
        [KeyboardButton(text="💰 برداشت ZP"), KeyboardButton(text="⬆️ ارتقا ماینر")],
        [KeyboardButton(text="📊 اطلاعات ماینر"), KeyboardButton(text="🔙 بازگشت")]
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

class BuyStates(StatesGroup):
    waiting_for_quantity = State()
    waiting_for_item = State()

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_coin_amount = State()
    waiting_for_gem_amount = State()
    waiting_for_zp_amount = State()
    waiting_for_level = State()
    # ==================== داده‌های بازی ====================

# 🚀 موشک‌های معمولی
MISSILES = {
    "موشک کوتاه برد": {"damage": 50, "price": 200, "min_level": 1, "emoji": "🚀"},
    "موشک میان برد": {"damage": 70, "price": 500, "min_level": 2, "emoji": "🎯"},
    "موشک بالستیک": {"damage": 90, "price": 1000, "min_level": 3, "emoji": "💥"},
    "موشک هدایت شونده": {"damage": 110, "price": 2000, "min_level": 4, "emoji": "🎮"},
    "موشک زمین به هوا": {"damage": 130, "price": 5000, "min_level": 5, "emoji": "🛩️"},
}

# ☢️ موشک‌های آخرالزمانی
APOCALYPSE_MISSILES = {
    "موشک هسته‌ای": {"damage": 500, "price": 50000, "min_level": 10, "emoji": "☢️", "required_gem": 5},
    "موشک پلاسمایی": {"damage": 400, "price": 40000, "min_level": 9, "emoji": "⚡", "required_gem": 4},
    "موشک خورشیدی": {"damage": 350, "price": 35000, "min_level": 8, "emoji": "☀️", "required_gem": 3},
    "موشک سونامی": {"damage": 300, "price": 30000, "min_level": 7, "emoji": "🌊", "required_gem": 2},
    "موشک زلزله": {"damage": 250, "price": 25000, "min_level": 6, "emoji": "🌋", "required_gem": 1},
}

# ترکیب موشک‌ها
ALL_MISSILES = {**MISSILES, **APOCALYPSE_MISSILES}

# ✈️ جنگنده‌ها
FIGHTERS = {
    "F-16 Falcon": {"bonus": 80, "price": 5000, "min_level": 3, "emoji": "🦅"},
    "F-22 Raptor": {"bonus": 150, "price": 12000, "min_level": 6, "emoji": "⚡"},
    "Su-57 Felon": {"bonus": 220, "price": 25000, "min_level": 9, "emoji": "🔥"},
    "B-2 Spirit": {"bonus": 300, "price": 50000, "min_level": 12, "emoji": "👻"},
}

# 🛸 پهپادها
DRONES = {
    "MQ-9 Reaper": {"bonus": 100, "price": 8000, "min_level": 4, "emoji": "💀"},
    "RQ-4 Global Hawk": {"bonus": 180, "price": 18000, "min_level": 7, "emoji": "🦅"},
    "X-47B": {"bonus": 250, "price": 35000, "min_level": 10, "emoji": "🤖"},
    "Avenger": {"bonus": 350, "price": 60000, "min_level": 13, "emoji": "⚡"},
}

# 🛡️ سیستم دفاعی
DEFENSES = {
    "پدافند موشکی": {"bonus": 0.15, "price": 3000, "upgrade_cost": 1500, "level": 1, "emoji": "🚫"},
    "پدافند الکترونیک": {"bonus": 0.10, "price": 2000, "upgrade_cost": 1000, "level": 1, "emoji": "📡"},
    "پدافند ضد جنگنده": {"bonus": 0.12, "price": 2500, "upgrade_cost": 1200, "level": 1, "emoji": "✈️"},
    "برج امنیت سایبری": {"bonus": 0.50, "price": 10000, "upgrade_cost": 5000, "level": 1, "emoji": "🏰"},
}

# ⛏️ ماینر
MINER_LEVELS = {
    1: {"zp_per_hour": 100, "upgrade_cost": 100, "name": "ماینر پایه", "emoji": "⛏️"},
    2: {"zp_per_hour": 200, "upgrade_cost": 200, "name": "ماینر متوسط", "emoji": "⚒️"},
    3: {"zp_per_hour": 300, "upgrade_cost": 300, "name": "ماینر پیشرفته", "emoji": "🔧"},
    4: {"zp_per_hour": 400, "upgrade_cost": 400, "name": "ماینر حرفه‌ای", "emoji": "⚙️"},
    5: {"zp_per_hour": 500, "upgrade_cost": 500, "name": "ماینر فوق‌حرفه‌ای", "emoji": "💎"},
    6: {"zp_per_hour": 600, "upgrade_cost": 600, "name": "ماینر صنعتی", "emoji": "🏭"},
    7: {"zp_per_hour": 700, "upgrade_cost": 700, "name": "ماینر فوق‌صنعتی", "emoji": "🏗️"},
    8: {"zp_per_hour": 800, "upgrade_cost": 800, "name": "ماینر فضایی", "emoji": "🚀"},
    9: {"zp_per_hour": 900, "upgrade_cost": 900, "name": "ماینر کوانتومی", "emoji": "⚛️"},
    10: {"zp_per_hour": 1000, "upgrade_cost": 10000, "name": "ماینر ستاره‌ای", "emoji": "⭐"},
    11: {"zp_per_hour": 1100, "upgrade_cost": 11000, "name": "ماینر افسانه‌ای", "emoji": "🌟"},
    12: {"zp_per_hour": 1200, "upgrade_cost": 12000, "name": "ماینر کهکشانی", "emoji": "🌌"},
    13: {"zp_per_hour": 1300, "upgrade_cost": 13000, "name": "ماینر کیهانی", "emoji": "☄️"},
    14: {"zp_per_hour": 1400, "upgrade_cost": 14000, "name": "ماینر مطلق", "emoji": "♾️"},
    15: {"zp_per_hour": 1500, "upgrade_cost": 0, "name": "ماینر خداگونه", "emoji": "👑"},
}

# 🎁 باکس‌ها
BOXES = {
    "سکه": {"name": "باکس سکه", "price": 500, "reward_type": "coin", "min": 100, "max": 2000, "emoji": "💰"},
    "zp": {"name": "باکس ZP", "price": 1000, "reward_type": "zp", "min": 50, "max": 500, "emoji": "🪙"},
    "ویژه": {"name": "باکس ویژه", "price_gem": 5, "reward_type": "gem", "min": 1, "max": 20, "emoji": "💎"},
    "افسانه‌ای": {"name": "باکس افسانه‌ای", "price_gem": 10, "reward_type": "all", "chance": 0.1, "emoji": "✨"},
    "رایگان": {"name": "باکس رایگان", "price": 0, "reward_type": "random", "min": 10, "max": 100, "emoji": "🎫"},
}

# 💥 ترکیب‌های حمله
ATTACK_COMBOS = {
    "ترکیب ۱": {
        "name": "💣 حمله ساده",
        "description": "حمله پایه با موشک کوتاه برد",
        "damage_multiplier": 1.0,
        "required_missiles": {"موشک کوتاه برد": 1}
    },
    "ترکیب ۲": {
        "name": "💥 حمله متوسط",
        "description": "حمله با موشک میان برد و جنگنده",
        "damage_multiplier": 1.5,
        "required_missiles": {"موشک میان برد": 1},
        "required_fighters": {"F-16 Falcon": 1}
    },
    "ترکیب ۳": {
        "name": "🔥 حمله پیشرفته",
        "description": "حمله کامل با موشک بالستیک، جنگنده و پهپاد",
        "damage_multiplier": 2.0,
        "required_missiles": {"موشک بالستیک": 1},
        "required_fighters": {"F-22 Raptor": 1},
        "required_drones": {"MQ-9 Reaper": 1}
    },
    "ترکیب هسته‌ای": {
        "name": "☢️ حمله هسته‌ای",
        "description": "حمله ویرانگر با موشک هسته‌ای",
        "damage_multiplier": 5.0,
        "required_missiles": {"موشک هسته‌ای": 1},
        "required_gems": 10
    }
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
                total_gems BIGINT DEFAULT 0,
                total_zp BIGINT DEFAULT 0,
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
        
        # جدول باکس‌ها
        c.execute('''
            CREATE TABLE IF NOT EXISTS box_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                box_type TEXT,
                reward_amount INTEGER,
                reward_type TEXT,
                opened_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        # جدول لاگ ادمین
        c.execute('''
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                action TEXT,
                target_user_id INTEGER,
                details TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        c.execute('INSERT OR IGNORE INTO bot_stats (id, total_users, total_coins, total_gems, total_zp) VALUES (1, 0, 0, 0, 0)')
        
        self.conn.commit()
        logger.info("✅ دیتابیس راه‌اندازی شد")
    
    def execute(self, query: str, params: tuple = ()):
        try:
            c = self.conn.cursor()
            c.execute(query, params)
            self.conn.commit()
            return c
        except sqlite3.Error as e:
            logger.error(f"❌ خطای دیتابیس: {e}")
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
        logger.error(f"خطا در دریافت کاربر {user_id}: {e}")
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
            for missile in ALL_MISSILES:
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
            
            db.execute('UPDATE bot_stats SET total_users = total_users + 1, total_coins = total_coins + ?, total_gems = total_gems + ?', 
                      (coins, gems))
            
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
    return user['is_admin'] == 1 or user_id in ADMIN_IDS

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
        
        # به‌روزرسانی آمار کلی
        if amount > 0:
            db.execute('UPDATE bot_stats SET total_coins = total_coins + ?', (amount,))
        
        return True
    except Exception as e:
        logger.error(f"خطا در بروزرسانی سکه برای {user_id}: {e}")
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
        
        # به‌روزرسانی آمار کلی
        if amount > 0:
            db.execute('UPDATE bot_stats SET total_gems = total_gems + ?', (amount,))
        
        return True
    except Exception as e:
        logger.error(f"خطا در بروزرسانی جم برای {user_id}: {e}")
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
        
        # به‌روزرسانی آمار کلی
        if amount > 0:
            db.execute('UPDATE bot_stats SET total_zp = total_zp + ?', (amount,))
        
        return True
    except Exception as e:
        logger.error(f"خطا در بروزرسانی ZP برای {user_id}: {e}")
        return False

def update_user_level(user_id: int, new_level: int):
    try:
        if new_level < 1 or new_level > 100:
            return False
        
        db.execute('UPDATE users SET level = ? WHERE user_id = ?', 
                  (new_level, user_id))
        return True
    except Exception as e:
        logger.error(f"خطا در بروزرسانی لول برای {user_id}: {e}")
        return False

def get_user_missiles(user_id: int):
    """دریافت موشک‌های کاربر"""
    try:
        c = db.execute('SELECT missile_name, quantity FROM user_missiles WHERE user_id = ?', (user_id,))
        missiles = {row['missile_name']: row['quantity'] for row in c.fetchall()}
        return missiles
    except Exception as e:
        logger.error(f"خطا در دریافت موشک‌های کاربر {user_id}: {e}")
        return {}

def update_user_missile(user_id: int, missile_name: str, amount: int):
    """به‌روزرسانی موشک کاربر"""
    try:
        # بررسی وجود موشک
        c = db.execute('SELECT 1 FROM user_missiles WHERE user_id = ? AND missile_name = ?', 
                      (user_id, missile_name))
        exists = c.fetchone()
        
        if exists:
            db.execute('UPDATE user_missiles SET quantity = quantity + ? WHERE user_id = ? AND missile_name = ?',
                      (amount, user_id, missile_name))
        else:
            db.execute('INSERT INTO user_missiles (user_id, missile_name, quantity) VALUES (?, ?, ?)',
                      (user_id, missile_name, amount))
        
        # بررسی مقدار منفی
        c = db.execute('SELECT quantity FROM user_missiles WHERE user_id = ? AND missile_name = ?',
                      (user_id, missile_name))
        quantity = c.fetchone()['quantity']
        if quantity < 0:
            db.execute('UPDATE user_missiles SET quantity = 0 WHERE user_id = ? AND missile_name = ?',
                      (user_id, missile_name))
        
        return True
    except Exception as e:
        logger.error(f"خطا در بروزرسانی موشک برای {user_id}: {e}")
        return False

def get_bot_stats():
    """دریافت آمار ربات"""
    try:
        c = db.execute('SELECT * FROM bot_stats WHERE id = 1')
        stats = c.fetchone()
        return dict(stats) if stats else None
    except Exception as e:
        logger.error(f"خطا در دریافت آمار ربات: {e}")
        return None

def log_admin_action(admin_id: int, action: str, target_user_id: int = None, details: str = ""):
    """ثبت لاگ اقدامات ادمین"""
    try:
        db.execute('''
            INSERT INTO admin_logs (admin_id, action, target_user_id, details)
            VALUES (?, ?, ?, ?)
        ''', (admin_id, action, target_user_id, details))
        return True
    except Exception as e:
        logger.error(f"خطا در ثبت لاگ ادمین: {e}")
        return False

def get_all_users():
    """دریافت لیست همه کاربران"""
    try:
        c = db.execute('SELECT user_id, username, full_name, zone_coin, zone_gem, zone_point, level, last_miner_claim FROM users ORDER BY created_at DESC')
        users = [dict(row) for row in c.fetchall()]
        return users
    except Exception as e:
        logger.error(f"خطا در دریافت لیست کاربران: {e}")
        return []

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

# ==================== پنل ادمین ====================

@dp.message(F.text == "👑 پنل ادمین")
async def admin_panel_handler(message: types.Message):
    """ورود به پنل ادمین"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("⛔ دسترسی ممنوع! شما ادمین نیستید.")
        return
    
    await message.answer(
        "👑 <b>پنل مدیریت ادمین</b>\n\n"
        "لطفا یکی از گزینه‌های زیر را انتخاب کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_panel_keyboard()
    )
@dp.message(F.text == "👥 مدیریت کاربران")
async def manage_users_handler(message: types.Message):
    """مدیریت کاربران"""
    if not is_admin(message.from_user.id):
        return
    
    users = get_all_users()
    
    if not users:
        await message.answer("📭 هیچ کاربری ثبت نشده است.")
        return
    
    # نمایش 10 کاربر آخر
    recent_users = users[:10]
    
    users_text = ""
    for i, user in enumerate(recent_users, 1):
        users_text += f"\n{i}. {user['full_name']} (ID: {user['user_id']})"
        users_text += f"\n   💰 {user['zone_coin']:,} سکه | 💎 {user['zone_gem']:,} جم | 🪙 {user['zone_point']:,} ZP | 📊 لول {user['level']}"
    
    await message.answer(
        f"👥 <b>مدیریت کاربران</b>\n\n"
        f"📊 مجموع کاربران: {len(users)}\n"
        f"🆕 آخرین کاربران:{users_text}\n\n"
        f"برای تغییر مشخصات کاربر، آیدی آن را ارسال کنید.",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )

@dp.message(F.text == "📊 آمار کامل")
async def bot_stats_handler(message: types.Message):
    """آمار کامل ربات"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        # دریافت آمار
        stats = get_bot_stats()
        all_users = get_all_users()
        
        if not stats:
            await message.answer("❌ خطا در دریافت آمار!")
            return
        
        # محاسبه آمار
        total_users = len(all_users)
        
        # محاسبه مجموع دارایی‌ها
        total_coins = 0
        total_gems = 0
        total_zp = 0
        active_users = 0
        
        now = int(datetime.now().timestamp())
        for user in all_users:
            total_coins += user.get('zone_coin', 0)
            total_gems += user.get('zone_gem', 0)
            total_zp += user.get('zone_point', 0)
            
            # کاربران فعال (آخرین 24 ساعت)
            last_claim = user.get('last_miner_claim', 0)
            if last_claim > now - 86400:
                active_users += 1
        
        # زمان به‌روزرسانی
        update_time = stats.get('last_updated', now)
        try:
            last_updated = datetime.fromtimestamp(update_time).strftime('%Y-%m-%d %H:%M:%S')
        except:
            last_updated = "نامشخص"
        
        # ساخت پیام
        stats_message = (
            f"📊 <b>آمار کامل ربات</b>\n\n"
            f"👥 <b>کاربران:</b>\n"
            f"• مجموع کاربران: {total_users:,}\n"
            f"• کاربران فعال (24h): {active_users:,}\n\n"
            f"💰 <b>اقتصاد بازی:</b>\n"
            f"• مجموع سکه‌ها: {total_coins:,}\n"
            f"• مجموع جم‌ها: {total_gems:,}\n"
            f"• مجموع ZP: {total_zp:,}\n\n"
            f"🏦 <b>آمار سرور:</b>\n"
            f"• کل سکه تولید شده: {stats.get('total_coins', 0):,}\n"
            f"• کل جم تولید شده: {stats.get('total_gems', 0):,}\n"
            f"• کل ZP تولید شده: {stats.get('total_zp', 0):,}\n\n"
            f"🕒 آخرین بروزرسانی: {last_updated}"
        )
        
        await message.answer(stats_message, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"خطا در آمار ربات: {e}")
        await message.answer("❌ خطا در پردازش آمار!")

@dp.message(F.text == "💰 +سکه")
async def add_coins_handler(message: types.Message, state: FSMContext):
    """افزودن سکه به کاربر"""
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "💰 <b>افزودن سکه</b>\n\n"
        "لطفا آیدی کاربر مورد نظر را ارسال کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="add_coins")

@dp.message(F.text == "💎 +جم")
async def add_gems_handler(message: types.Message, state: FSMContext):
    """افزودن جم به کاربر"""
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "💎 <b>افزودن جم</b>\n\n"
        "لطفا آیدی کاربر مورد نظر را ارسال کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="add_gems")

@dp.message(F.text == "🪙 +ZP")
async def add_zp_handler(message: types.Message, state: FSMContext):
    """افزودن ZP به کاربر"""
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "🪙 <b>افزودن ZP</b>\n\n"
        "لطفا آیدی کاربر مورد نظر را ارسال کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="add_zp")

@dp.message(F.text == "🆙 تغییر لول")
async def change_level_handler(message: types.Message, state: FSMContext):
    """تغییر لول کاربر"""
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "🆙 <b>تغییر لول کاربر</b>\n\n"
        "لطفا آیدی کاربر مورد نظر را ارسال کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="change_level")

@dp.message(AdminStates.waiting_for_user_id)
async def process_user_id(message: types.Message, state: FSMContext):
    """پردازش آیدی کاربر"""
    if message.text == "🔙 بازگشت":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=admin_keyboard())
        return
    
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("❌ آیدی باید عدد باشد! لطفا دوباره ارسال کنید.")
        return
    
    # بررسی وجود کاربر
    user = get_user(user_id)
    if not user:
        await message.answer(f"❌ کاربر با آیدی {user_id} یافت نشد!")
        return
    
    data = await state.get_data()
    action = data.get('action')
    
    await state.update_data(target_user_id=user_id, user_name=user['full_name'])
    
    if action == "add_coins":
        await message.answer(
            f"💰 <b>افزودن سکه به کاربر</b>\n\n"
            f"👤 کاربر: {user['full_name']}\n"
            f"🆔 آیدی: {user_id}\n"
            f"💰 سکه فعلی: {user['zone_coin']:,}\n\n"
            f"لطفا مقدار سکه را وارد کنید:",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )
        await state.set_state(AdminStates.waiting_for_coin_amount)
    
    elif action == "add_gems":
        await message.answer(
            f"💎 <b>افزودن جم به کاربر</b>\n\n"
            f"👤 کاربر: {user['full_name']}\n"
            f"🆔 آیدی: {user_id}\n"
            f"💎 جم فعلی: {user['zone_gem']:,}\n\n"
            f"لطفا مقدار جم را وارد کنید:",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )
        await state.set_state(AdminStates.waiting_for_gem_amount)
    
    elif action == "add_zp":
        await message.answer(
            f"🪙 <b>افزودن ZP به کاربر</b>\n\n"
            f"👤 کاربر: {user['full_name']}\n"
            f"🆔 آیدی: {user_id}\n"
            f"🪙 ZP فعلی: {user['zone_point']:,}\n\n"
            f"لطفا مقدار ZP را وارد کنید:",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )
        await state.set_state(AdminStates.waiting_for_zp_amount)
    
    elif action == "change_level":
        await message.answer(
            f"🆙 <b>تغییر لول کاربر</b>\n\n"
            f"👤 کاربر: {user['full_name']}\n"
            f"🆔 آیدی: {user_id}\n"
            f"📊 لول فعلی: {user['level']}\n\n"
            f"لطفا لول جدید را وارد کنید (1 تا 100):",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )
        await state.set_state(AdminStates.waiting_for_level)
        
