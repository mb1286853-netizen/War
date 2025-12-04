"""
🔄 سیستم Keep-Alive برای Railway
برای جلوگیری از خوابیدن ربات
"""

from flask import Flask, jsonify
import threading
import requests
import time
import os
import logging

app = Flask(__name__)

# تنظیمات
KEEP_ALIVE_URL = os.getenv("KEEP_ALIVE_URL", "")
PORT = int(os.getenv("PORT", 8080))

@app.route('/')
def home():
    """صفحه اصلی برای health check"""
    return jsonify({
        "status": "online",
        "service": "Warzone Bot",
        "timestamp": time.time()
    })

@app.route('/health')
def health():
    """endpoint برای health check Railway"""
    return jsonify({"status": "healthy"}), 200

@app.route('/keep-alive')
def keep_alive():
    """endpoint برای فعال نگه داشتن"""
    return jsonify({"message": "Keep-alive triggered"}), 200

def ping_self():
    """پینگ کردن خود برای فعال ماندن"""
    if KEEP_ALIVE_URL:
        try:
            response = requests.get(KEEP_ALIVE_URL, timeout=10)
            logging.info(f"✅ Self-ping: {response.status_code}")
        except Exception as e:
            logging.error(f"❌ Self-ping failed: {e}")

def start_ping_loop():
    """شروع حلقه پینگ خودکار"""
    def loop():
        while True:
            ping_self()
            time.sleep(300)  # هر 5 دقیقه
    
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # شروع حلقه پینگ
    start_ping_loop()
    
    # اجرای Flask
    app.run(host='0.0.0.0', port=PORT)
