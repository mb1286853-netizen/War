# main.py
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Railway نیاز داره logging به stdout باشه
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    logging.error("❌ BOT_TOKEN not found in environment variables!")
    exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🎮 ربات Warzone فعال شد!")

async def main():
    logging.info("🚀 Starting bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
