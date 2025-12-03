import os
import asyncio
import sqlite3
import random
import logging
from datetime import datetime, timedelta
from contextlib import closing
from enum import Enum

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

# ==================== حالت‌های FSM ====================
class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirmation = State()

class GiftStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_type = State()

# ==================== داده‌های بازی (بدون تغییر) ====================
# [همان داده‌های قبلی...]
# برای حفظ فضای پاسخ، داده‌ها را تکرار نمی‌کنم

# ==================== کیبوردها (بدون تغییر) ====================
# [همان کیبوردهای قبلی...]

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
    """شروع پینگ دوره‌ای هر 10 دقیقه"""
    while True:
        await asyncio.sleep(600)  # هر 10 دقیقه
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

# ==================== بهبود دیتابیس ====================
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
        
        # جدول کاربران (بهبود یافته)
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
                last_miner_claim INTEGER,  -- تغییر به INTEGER
                cyber_tower_level INTEGER DEFAULT 0,
                defense_missile_level INTEGER DEFAULT 0,
                defense_electronic_level INTEGER DEFAULT 0,
                defense_antifighter_level INTEGER DEFAULT 0,
                total_defense_bonus REAL DEFAULT 0.0,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        # جدول موشک‌های کاربر
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
        
        # جدول لاگ پیام‌های همگانی
        c.execute('''
            CREATE TABLE IF NOT EXISTS broadcast_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                message_text TEXT,
                sent_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                sent_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        c.execute('INSERT OR IGNORE INTO bot_stats (id, total_users, total_coins) VALUES (1, 0, 0)')
        
        self.conn.commit()
        logger.info("✅ دیتابیس راه‌اندازی شد")
    
    def get_connection(self):
        return self.conn
    
    def execute(self, query: str, params: tuple = ()):
        """اجرای کوئری با مدیریت خطا"""
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

# ایجاد نمونه دیتابیس
db = Database()

def get_user(user_id: int):
    """دریافت کاربر با مدیریت خطا"""
    try:
        c = db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
        return dict(user) if user else None
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None

def create_user(user_id: int, username: str, full_name: str):
    """ایجاد کاربر جدید با مقادیر اولیه"""
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
            
            # ایجاد مقادیر اولیه برای تجهیزات
            for missile in MISSILES:
                db.execute('''
                    INSERT OR IGNORE INTO user_missiles (user_id, missile_name, quantity)
                    VALUES (?, ?, ?)
                ''', (user_id, missile, 0))
            
            db.execute('UPDATE bot_stats SET total_users = total_users + 1')
            
            logger.info(f"✅ کاربر جدید ایجاد شد: {user_id} - {username}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ خطا در ایجاد کاربر {user_id}: {e}")
        return False

def update_user_coins(user_id: int, amount: int):
    """به روزرسانی سکه‌های کاربر با بررسی موجودی"""
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
    """به روزرسانی جم کاربر"""
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
    """به روزرسانی ZP کاربر"""
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

def is_admin(user_id: int) -> bool:
    """بررسی ادمین بودن با اعتبارسنجی کامل"""
    user = get_user(user_id)
    if not user:
        return False
    return user['is_admin'] == 1

# ==================== سیستم پیام همگانی ====================
async def send_broadcast_to_all_users(message_text: str, admin_id: int):
    """ارسال پیام به همه کاربران"""
    try:
        c = db.execute('SELECT user_id FROM users')
        users = c.fetchall()
        
        sent_count = 0
        failed_count = 0
        
        for user_row in users:
            user_id = user_row['user_id']
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"📢 <b>پیام همگانی:</b>\n\n{message_text}",
                    parse_mode=ParseMode.HTML
                )
                sent_count += 1
                await asyncio.sleep(0.05)  # جلوگیری از محدودیت rate limit
            except Exception as e:
                logger.error(f"Failed to send to {user_id}: {e}")
                failed_count += 1
        
        # ذخیره در لاگ
        db.execute('''
            INSERT INTO broadcast_logs (admin_id, message_text, sent_count, failed_count)
            VALUES (?, ?, ?, ?)
        ''', (admin_id, message_text, sent_count, failed_count))
        
        return sent_count, failed_count
    except Exception as e:
        logger.error(f"❌ Broadcast error: {e}")
        return 0, 0

# ==================== هندلرهای پیام همگانی ====================
@dp.message(F.text == "📣 پیام همگانی")
async def start_broadcast(message: types.Message, state: FSMContext):
    """شروع فرآیند ارسال پیام همگانی"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ دسترسی denied!")
        return
    
    await message.answer(
        "📝 لطفا متن پیام همگانی را ارسال کنید:\n\n"
        "📌 می‌توانید از HTML برای فرمت‌دهی استفاده کنید.",
        reply_markup=back_keyboard()
    )
    await state.set_state(BroadcastStates.waiting_for_message)

@dp.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    """پردازش پیام همگانی و تایید"""
    if message.text == "🔙 بازگشت":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=admin_keyboard())
        return
    
    await state.update_data(broadcast_message=message.text)
    
    await message.answer(
        f"📋 <b>پیش‌نمایش پیام:</b>\n\n{message.text}\n\n"
        f"✅ آیا از ارسال این پیام به همه کاربران اطمینان دارید؟",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ بله، ارسال کن"), 
                 KeyboardButton(text="❌ خیر، لغو کن")]
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(BroadcastStates.waiting_for_confirmation)

@dp.message(BroadcastStates.waiting_for_confirmation)
async def confirm_broadcast(message: types.Message, state: FSMContext):
    """تایید نهایی و ارسال پیام همگانی"""
    if message.text == "❌ خیر، لغو کن":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=admin_keyboard())
        return
    
    if message.text != "✅ بله، ارسال کن":
        await message.answer("لطفا یکی از گزینه‌ها را انتخاب کنید.")
        return
    
    data = await state.get_data()
    broadcast_message = data.get('broadcast_message', '')
    
    if not broadcast_message:
        await message.answer("پیامی یافت نشد!")
        await state.clear()
        return
    
    # اطلاع به ادمین درباره شروع
    processing_msg = await message.answer(
        "🔄 در حال ارسال پیام به کاربران... لطفا منتظر بمانید.",
        reply_markup=None
    )
    
    # ارسال پیام همگانی
    sent, failed = await send_broadcast_to_all_users(
        broadcast_message, 
        message.from_user.id
    )
    
    # گزارش نتیجه
    await processing_msg.delete()
    await message.answer(
        f"✅ <b>پیام همگانی ارسال شد!</b>\n\n"
        f"📊 آمار:\n"
        f"• ✅ ارسال موفق: {sent} کاربر\n"
        f"• ❌ ارسال ناموفق: {failed} کاربر\n"
        f"• 📈 مجموع: {sent + failed} کاربر",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard()
    )
    
    await state.clear()

# ==================== هندلر هدیه همگانی ====================
@dp.message(F.text == "🎁 هدیه همگانی")
async def start_gift(message: types.Message, state: FSMContext):
    """شروع هدیه همگانی"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ دسترسی denied!")
        return
    
    await message.answer(
        "🎁 لطفا نوع هدیه را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💰 سکه"), KeyboardButton(text="💎 جم")],
                [KeyboardButton(text="🪙 ZP"), KeyboardButton(text="🔙 بازگشت")]
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(GiftStates.waiting_for_type)

@dp.message(GiftStates.waiting_for_type)
async def process_gift_type(message: types.Message, state: FSMContext):
    """پردازش نوع هدیه"""
    if message.text == "🔙 بازگشت":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=admin_keyboard())
        return
    
    gift_types = {"💰 سکه": "coin", "💎 جم": "gem", "🪙 ZP": "zp"}
    
    if message.text not in gift_types:
        await message.answer("لطفا یکی از گزینه‌های معتبر را انتخاب کنید.")
        return
    
    await state.update_data(gift_type=gift_types[message.text])
    
    await message.answer(
        f"💰 لطفا مقدار {message.text} را وارد کنید:",
        reply_markup=back_keyboard()
    )
    await state.set_state(GiftStates.waiting_for_amount)

@dp.message(GiftStates.waiting_for_amount)
async def process_gift_amount(message: types.Message, state: FSMContext):
    """پردازش مقدار هدیه و ارسال"""
    if message.text == "🔙 بازگشت":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=admin_keyboard())
        return
    
    try:
        amount = int(message.text)
        if amount <= 0:
            await message.answer("مقدار باید مثبت باشد!")
            return
        if amount > 1000000:
            await message.answer("مقدار خیلی بزرگ است! حداکثر ۱,۰۰۰,۰۰۰")
            return
    except ValueError:
        await message.answer("لطفا یک عدد معتبر وارد کنید!")
        return
    
    data = await state.get_data()
    gift_type = data.get('gift_type')
    
    # اطلاع به ادمین
    processing_msg = await message.answer(
        f"🔄 در حال افزودن {amount} {gift_type} به همه کاربران...",
        reply_markup=None
    )
    
    # به روزرسانی همه کاربران
    c = db.execute('SELECT user_id FROM users')
    users = c.fetchall()
    
    updated_count = 0
    for user_row in users:
        user_id = user_row['user_id']
        
        if gift_type == 'coin':
            success = update_user_coins(user_id, amount)
        elif gift_type == 'gem':
            success = update_user_gems(user_id, amount)
        elif gift_type == 'zp':
            success = update_user_zp(user_id, amount)
        else:
            success = False
        
        if success:
            updated_count += 1
    
    await processing_msg.delete()
    await message.answer(
        f"✅ <b>هدیه همگانی توزیع شد!</b>\n\n"
        f"🎁 نوع: {gift_type}\n"
        f"💰 مقدار: {amount:,}\n"
        f"👥 کاربران به‌روز شده: {updated_count}",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard()
    )
    
    await state.clear()

# ==================== سایر هندلرها ====================
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
