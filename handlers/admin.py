from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from database import db
from keyboards import (
    admin_menu_keyboard, admin_users_keyboard, admin_keys_keyboard,
    key_type_keyboard, user_manage_keyboard, give_sub_keyboard,
    back_to_menu_keyboard
)
from config import ADMIN_IDS, SUBSCRIPTION_NAMES

router = Router()

class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_ban_reason = State()
    waiting_broadcast = State()

# Проверка на админа
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ========== АДМИН МЕНЮ ==========

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели!")
        return
    
    await message.answer(
        "🔧 <b>Админ-панель Raven Client</b>\n\n"
        "Выберите раздел:",
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_menu")
async def callback_admin_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!")
        return
    
    await state.clear()
    await callback.message.edit_text(
        "🔧 <b>Админ-панель Raven Client</b>\n\n"
        "Выберите раздел:",
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML"
    )

# ========== СТАТИСТИКА ==========

@router.callback_query(F.data == "admin_stats")
async def callback_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    stats = db.get_stats()
    
    text = (
        "📊 <b>Статистика Raven Client</b>\n\n"
        f"<b>👥 Пользователи:</b>\n"
        f"├ Всего: {stats['total_users']}\n"
        f"├ С подпиской: {stats['with_subscription']}\n"
        f"├ Без подписки: {stats['without_subscription']}\n"
        f"├ Забанено: {stats['banned']}\n"
        f"└ Сегодня: +{stats['registered_today']}\n\n"
        f"<b>🔑 Ключи:</b>\n"
        f"├ Всего: {stats['total_keys']}\n"
        f"├ Использовано: {stats['used_keys']}\n"
        f"└ Свободно: {stats['unused_keys']}\n\n"
        f"<b>💰 Финансы:</b>\n"
        f"├ Общий доход: {stats['total_revenue']}₽\n"
        f"└ Ожидает оплат: {stats['pending_payments']}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML"
    )

# ========== ПОЛЬЗОВАТЕЛИ ==========

@router.callback_query(F.data == "admin_users")
async def callback_admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        "👥 <b>Управление пользователями</b>\n\n"
        "Выберите действие:",
        reply_markup=admin_users_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_find_user")
async def callback_find_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите Telegram ID пользователя:",
        reply_markup=back_to_menu_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_user_id)

@router.message(AdminStates.waiting_user_id)
async def process_user_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_id = int(message.text.strip())
    except:
        await message.answer("❌ Введите корректный ID!")
        return
    
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Пользователь не найден!")
        return
    
    await state.clear()
    await show_user_info(message, user)

async def show_user_info(message: Message, user: dict):
    sub_info = db.get_subscription_info(user['user_id'])
    
    if sub_info and sub_info['active']:
        if sub_info['type'] == 'forever':
            sub_text = "♾ Навсегда"
        else:
            sub_text = f"✅ {sub_info['days_left']} дней"
    else:
        sub_text = "❌ Нет"
    
    ban_text = "🚫 Да" if user['is_banned'] else "✅ Нет"
    reg_date = datetime.fromisoformat(user['registered_at']).strftime("%d.%m.%Y %H:%M")
    
    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"👤 Username: @{user['username'] or 'Нет'}\n"
        f"🎮 Никнейм: {user['nickname']}\n"
        f"🔐 Пароль: <code>{user['password']}</code>\n\n"
        f"📅 Регистрация: {reg_date}\n"
        f"💰 Оплачено: {user['total_paid']}₽\n"
        f"📦 Подписка: {sub_text}\n"
        f"🚫 Бан: {ban_text}\n"
        f"🔑 Ключ: {user['activated_key'] or 'Нет'}"
    )
    
    has_sub = sub_info and sub_info['active']
    
    await message.answer(
        text,
        reply_markup=user_manage_keyboard(user['user_id'], user['is_banned'], has_sub),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("manage_user_"))
async def callback_manage_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    user_id = int(callback.data.replace("manage_user_", ""))
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден!")
        return
    
    sub_info = db.get_subscription_info(user['user_id'])
    
    if sub_info and sub_info['active']:
        if sub_info['type'] == 'forever':
            sub_text = "♾ Навсегда"
        else:
            sub_text = f"✅ {sub_info['days_left']} дней"
    else:
        sub_text = "❌ Нет"
    
    ban_text = "🚫 Да" if user['is_banned'] else "✅ Нет"
    reg_date = datetime.fromisoformat(user['registered_at']).strftime("%d.%m.%Y %H:%M")
    
    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"👤 Username: @{user['username'] or 'Нет'}\n"
        f"🎮 Никнейм: {user['nickname']}\n"
        f"🔐 Пароль: <code>{user['password']}</code>\n\n"
        f"📅 Регистрация: {reg_date}\n"
        f"💰 Оплачено: {user['total_paid']}₽\n"
        f"📦 Подписка: {sub_text}\n"
        f"🚫 Бан: {ban_text}\n"
        f"🔑 Ключ: {user['activated_key'] or 'Нет'}"
    )
    
    has_sub = sub_info and sub_info['active']
    
    await callback.message.edit_text(
        text,
        reply_markup=user_manage_keyboard(user['user_id'], user['is_banned'], has_sub),
        parse_mode="HTML"
    )

# Бан пользователя
@router.callback_query(F.data.startswith("ban_"))
async def callback_ban_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    user_id = int(callback.data.replace("ban_", ""))
    await state.update_data(ban_user_id=user_id)
    
    await callback.message.edit_text(
        "🚫 <b>Бан пользователя</b>\n\n"
        "Введите причину бана:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_ban_reason)

@router.message(AdminStates.waiting_ban_reason)
async def process_ban_reason(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    user_id = data['ban_user_id']
    reason = message.text.strip()
    
    db.ban_user(user_id, reason)
    
    await state.clear()
    await message.answer(f"✅ Пользователь {user_id} забанен!\nПричина: {reason}")
    
    # Уведомляем пользователя
    try:
        await message.bot.send_message(
            user_id,
            f"🚫 <b>Вы были заблокированы!</b>\n\n"
            f"📝 Причина: {reason}",
            parse_mode="HTML"
        )
    except:
        pass

# Разбан пользователя
@router.callback_query(F.data.startswith("unban_"))
async def callback_unban_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    user_id = int(callback.data.replace("unban_", ""))
    db.unban_user(user_id)
    
    await callback.answer("✅ Пользователь разбанен!")
    
    # Обновляем информацию
    user = db.get_user(user_id)
    sub_info = db.get_subscription_info(user_id)
    has_sub = sub_info and sub_info['active']
    
    await callback.message.edit_reply_markup(
        reply_markup=user_manage_keyboard(user_id, False, has_sub)
    )
    
    # Уведомляем пользователя
    try:
        await callback.bot.send_message(
            user_id,
            "✅ <b>Вы были разблокированы!</b>\n\n"
            "Можете продолжить использование бота.",
            parse_mode="HTML"
        )
    except:
        pass

# Забрать подписку
@router.callback_query(F.data.startswith("remove_sub_"))
async def callback_remove_sub(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    user_id = int(callback.data.replace("remove_sub_", ""))
    db.remove_subscription(user_id)
    
    await callback.answer("✅ Подписка удалена!")
    
    user = db.get_user(user_id)
    await callback.message.edit_reply_markup(
        reply_markup=user_manage_keyboard(user_id, user['is_banned'], False)
    )
    
    try:
        await callback.bot.send_message(
            user_id,
            "❌ <b>Ваша подписка была отозвана администратором.</b>",
            parse_mode="HTML"
        )
    except:
        pass

# Выдать подписку
@router.callback_query(F.data.startswith("give_sub_"))
async def callback_give_sub(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    user_id = int(callback.data.replace("give_sub_", ""))
    
    await callback.message.edit_text(
        "➕ <b>Выдача подписки</b>\n\n"
        "Выберите тип подписки:",
        reply_markup=give_sub_keyboard(user_id),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("give_"))
async def callback_give_sub_type(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    parts = callback.data.split("_")
    
    if parts[1] == "sub":  # give_sub_userID
        return
    
    # give_TYPE_userID (например give_1_day_12345 или give_forever_12345)
    if parts[1] == "forever":
        sub_type = "forever"
        user_id = int(parts[2])
        days = None
    else:
        sub_type = f"{parts[1]}_{parts[2]}"  # 1_day, 14_days, 30_days
        user_id = int(parts[3])
        days_map = {'1_day': 1, '14_days': 14, '30_days': 30}
        days = days_map.get(sub_type)
    
    if sub_type == 'forever':
        db.add_subscription(user_id, 'forever')
    else:
        db.add_subscription(user_id, sub_type, days)
    
    await callback.answer("✅ Подписка выдана!")
    
    user = db.get_user(user_id)
    await callback.message.edit_text(
        f"✅ Пользователю {user['nickname']} выдана подписка: {SUBSCRIPTION_NAMES.get(sub_type, sub_type)}",
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML"
    )
    
    try:
        await callback.bot.send_message(
            user_id,
            f"🎉 <b>Вам выдана подписка!</b>\n\n"
            f"📦 Тип: {SUBSCRIPTION_NAMES.get(sub_type, sub_type)}",
            parse_mode="HTML"
        )
    except:
        pass

# Список с подпиской
@router.callback_query(F.data == "admin_users_sub")
async def callback_users_with_sub(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    users = db.get_all_users()
    users_with_sub = [u for u in users if db.has_subscription(u['user_id'])]
    
    if not users_with_sub:
        await callback.message.edit_text(
            "📋 <b>Пользователи с подпиской</b>\n\n"
            "Список пуст.",
            reply_markup=admin_users_keyboard(),
            parse_mode="HTML"
        )
        return
    
    text = "📋 <b>Пользователи с подпиской</b>\n\n"
    
    for i, user in enumerate(users_with_sub[:20], 1):
        sub_info = db.get_subscription_info(user['user_id'])
        if sub_info['type'] == 'forever':
            sub_text = "♾"
        else:
            sub_text = f"{sub_info['days_left']}д"
        
        text += f"{i}. {user['nickname']} (<code>{user['user_id']}</code>) - {sub_text}\n"
    
    if len(users_with_sub) > 20:
        text += f"\n... и ещё {len(users_with_sub) - 20}"
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_users_keyboard(),
        parse_mode="HTML"
    )

# Забаненные
@router.callback_query(F.data == "admin_users_banned")
async def callback_users_banned(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    users = db.get_all_users()
    banned_users = [u for u in users if u['is_banned']]
    
    if not banned_users:
        await callback.message.edit_text(
            "🚫 <b>Забаненные пользователи</b>\n\n"
            "Список пуст.",
            reply_markup=admin_users_keyboard(),
            parse_mode="HTML"
        )
        return
    
    text = "🚫 <b>Забаненные пользователи</b>\n\n"
    
    for i, user in enumerate(banned_users[:20], 1):
        text += f"{i}. {user['nickname']} (<code>{user['user_id']}</code>)\n"
        text += f"   Причина: {user['ban_reason'] or 'Не указана'}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_users_keyboard(),
        parse_mode="HTML"
    )

# ========== КЛЮЧИ ==========

@router.callback_query(F.data == "admin_keys")
async def callback_admin_keys(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        "🔑 <b>Управление ключами</b>\n\n"
        "Выберите действие:",
        reply_markup=admin_keys_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_create_key")
async def callback_create_key(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        "➕ <b>Создание ключа</b>\n\n"
        "Выберите тип ключа:",
        reply_markup=key_type_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("gen_key_"))
async def callback_gen_key(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    key_type = callback.data.replace("gen_key_", "")
    days_map = {'1_day': 1, '14_days': 14, '30_days': 30, 'forever': 0}
    days = days_map.get(key_type, 0)
    
    key = db.generate_key(key_type, days, callback.from_user.id)
    
    await callback.message.edit_text(
        f"✅ <b>Ключ создан!</b>\n\n"
        f"🔑 Ключ: <code>{key}</code>\n"
        f"📦 Тип: {SUBSCRIPTION_NAMES.get(key_type, key_type)}\n"
        f"📅 Дней: {days if days else '∞'}",
        reply_markup=admin_keys_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_all_keys")
async def callback_all_keys(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    keys = db.get_all_keys()
    
    if not keys:
        await callback.message.edit_text(
            "🔑 <b>Все ключи</b>\n\nСписок пуст.",
            reply_markup=admin_keys_keyboard(),
            parse_mode="HTML"
        )
        return
    
    text = "🔑 <b>Все ключи</b>\n\n"
    
    for key in keys[:15]:
        status = "✅" if not key['is_used'] else "❌"
        text += f"{status} <code>{key['key']}</code>\n"
        text += f"   Тип: {key['key_type']}, Дней: {key['days'] or '∞'}\n"
    
    if len(keys) > 15:
        text += f"\n... и ещё {len(keys) - 15}"
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_keys_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_unused_keys")
async def callback_unused_keys(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    keys = db.get_all_keys()
    unused = [k for k in keys if not k['is_used']]
    
    if not unused:
        await callback.message.edit_text(
            "✅ <b>Неиспользованные ключи</b>\n\nСписок пуст.",
            reply_markup=admin_keys_keyboard(),
            parse_mode="HTML"
        )
        return
    
    text = "✅ <b>Неиспользованные ключи</b>\n\n"
    
    for key in unused[:15]:
        text += f"<code>{key['key']}</code>\n"
        text += f"   Тип: {key['key_type']}, Дней: {key['days'] or '∞'}\n"
    
    if len(unused) > 15:
        text += f"\n... и ещё {len(unused) - 15}"
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_keys_keyboard(),
        parse_mode="HTML"
    )

# ========== ПЛАТЕЖИ ==========

@router.callback_query(F.data == "admin_payments")
async def callback_admin_payments(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    payments = db.get_pending_payments()
    
    if not payments:
        await callback.message.edit_text(
            "💰 <b>Ожидающие платежи</b>\n\n"
            "Нет ожидающих платежей.",
            reply_markup=admin_menu_keyboard(),
            parse_mode="HTML"
        )
        return
    
    text = "💰 <b>Ожидающие платежи</b>\n\n"
    
    for p in payments[:10]:
        user = db.get_user(p['user_id'])
        created = datetime.fromisoformat(p['created_at']).strftime("%d.%m %H:%M")
        text += (
            f"#{p['id']} | {user['nickname']} | {p['amount']}₽\n"
            f"   {SUBSCRIPTION_NAMES.get(p['subscription_type'], p['subscription_type'])} | {created}\n\n"
        )
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("confirm_pay_"))
async def callback_confirm_payment(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    payment_id = int(callback.data.replace("confirm_pay_", ""))
    payment = db.confirm_payment(payment_id, callback.from_user.id)
    
    if not payment:
        await callback.answer("❌ Платёж не найден!")
        return
    
    await callback.message.edit_text(
        f"✅ Платёж #{payment_id} подтверждён!",
        parse_mode="HTML"
    )
    
    # Уведомляем пользователя
    try:
        await callback.bot.send_message(
            payment['user_id'],
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"📦 Тариф: {SUBSCRIPTION_NAMES.get(payment['subscription_type'], payment['subscription_type'])}\n"
            f"💰 Сумма: {payment['amount']}₽\n\n"
            f"Спасибо за покупку! 🎉",
            parse_mode="HTML"
        )
    except:
        pass

@router.callback_query(F.data.startswith("reject_pay_"))
async def callback_reject_payment(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    payment_id = int(callback.data.replace("reject_pay_", ""))
    db.reject_payment(payment_id)
    
    await callback.message.edit_text(
        f"❌ Платёж #{payment_id} отклонён!",
        parse_mode="HTML"
    )

# ========== РАССЫЛКА ==========

@router.callback_query(F.data == "admin_broadcast")
async def callback_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        "📨 <b>Рассылка</b>\n\n"
        "Отправьте сообщение для рассылки всем пользователям:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_broadcast)

@router.message(AdminStates.waiting_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await state.clear()
    
    users = db.get_all_users()
    success = 0
    failed = 0
    
    status_msg = await message.answer("📨 Рассылка началась...")
    
    for user in users:
        if user['is_banned']:
            continue
        try:
            await message.copy_to(user['user_id'])
            success += 1
        except:
            failed += 1
    
    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📨 Отправлено: {success}\n"
        f"❌ Ошибок: {failed}",
        parse_mode="HTML"
    )

# История действий пользователя
@router.callback_query(F.data.startswith("user_logs_"))
async def callback_user_logs(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    user_id = int(callback.data.replace("user_logs_", ""))
    logs = db.get_user_logs(user_id, 15)
    
    if not logs:
        await callback.answer("📜 Логов нет")
        return
    
    text = f"📜 <b>Логи пользователя {user_id}</b>\n\n"
    
    for log in logs:
        dt = datetime.fromisoformat(log['created_at']).strftime("%d.%m %H:%M")
        text += f"[{dt}] {log['action']}: {log['details']}\n"
    
    from keyboards import admin_users_keyboard
    await callback.message.edit_text(
        text,
        reply_markup=admin_users_keyboard(),
        parse_mode="HTML"
    )