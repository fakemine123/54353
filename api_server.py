# api_server.py - API сервер для связи бота и лаунчера
from flask import Flask, request, jsonify
from functools import wraps
import hashlib
import secrets
import time
import sqlite3
from datetime import datetime
import threading

app = Flask(__name__)

# ⚠️ ВАЖНО: Должен совпадать с лаунчером и Node.js!
API_SECRET = "RavenClient_SuperSecret_2024!@#$"
DB_PATH = "raven_client.db"

# Хранилище активных сессий (в памяти)
active_sessions = {}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def generate_api_key():
    """Генерация API ключа"""
    return hashlib.sha256(API_SECRET.encode()).hexdigest()[:32]

def verify_api_key(f):
    """Декоратор проверки API ключа"""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({"success": False, "error": "API key required"}), 401
        
        if api_key != generate_api_key():
            return jsonify({"success": False, "error": "Invalid API key"}), 401
        
        return f(*args, **kwargs)
    return decorated

# ==================== АВТОРИЗАЦИЯ ====================

@app.route('/api/auth/login', methods=['POST'])
@verify_api_key
def login():
    """Авторизация пользователя из лаунчера"""
    data = request.json
    
    nickname = data.get('nickname', '').strip()
    password = data.get('password', '').strip()
    hwid = data.get('hwid', '').strip()
    
    print(f"[LOGIN] Попытка входа: {nickname}")
    
    if not nickname or not password:
        return jsonify({
            "success": False,
            "error": "Никнейм и пароль обязательны!"
        })
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Ищем пользователя по нику (регистронезависимо)
    cursor.execute(
        "SELECT * FROM users WHERE LOWER(nickname) = LOWER(?)",
        (nickname,)
    )
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        print(f"[LOGIN] Пользователь не найден: {nickname}")
        return jsonify({
            "success": False,
            "error": "Пользователь не найден! Зарегистрируйтесь в TG боте."
        })
    
    user = dict(user)
    
    # Проверяем пароль
    if user['password'] != password:
        conn.close()
        print(f"[LOGIN] Неверный пароль для: {nickname}")
        return jsonify({
            "success": False,
            "error": "Неверный пароль!"
        })
    
    # Проверяем бан
    if user['is_banned'] == 1:
        conn.close()
        print(f"[LOGIN] Пользователь забанен: {nickname}")
        return jsonify({
            "success": False,
            "error": f"Аккаунт заблокирован: {user['ban_reason'] or 'Причина не указана'}"
        })
    
    # Проверяем HWID
    if user['hwid'] and user['hwid'] != hwid:
        conn.close()
        print(f"[LOGIN] HWID не совпадает для: {nickname}")
        return jsonify({
            "success": False,
            "error": "Аккаунт привязан к другому устройству!"
        })
    
    # Привязываем HWID если не привязан
    if not user['hwid'] and hwid:
        cursor.execute(
            "UPDATE users SET hwid = ? WHERE user_id = ?",
            (hwid, user['user_id'])
        )
        conn.commit()
        print(f"[HWID] Привязан для {nickname}: {hwid[:16]}...")
    
    # Проверяем подписку
    has_sub = check_subscription(user)
    
    if not has_sub:
        conn.close()
        print(f"[LOGIN] Нет подписки: {nickname}")
        return jsonify({
            "success": False,
            "error": "У вас нет активной подписки! Купите подписку в боте."
        })
    
    # Генерируем токен сессии
    session_token = secrets.token_hex(32)
    session_data = {
        "user_id": user['user_id'],
        "nickname": user['nickname'],  # ⬅️ НИК ИЗ РЕГИСТРАЦИИ!
        "hwid": hwid,
        "created_at": time.time(),
        "expires_at": time.time() + 86400  # 24 часа
    }
    active_sessions[session_token] = session_data
    
    # Логируем вход
    cursor.execute('''
        INSERT INTO logs (user_id, action, details, created_at)
        VALUES (?, 'LAUNCHER_LOGIN', ?, ?)
    ''', (user['user_id'], f"HWID: {hwid[:16]}...", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    # Получаем инфо о подписке
    sub_info = get_subscription_info(user)
    
    print(f"[LOGIN] Успешный вход: {nickname} ({sub_info})")
    
    return jsonify({
        "success": True,
        "session_token": session_token,
        "user": {
            "user_id": user['user_id'],
            "nickname": user['nickname'],  # ⬅️ ЭТОТ НИК ПОПАДЁТ В ИГРУ!
            "subscription": sub_info
        }
    })

@app.route('/api/auth/verify_session', methods=['POST'])
@verify_api_key
def verify_session():
    """Проверка активной сессии"""
    data = request.json
    session_token = data.get('session_token', '')
    hwid = data.get('hwid', '')
    
    if session_token not in active_sessions:
        return jsonify({"success": False, "error": "Сессия не найдена"})
    
    session = active_sessions[session_token]
    
    # Проверяем срок
    if time.time() > session['expires_at']:
        del active_sessions[session_token]
        return jsonify({"success": False, "error": "Сессия истекла"})
    
    # Проверяем HWID
    if session['hwid'] != hwid:
        return jsonify({"success": False, "error": "HWID не совпадает"})
    
    # Проверяем пользователя в БД
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return jsonify({"success": False, "error": "Пользователь не найден"})
    
    user = dict(user)
    
    if user['is_banned'] == 1:
        return jsonify({"success": False, "error": "Аккаунт заблокирован"})
    
    if not check_subscription(user):
        return jsonify({"success": False, "error": "Подписка истекла"})
    
    return jsonify({
        "success": True,
        "user": {
            "user_id": user['user_id'],
            "nickname": user['nickname'],
            "subscription": get_subscription_info(user)
        }
    })

@app.route('/api/auth/logout', methods=['POST'])
@verify_api_key
def logout():
    """Выход из сессии"""
    data = request.json
    session_token = data.get('session_token', '')
    
    if session_token in active_sessions:
        del active_sessions[session_token]
    
    return jsonify({"success": True})

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def check_subscription(user: dict) -> bool:
    """Проверка активности подписки"""
    if not user.get('subscription_end'):
        return False
    
    if user.get('subscription_type') == 'forever':
        return True
    
    if user['subscription_end'] == 'forever':
        return True
    
    try:
        end_date = datetime.fromisoformat(user['subscription_end'])
        return end_date > datetime.now()
    except:
        return False

def get_subscription_info(user: dict) -> dict:
    """Получение информации о подписке"""
    if not user.get('subscription_end'):
        return {"active": False, "type": None, "days_left": 0}
    
    if user.get('subscription_type') == 'forever' or user['subscription_end'] == 'forever':
        return {"active": True, "type": "forever", "days_left": -1}
    
    try:
        end_date = datetime.fromisoformat(user['subscription_end'])
        days_left = (end_date - datetime.now()).days
        return {
            "active": days_left >= 0,
            "type": user.get('subscription_type'),
            "days_left": max(0, days_left),
            "end_date": user['subscription_end']
        }
    except:
        return {"active": False, "type": None, "days_left": 0}

# ==================== HEALTH CHECK ====================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route('/api/stats/online', methods=['GET'])
@verify_api_key
def get_online():
    """Количество онлайн"""
    current_time = time.time()
    # Очищаем истекшие
    expired = [k for k, v in active_sessions.items() if current_time > v['expires_at']]
    for k in expired:
        del active_sessions[k]
    
    return jsonify({
        "success": True,
        "online": len(active_sessions)
    })

# ==================== ОЧИСТКА ====================

def cleanup_sessions():
    """Периодическая очистка сессий"""
    while True:
        time.sleep(3600)  # Каждый час
        current_time = time.time()
        expired = [k for k, v in active_sessions.items() if current_time > v['expires_at']]
        for k in expired:
            del active_sessions[k]
        if expired:
            print(f"[Cleanup] Удалено {len(expired)} истекших сессий")

# ==================== ЗАПУСК ====================

if __name__ == '__main__':
    # Запускаем очистку в фоне
    cleanup_thread = threading.Thread(target=cleanup_sessions, daemon=True)
    cleanup_thread.start()
    
    print("=" * 50)
    print("🦅 Raven Client API Server (Python)")
    print("=" * 50)
    print(f"📡 Адрес: http://0.0.0.0:25567")
    print(f"🔑 API Key: {generate_api_key()}")
    print(f"📁 База данных: {DB_PATH}")
    print("=" * 50)
    
    # ⚠️ ПОРТ 25567 - ДОЛЖЕН СОВПАДАТЬ С ЛАУНЧЕРОМ!
    app.run(host='0.0.0.0', port=25567, debug=False, threaded=True)