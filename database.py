import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import secrets
import string

class Database:
    def __init__(self, db_name: str = "raven_client.db"):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                nickname TEXT,
                password TEXT,
                registered_at TEXT,
                subscription_end TEXT,
                subscription_type TEXT,
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT,
                total_paid REAL DEFAULT 0,
                activated_key TEXT,
                hwid TEXT
            )
        ''')
        
        # Таблица ключей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE,
                key_type TEXT,
                days INTEGER,
                created_at TEXT,
                created_by INTEGER,
                used_by INTEGER,
                used_at TEXT,
                is_used INTEGER DEFAULT 0
            )
        ''')
        
        # Таблица платежей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                subscription_type TEXT,
                status TEXT,
                created_at TEXT,
                confirmed_at TEXT,
                confirmed_by INTEGER
            )
        ''')
        
        # Таблица логов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                created_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # ========== ПОЛЬЗОВАТЕЛИ ==========
    
    def user_exists(self, user_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def register_user(self, user_id: int, username: str, nickname: str, password: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (user_id, username, nickname, password, registered_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, nickname, password, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        self.log_action(user_id, "REGISTER", f"Зарегистрирован с ником {nickname}")
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            columns = ['user_id', 'username', 'nickname', 'password', 'registered_at',
                      'subscription_end', 'subscription_type', 'is_banned', 'ban_reason',
                      'total_paid', 'activated_key', 'hwid']
            return dict(zip(columns, row))
        return None
    
    def get_all_users(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        conn.close()
        
        columns = ['user_id', 'username', 'nickname', 'password', 'registered_at',
                  'subscription_end', 'subscription_type', 'is_banned', 'ban_reason',
                  'total_paid', 'activated_key', 'hwid']
        return [dict(zip(columns, row)) for row in rows]
    
    def is_banned(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        return user and user['is_banned'] == 1
    
    def ban_user(self, user_id: int, reason: str = "Не указана"):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = 1, ban_reason = ? WHERE user_id = ?",
                      (reason, user_id))
        conn.commit()
        conn.close()
        self.log_action(user_id, "BAN", f"Забанен. Причина: {reason}")
    
    def unban_user(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = 0, ban_reason = NULL WHERE user_id = ?",
                      (user_id,))
        conn.commit()
        conn.close()
        self.log_action(user_id, "UNBAN", "Разбанен")
    
    def has_subscription(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user or not user['subscription_end']:
            return False
        
        if user['subscription_type'] == 'forever':
            return True
        
        end_date = datetime.fromisoformat(user['subscription_end'])
        return end_date > datetime.now()
    
    def get_subscription_info(self, user_id: int) -> Optional[Dict]:
        user = self.get_user(user_id)
        if not user or not user['subscription_end']:
            return None
        
        if user['subscription_type'] == 'forever':
            return {
                'type': 'forever',
                'end': None,
                'days_left': '∞',
                'active': True
            }
        
        end_date = datetime.fromisoformat(user['subscription_end'])
        days_left = (end_date - datetime.now()).days
        
        return {
            'type': user['subscription_type'],
            'end': end_date,
            'days_left': max(0, days_left),
            'active': days_left >= 0
        }
    
    def add_subscription(self, user_id: int, sub_type: str, days: int = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if sub_type == 'forever':
            end_date = None
        else:
            current_user = self.get_user(user_id)
            if current_user and current_user['subscription_end']:
                try:
                    current_end = datetime.fromisoformat(current_user['subscription_end'])
                    if current_end > datetime.now():
                        end_date = current_end + timedelta(days=days)
                    else:
                        end_date = datetime.now() + timedelta(days=days)
                except:
                    end_date = datetime.now() + timedelta(days=days)
            else:
                end_date = datetime.now() + timedelta(days=days)
        
        cursor.execute('''
            UPDATE users SET subscription_end = ?, subscription_type = ?
            WHERE user_id = ?
        ''', (end_date.isoformat() if end_date else 'forever', sub_type, user_id))
        
        conn.commit()
        conn.close()
        self.log_action(user_id, "SUBSCRIPTION_ADD", f"Добавлена подписка: {sub_type}")
    
    def remove_subscription(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET subscription_end = NULL, subscription_type = NULL
            WHERE user_id = ?
        ''', (user_id,))
        conn.commit()
        conn.close()
        self.log_action(user_id, "SUBSCRIPTION_REMOVE", "Подписка удалена")
    
    def update_total_paid(self, user_id: int, amount: float):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET total_paid = total_paid + ? WHERE user_id = ?
        ''', (amount, user_id))
        conn.commit()
        conn.close()
    
    # ========== КЛЮЧИ ==========
    
    def generate_key(self, key_type: str, days: int, created_by: int) -> str:
        key = 'RAVEN-' + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO keys (key, key_type, days, created_at, created_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (key, key_type, days, datetime.now().isoformat(), created_by))
        conn.commit()
        conn.close()
        
        return key
    
    def get_key(self, key: str) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM keys WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            columns = ['id', 'key', 'key_type', 'days', 'created_at', 'created_by', 
                      'used_by', 'used_at', 'is_used']
            return dict(zip(columns, row))
        return None
    
    def activate_key(self, key: str, user_id: int) -> tuple[bool, str]:
        key_data = self.get_key(key)
        
        if not key_data:
            return False, "❌ Ключ не найден!"
        
        if key_data['is_used']:
            return False, "❌ Ключ уже использован!"
        
        # Активируем ключ
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE keys SET is_used = 1, used_by = ?, used_at = ?
            WHERE key = ?
        ''', (user_id, datetime.now().isoformat(), key))
        
        cursor.execute('''
            UPDATE users SET activated_key = ? WHERE user_id = ?
        ''', (key, user_id))
        
        conn.commit()
        conn.close()
        
        # Добавляем подписку
        if key_data['key_type'] == 'forever':
            self.add_subscription(user_id, 'forever')
        else:
            self.add_subscription(user_id, key_data['key_type'], key_data['days'])
        
        self.log_action(user_id, "KEY_ACTIVATE", f"Активирован ключ: {key}")
        return True, f"✅ Ключ успешно активирован!\n📅 Подписка: {key_data['key_type']} ({key_data['days']} дней)" if key_data['days'] else f"✅ Ключ успешно активирован!\n📅 Подписка: Навсегда"
    
    def get_all_keys(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM keys ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        columns = ['id', 'key', 'key_type', 'days', 'created_at', 'created_by', 
                  'used_by', 'used_at', 'is_used']
        return [dict(zip(columns, row)) for row in rows]
    
    def delete_key(self, key: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM keys WHERE key = ?", (key,))
        conn.commit()
        conn.close()
    
    # ========== ПЛАТЕЖИ ==========
    
    def create_payment(self, user_id: int, amount: float, sub_type: str) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO payments (user_id, amount, subscription_type, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        ''', (user_id, amount, sub_type, datetime.now().isoformat()))
        payment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return payment_id
    
    def get_pending_payments(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM payments WHERE status = 'pending' ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        columns = ['id', 'user_id', 'amount', 'subscription_type', 'status', 
                  'created_at', 'confirmed_at', 'confirmed_by']
        return [dict(zip(columns, row)) for row in rows]
    
    def confirm_payment(self, payment_id: int, admin_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        columns = ['id', 'user_id', 'amount', 'subscription_type', 'status', 
                  'created_at', 'confirmed_at', 'confirmed_by']
        payment = dict(zip(columns, row))
        
        cursor.execute('''
            UPDATE payments SET status = 'confirmed', confirmed_at = ?, confirmed_by = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), admin_id, payment_id))
        
        conn.commit()
        conn.close()
        
        # Добавляем подписку
        days_map = {'1_day': 1, '14_days': 14, '30_days': 30, 'forever': None}
        days = days_map.get(payment['subscription_type'])
        
        if payment['subscription_type'] == 'forever':
            self.add_subscription(payment['user_id'], 'forever')
        else:
            self.add_subscription(payment['user_id'], payment['subscription_type'], days)
        
        self.update_total_paid(payment['user_id'], payment['amount'])
        self.log_action(payment['user_id'], "PAYMENT_CONFIRM", f"Оплата подтверждена: {payment['amount']}₽")
        
        return payment
    
    def reject_payment(self, payment_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE payments SET status = 'rejected' WHERE id = ?", (payment_id,))
        conn.commit()
        conn.close()
    
    # ========== СТАТИСТИКА ==========
    
    def get_stats(self) -> Dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Всего пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # С подпиской
        cursor.execute('''
            SELECT COUNT(*) FROM users 
            WHERE subscription_end IS NOT NULL 
            AND (subscription_type = 'forever' OR subscription_end > ?)
        ''', (datetime.now().isoformat(),))
        with_subscription = cursor.fetchone()[0]
        
        # Забаненных
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
        banned = cursor.fetchone()[0]
        
        # Всего ключей
        cursor.execute("SELECT COUNT(*) FROM keys")
        total_keys = cursor.fetchone()[0]
        
        # Использованных ключей
        cursor.execute("SELECT COUNT(*) FROM keys WHERE is_used = 1")
        used_keys = cursor.fetchone()[0]
        
        # Общий доход
        cursor.execute("SELECT SUM(total_paid) FROM users")
        total_revenue = cursor.fetchone()[0] or 0
        
        # Ожидающих платежей
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
        pending_payments = cursor.fetchone()[0]
        
        # Зарегистрированных сегодня
        today = datetime.now().date().isoformat()
        cursor.execute("SELECT COUNT(*) FROM users WHERE registered_at LIKE ?", (f"{today}%",))
        registered_today = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_users': total_users,
            'with_subscription': with_subscription,
            'without_subscription': total_users - with_subscription,
            'banned': banned,
            'total_keys': total_keys,
            'used_keys': used_keys,
            'unused_keys': total_keys - used_keys,
            'total_revenue': total_revenue,
            'pending_payments': pending_payments,
            'registered_today': registered_today
        }
    
    # ========== ЛОГИ ==========
    
    def log_action(self, user_id: int, action: str, details: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO logs (user_id, action, details, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, action, details, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def get_user_logs(self, user_id: int, limit: int = 10) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM logs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
        ''', (user_id, limit))
        rows = cursor.fetchall()
        conn.close()
        
        columns = ['id', 'user_id', 'action', 'details', 'created_at']
        return [dict(zip(columns, row)) for row in rows]


# Создаём глобальный экземпляр базы данных
db = Database()