"""
مدیریت دیتابیس SQLite
"""

import sqlite3
import os
import logging
import shutil
from datetime import datetime
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "warzone.db"):
        self.db_path = db_path
        self.setup_database()
    
    def setup_database(self):
        """ایجاد جدول‌های اصلی"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # جدول کاربران
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                zone_coin INTEGER DEFAULT 1000,
                zone_gem INTEGER DEFAULT 0,
                zone_point INTEGER DEFAULT 500,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                is_admin BOOLEAN DEFAULT 0,
                miner_level INTEGER DEFAULT 1,
                last_miner_claim INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول موشک‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_missiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                missile_name TEXT,
                quantity INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # جدول ترکیب‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_combos (
                combo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                combo_name TEXT,
                missiles TEXT,
                damage_multiplier REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database setup complete")
    
    def get_connection(self):
        """دریافت اتصال به دیتابیس"""
        return sqlite3.connect(self.db_path)
    
    def get_user(self, user_id: int) -> Optional[Tuple]:
        """دریافت اطلاعات کاربر"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    
    def create_user(self, user_id: int, username: str, full_name: str):
        """ایجاد کاربر جدید"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, full_name) 
            VALUES (?, ?, ?)
        ''', (user_id, username, full_name))
        conn.commit()
        conn.close()
    
    def update_coins(self, user_id: int, amount: int):
        """بروزرسانی سکه کاربر"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET zone_coin = zone_coin + ? WHERE user_id = ?', 
                      (amount, user_id))
        conn.commit()
        conn.close()
    
    def update_gems(self, user_id: int, amount: int):
        """بروزرسانی جم کاربر"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET zone_gem = zone_gem + ? WHERE user_id = ?', 
                      (amount, user_id))
        conn.commit()
        conn.close()
    
    def update_zp(self, user_id: int, amount: int):
        """بروزرسانی ZP کاربر"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET zone_point = zone_point + ? WHERE user_id = ?', 
                      (amount, user_id))
        conn.commit()
        conn.close()
    
    def get_user_missiles(self, user_id: int) -> List[Tuple]:
        """دریافت موشک‌های کاربر"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT missile_name, quantity FROM user_missiles WHERE user_id = ?', 
                      (user_id,))
        missiles = cursor.fetchall()
        conn.close()
        return missiles
    
    def add_missile(self, user_id: int, missile_name: str, quantity: int = 1):
        """اضافه کردن موشک به کاربر"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_missiles (user_id, missile_name, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, missile_name) 
            DO UPDATE SET quantity = quantity + ?
        ''', (user_id, missile_name, quantity, quantity))
        conn.commit()
        conn.close()
    
    def create_backup(self):
        """ایجاد Backup از دیتابیس"""
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{backup_dir}/backup_{timestamp}.db"
        
        shutil.copy2(self.db_path, backup_file)
        logger.info(f"✅ Backup created: {backup_file}")
        return backup_file
