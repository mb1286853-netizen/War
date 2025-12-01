# main.py - قطعی برای Railway
import os
import asyncio
import logging
from aiohttp import web

# تنظیمات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("=" * 60)
print("🎯 WARZONE BOT - RAILWAY SPECIAL EDITION")
print("=" * 60)

# دریافت توکن
TOKEN = os.getenv("TELEGRAM_TOKEN")
if TOKEN:
    print(f"✅ Token loaded: {TOKEN[:15]}...")
else:
    print("⚠️ Running in healthcheck mode")

# ==================== HEALTHCHECK ====================
async def health_check(request):
    """برای Railway Healthcheck"""
    return web.Response(text="OK")

async def start_http_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 8000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"✅ HTTP Server started on port {port}")
    return runner

# ==================== TELEGRAM BOT ====================
async def telegram_bot():
    if not TOKEN:
        return None
    
    try:
        # تست aiogram
        print("🤖 Testing aiogram import...")
        from aiogram import Bot, Dispatcher, types
        
        print("✅ aiogram imported successfully")
        
        # ساخت بات
        bot = Bot(token=TOKEN)
        dp = Dispatcher(bot)
        
        # هندلرها
        @dp.message_handler(commands=['start'])
        async def start_cmd(message: types.Message):
            await message.answer(
                "🎯 **WarZone روی Railway فعال شد!**\n\n"
                "✅ بات کاملاً آنلاین است\n"
                "🚀 میزبانی: Railway\n"
                "⚡ سرعت: بالا\n\n"
                "💡 دستورات:\n"
                "/help - راهنما\n"
                "/test - تست بات",
                parse_mode="Markdown"
            )
            print(f"👤 User {message.from_user.id} started")
        
        @dp.message_handler(commands=['help'])
        async def help_cmd(message: types.Message):
            await message.answer(
                "🆘 **راهنمای WarZone**\n\n"
                "• /start - شروع بات\n"
                "• /help - این راهنما\n"
                "• /test - تست اتصال\n\n"
                "🤖 بات با موفقیت روی Railway اجرا شده!",
                parse_mode="Markdown"
            )
        
        @dp.message_handler(commands=['test'])
        async def test_cmd(message: types.Message):
            import random
            await message.answer(
                f"✅ **تست موفق!**\n"
                f"🎯 شماره تست: {random.randint(1000, 9999)}\n"
                f"⚡ بات فعال است",
                parse_mode="Markdown"
            )
        
        # تست اتصال
        print("🔗 Testing Telegram connection...")
        me = await bot.get_me()
        print(f"✅ Connected to @{me.username} (ID: {me.id})")
        
        return dp
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("📦 Please check requirements.txt")
        return None
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        import traceback
        traceback.print_exc()
        return None

# ==================== MAIN ====================
async def main():
    # شروع HTTP سرور
    print("🌐 Starting HTTP server...")
    http_runner = await start_http_server()
    
    # شروع بات تلگرام
    print("🤖 Starting Telegram bot...")
    dp = await telegram_bot()
    
    if dp:
        print("\n" + "=" * 60)
        print("✅ BOT IS FULLY OPERATIONAL!")
        print("✅ HTTP Server: Running")
        print("✅ Telegram Bot: Connected")
        print("✅ Railway Healthcheck: Active")
        print("=" * 60)
        
        print("\n🔄 Starting message polling...")
        await dp.start_polling()
    else:
        print("\n⚠️ Telegram bot not available")
        print("✅ But HTTP server is running for Railway")
        print("📡 Healthcheck available at: http://localhost:8000/health")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        # برای Railway همیشه اجرا بمان
        import time
        time.sleep(3600)
