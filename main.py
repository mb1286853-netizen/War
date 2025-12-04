"""
🏆 Warzone Bot - Main File
ربات جنگی با ساختار ماژولار
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv

# Import handlers
from handlers.start_handler import register_start_handlers
from handlers.market_handler import register_market_handlers
from handlers.miner_handler import register_miner_handlers
from handlers.attack_handler import register_attack_handlers
from handlers.combo_handler import register_combo_handlers
from handlers.admin_handler import register_admin_handlers

# Import database
from database import Database

# Import keyboards
from keyboards import get_main_keyboard

# ==================== CONFIG ====================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
DEVELOPER_ID = os.getenv("DEVELOPER_ID", "")

# تنظیمات logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# ==================== INITIALIZE ====================
bot = Bot(token=TOKEN)
dp = Dispatcher()
db = Database()

# ذخیره shared instances
dp["bot"] = bot
dp["db"] = db
dp["developer_id"] = DEVELOPER_ID

# ==================== REGISTER HANDLERS ====================
register_start_handlers(dp)
register_market_handlers(dp)
register_miner_handlers(dp)
register_attack_handlers(dp)
register_combo_handlers(dp)
register_admin_handlers(dp)

# ==================== BASIC COMMANDS ====================
@dp.message(CommandStart())
async def start_command(message: Message):
    """دستور /start اصلی"""
    from handlers.start_handler import handle_start
    await handle_start(message, dp["db"])

@dp.message(Command("help"))
async def help_command(message: Message):
    """دستور /help"""
    help_text = """
🎮 **Warzone Bot Help**

📋 **دستورات اصلی:**
/start - شروع بازی
/help - راهنما
/stats - آمار شما
/profile - پروفایل

🎯 **منوها (از کیبورد استفاده کن):**
• پنل جنگجو
• بازار جنگ  
• معدن‌چی
• سیستم ترکیب
• پشتیبانی

👨‍💻 **پشتیبانی:** @{DEVELOPER_ID}
    """.format(DEVELOPER_ID=DEVELOPER_ID or "WarzoneSupport")
    
    await message.answer(help_text, reply_markup=get_main_keyboard())

@dp.message(Command("stats"))
async def stats_command(message: Message):
    """آمار کاربر"""
    user = db.get_user(message.from_user.id)
    if user:
        stats_text = f"""
📊 **آمار شما:**

💰 سکه: {user[3]:,}
💎 جم: {user[4]:,}
🎯 ZP: {user[5]:,}
📈 سطح: {user[6]}
⛏️ ماینر: سطح {user[10]}
        """
        await message.answer(stats_text)
    else:
        await message.answer("⚠️ اول /start رو بزن!")

# ==================== ERROR HANDLER ====================
@dp.errors()
async def error_handler(exception, message: Message):
    """مدیریت خطاها"""
    logger.error(f"Error: {exception}")
    if message:
        await message.answer("⚠️ خطایی رخ داد. دوباره تلاش کن!")

# ==================== KEEP ALIVE FOR RAILWAY ====================
async def keep_alive():
    """فعال نگه داشتن Railway"""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://httpbin.org/get', timeout=5):
                logger.info("✅ Railway keep-alive")
    except:
        pass

# ==================== MAIN FUNCTION ====================
async def main():
    """تابع اصلی اجرا"""
    logger.info("🚀 Starting Warzone Bot...")
    logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # تست اتصال
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot: @{bot_info.username}")
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        return
    
    # Keep-alive background task
    async def keep_alive_task():
        while True:
            await keep_alive()
            await asyncio.sleep(300)  # هر 5 دقیقه
    
    asyncio.create_task(keep_alive_task())
    
    # شروع ربات
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
