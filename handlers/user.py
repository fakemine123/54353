# handlers/user.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from keyboards import main_menu_keyboard, back_to_menu_keyboard, cancel_keyboard

router = Router()

class RegisterStates(StatesGroup):
    waiting_nickname = State()
    waiting_password = State()

# ==================== СТАРТ ====================

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    if db.is_banned(user_id):
        await message.answer("🚫 Вы заблокированы!")
        return
    
    if not db.user_exists(user_id):
        await message.answer(
            "🦅 <b>Добро пожаловать в Raven Client!</b>\n\n"
            "Для начала работы нужно зарегистрироваться.\n\n"
            "Нажмите /register чтобы создать аккаунт."
        )
    else:
        user = db.get_user(user_id)
        nickname = user['nickname'] if user else "Unknown"
        
        sub_info = db.get_subscription_info(user_id)
        if sub_info and sub_info['active']:
            if sub_info['type'] == 'forever':
                sub_text = "♾ Навсегда"
            else:
                sub_text = f"📅 {sub_info['days_left']} дней"
        else:
            sub_text = "❌ Нет подписки"
        
        await message.answer(
            f"🦅 <b>Raven Client</b>\n\n"
            f"👤 Ник: <code>{nickname}</code>\n"
            f"📦 Подписка: {sub_text}\n\n"
            f"Выберите действие:",
            reply_markup=main_menu_keyboard()
        )

# ==================== РЕГИСТРАЦИЯ ====================

@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if db.user_exists(user_id):
        await message.answer(
            "❌ Вы уже зарегистрированы!\n\n"
            "Используйте /start для входа в меню."
        )
        return
    
    await message.answer(
        "📝 <b>Регистрация</b>\n\n"
        "Придумайте никнейм для входа в клиент.\n"
        "• От 3 до 16 символов\n"
        "• Только буквы, цифры и _\n\n"
        "✏️ Введите никнейм:",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(RegisterStates.waiting_nickname)

@router.message(RegisterStates.waiting_nickname)
async def process_nickname(message: Message, state: FSMContext):
    nickname = message.text.strip()
    
    # Валидация ника
    if len(nickname) < 3 or len(nickname) > 16:
        await message.answer("❌ Никнейм должен быть от 3 до 16 символов!")
        return
    
    import re
    if not re.match(r'^[a-zA-Z0-9_]+$', nickname):
        await message.answer("❌ Никнейм может содержать только буквы, цифры и _")
        return
    
    # Проверка уникальности
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE LOWER(nickname) = LOWER(?)", (nickname,))
    if cursor.fetchone():
        conn.close()
        await message.answer("❌ Этот никнейм уже занят! Выберите другой.")
        return
    conn.close()
    
    await state.update_data(nickname=nickname)
    
    await message.answer(
        f"✅ Никнейм <code>{nickname}</code> свободен!\n\n"
        "🔑 Теперь придумайте пароль:\n"
        "• Минимум 6 символов\n"
        "• Используйте буквы и цифры",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(RegisterStates.waiting_password)

@router.message(RegisterStates.waiting_password)
async def process_password(message: Message, state: FSMContext):
    password = message.text.strip()
    
    # Валидация пароля
    if len(password) < 6:
        await message.answer("❌ Пароль должен быть минимум 6 символов!")
        return
    
    data = await state.get_data()
    nickname = data['nickname']
    
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Регистрируем пользователя
    # ⬇️ ЗДЕСЬ СОХРАНЯЕТСЯ НИК КОТОРЫЙ ПОТОМ ПОПАДЁТ В ИГРУ!
    db.register_user(user_id, username, nickname, password)
    
    await state.clear()
    
    # Удаляем сообщение с паролем
    try:
        await message.delete()
    except:
        pass
    
    await message.answer(
        f"✅ <b>Регистрация успешна!</b>\n\n"
        f"👤 Ваш никнейм: <code>{nickname}</code>\n\n"
        f"⚠️ <i>Сообщение с паролем удалено в целях безопасности.</i>\n\n"
        f"📝 <b>Данные для входа в лаунчер:</b>\n"
        f"• Логин: <code>{nickname}</code>\n"
        f"• Пароль: тот что вы ввели\n\n"
        f"💡 Теперь купите подписку или активируйте ключ!",
        reply_markup=main_menu_keyboard()
    )

# ==================== ПРОФИЛЬ ====================

@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Профиль не найден!", show_alert=True)
        return
    
    nickname = user['nickname']
    registered_at = user['registered_at'][:10] if user['registered_at'] else "?"
    
    sub_info = db.get_subscription_info(user_id)
    if sub_info and sub_info['active']:
        if sub_info['type'] == 'forever':
            sub_text = "♾ Навсегда"
            sub_end = "—"
        else:
            sub_text = f"📅 {sub_info['days_left']} дней"
            sub_end = str(sub_info['end'])[:10] if sub_info['end'] else "?"
    else:
        sub_text = "❌ Нет подписки"
        sub_end = "—"
    
    hwid_status = "✅ Привязан" if user['hwid'] else "❌ Не привязан"
    
    await callback.message.edit_text(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🏷 Никнейм: <code>{nickname}</code>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📅 Регистрация: {registered_at}\n\n"
        f"📦 <b>Подписка:</b> {sub_text}\n"
        f"📆 Действует до: {sub_end}\n\n"
        f"🖥 HWID: {hwid_status}\n\n"
        f"<i>💡 Никнейм <code>{nickname}</code> будет отображаться в игре!</i>",
        reply_markup=back_to_menu_keyboard()
    )
    await callback.answer()

# ==================== ГЛАВНОЕ МЕНЮ ====================

@router.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.message.edit_text(
            "❌ Профиль не найден!\n\nИспользуйте /register"
        )
        return
    
    nickname = user['nickname']
    
    sub_info = db.get_subscription_info(user_id)
    if sub_info and sub_info['active']:
        if sub_info['type'] == 'forever':
            sub_text = "♾ Навсегда"
        else:
            sub_text = f"📅 {sub_info['days_left']} дней"
    else:
        sub_text = "❌ Нет подписки"
    
    await callback.message.edit_text(
        f"🦅 <b>Raven Client</b>\n\n"
        f"👤 Ник: <code>{nickname}</code>\n"
        f"📦 Подписка: {sub_text}\n\n"
        f"Выберите действие:",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer()

# ==================== АКТИВАЦИЯ КЛЮЧА ====================

class KeyStates(StatesGroup):
    waiting_key = State()

@router.callback_query(F.data == "activate_key")
async def activate_key_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔑 <b>Активация ключа</b>\n\n"
        "Введите ваш ключ активации:\n"
        "<i>Пример: RAVEN-XXXX-XXXX-XXXX</i>",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(KeyStates.waiting_key)
    await callback.answer()

@router.message(KeyStates.waiting_key)
async def process_key(message: Message, state: FSMContext):
    key = message.text.strip().upper()
    user_id = message.from_user.id
    
    success, result_msg = db.activate_key(key, user_id)
    
    await state.clear()
    
    if success:
        await message.answer(
            f"{result_msg}\n\n"
            f"🎮 Теперь можете запускать лаунчер!",
            reply_markup=main_menu_keyboard()
        )
    else:
        await message.answer(
            f"{result_msg}",
            reply_markup=main_menu_keyboard()
        )

# ==================== ПОМОЩЬ ====================

@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    await callback.message.edit_text(
        "❓ <b>Помощь</b>\n\n"
        "<b>Как начать использовать Raven Client:</b>\n\n"
        "1️⃣ Зарегистрируйтесь: /register\n"
        "2️⃣ Купите подписку или активируйте ключ\n"
        "3️⃣ Скачайте лаунчер\n"
        "4️⃣ Войдите используя никнейм и пароль\n"
        "5️⃣ Запустите игру!\n\n"
        "<b>Команды:</b>\n"
        "/start - Главное меню\n"
        "/register - Регистрация\n"
        "/profile - Ваш профиль\n\n"
        "❓ Вопросы? Пишите: @your_support",
        reply_markup=back_to_menu_keyboard()
    )
    await callback.answer()

# ==================== СКАЧАТЬ КЛИЕНТ ====================

@router.callback_query(F.data == "download_client")
async def download_client(callback: CallbackQuery):
    await callback.message.edit_text(
        "📥 <b>Скачать Raven Client</b>\n\n"
        "🔗 <b>Лаунчер:</b>\n"
        "• <a href='https://your-link.com/launcher.exe'>Windows (.exe)</a>\n\n"
        "📋 <b>Инструкция:</b>\n"
        "1. Скачайте лаунчер\n"
        "2. Запустите от имени администратора\n"
        "3. Введите никнейм и пароль\n"
        "4. Нажмите 'Запустить игру'\n\n"
        "⚠️ <i>Отключите антивирус перед запуском!</i>",
        reply_markup=back_to_menu_keyboard(),
        disable_web_page_preview=True
    )
    await callback.answer()
