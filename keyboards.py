from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import PRICES, SUBSCRIPTION_NAMES

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🔑 Активировать ключ", callback_data="activate_key")],
        [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_subscription")],
        [InlineKeyboardButton(text="🎁 Промокод", callback_data="use_promo")],  # Новое
        [InlineKeyboardButton(text="📥 Скачать клиент", callback_data="download_client")],
        [InlineKeyboardButton(text="💳 Мои платежи", callback_data="my_payments")],  # Новое
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help"),
         InlineKeyboardButton(text="📢 Новости", url="https://t.me/your_channel")]
    ])
    return keyboard

def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Кнопка назад в меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="main_menu")]
    ])

def subscription_keyboard() -> InlineKeyboardMarkup:
    """Меню покупки подписки"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⏱ 1 день — {PRICES['1_day']}₽", callback_data="buy_1_day")],
        [InlineKeyboardButton(text=f"📅 14 дней — {PRICES['14_days']}₽", callback_data="buy_14_days")],
        [InlineKeyboardButton(text=f"📆 30 дней — {PRICES['30_days']}₽", callback_data="buy_30_days")],
        [InlineKeyboardButton(text=f"♾ Навсегда — {PRICES['forever']}₽", callback_data="buy_forever")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])
    return keyboard

def payment_keyboard(sub_type: str) -> InlineKeyboardMarkup:
    """Меню оплаты"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатил(а)", callback_data=f"paid_{sub_type}")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="buy_subscription")]
    ])
    return keyboard

def cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
    ])

# ========== АДМИН КЛАВИАТУРЫ ==========

def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Админ меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="🔑 Ключи", callback_data="admin_keys")],
        [InlineKeyboardButton(text="💰 Платежи", callback_data="admin_payments")],
        [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="◀️ В меню пользователя", callback_data="main_menu")]
    ])
    return keyboard

def admin_users_keyboard() -> InlineKeyboardMarkup:
    """Меню управления пользователями"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_find_user")],
        [InlineKeyboardButton(text="📋 Список с подпиской", callback_data="admin_users_sub")],
        [InlineKeyboardButton(text="🚫 Забаненные", callback_data="admin_users_banned")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")]
    ])
    return keyboard

def admin_keys_keyboard() -> InlineKeyboardMarkup:
    """Меню управления ключами"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать ключ", callback_data="admin_create_key")],
        [InlineKeyboardButton(text="📋 Все ключи", callback_data="admin_all_keys")],
        [InlineKeyboardButton(text="✅ Неиспользованные", callback_data="admin_unused_keys")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")]
    ])
    return keyboard

def key_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа ключа"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="gen_key_1_day")],
        [InlineKeyboardButton(text="14 дней", callback_data="gen_key_14_days")],
        [InlineKeyboardButton(text="30 дней", callback_data="gen_key_30_days")],
        [InlineKeyboardButton(text="Навсегда", callback_data="gen_key_forever")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_keys")]
    ])
    return keyboard

def user_manage_keyboard(user_id: int, is_banned: bool, has_sub: bool) -> InlineKeyboardMarkup:
    """Управление пользователем"""
    buttons = []
    
    if is_banned:
        buttons.append([InlineKeyboardButton(text="✅ Разбанить", callback_data=f"unban_{user_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="🚫 Забанить", callback_data=f"ban_{user_id}")])
    
    if has_sub:
        buttons.append([InlineKeyboardButton(text="❌ Забрать подписку", callback_data=f"remove_sub_{user_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="➕ Выдать подписку", callback_data=f"give_sub_{user_id}")])
    
    buttons.append([InlineKeyboardButton(text="📜 История действий", callback_data=f"user_logs_{user_id}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def give_sub_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Выбор подписки для выдачи"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data=f"give_1_day_{user_id}")],
        [InlineKeyboardButton(text="14 дней", callback_data=f"give_14_days_{user_id}")],
        [InlineKeyboardButton(text="30 дней", callback_data=f"give_30_days_{user_id}")],
        [InlineKeyboardButton(text="Навсегда", callback_data=f"give_forever_{user_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"manage_user_{user_id}")]
    ])
    return keyboard

def payment_confirm_keyboard(payment_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Подтверждение платежа"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_pay_{payment_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_pay_{payment_id}")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data=f"manage_user_{user_id}")]
    ])
    return keyboard