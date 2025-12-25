from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from database import db
from keyboards import (
    main_menu_keyboard, back_to_menu_keyboard, subscription_keyboard,
    payment_keyboard, cancel_keyboard
)
from config import PRICES, SUBSCRIPTION_NAMES, PAYMENT_CARD, PAYMENT_SBP, ADMIN_IDS

router = Router()

class RegistrationStates(StatesGroup):
    waiting_nickname = State()
    waiting_password = State()

class ActivateKeyStates(StatesGroup):
    waiting_key = State()

# ========== РЕГИСТРАЦИЯ И СТАРТ ==========

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    # Проверяем бан
    if db.is_banned(user_id):
        user = db.get_user(user_id)
        await message.answer(
            f"🚫 <b>Вы заблокированы!</b>\n\n"
            f"📝 Причина: {user['ban_reason'] or 'Не указана'}\n\n"
            f"Для разблокировки обратитесь к администратору.",
            parse_mode="HTML"
        )
        return
    
    # Проверяем, зарегистрирован ли пользователь
    if db.user_exists(user_id):
        await show_main_menu(message)
    else:
        await message.answer(
            "🦅 <b>Добро пожаловать в Raven Client!</b>\n\n"
            "Для начала работы необходимо зарегистрироваться.\n\n"
            "📝 Введите ваш игровой никнейм:",
            parse_mode="HTML"
        )
        await state.set_state(RegistrationStates.waiting_nickname)

@router.message(RegistrationStates.waiting_nickname)
async def process_nickname(message: Message, state: FSMContext):
    nickname = message.text.strip()
    
    if len(nickname) < 3 or len(nickname) > 20:
        await message.answer("❌ Никнейм должен быть от 3 до 20 символов!")
        return
    
    await state.update_data(nickname=nickname)
    await message.answer(
        f"✅ Никнейм: <b>{nickname}</b>\n\n"
        "🔐 Теперь придумайте пароль (минимум 4 символа):",
        parse_mode="HTML"
    )
    await state.set_state(RegistrationStates.waiting_password)

@router.message(RegistrationStates.waiting_password)
async def process_password(message: Message, state: FSMContext):
    password = message.text.strip()
    
    if len(password) < 4:
        await message.answer("❌ Пароль должен быть минимум 4 символа!")
        return
    
    data = await state.get_data()
    nickname = data['nickname']
    
    # Регистрируем пользователя
    db.register_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        nickname=nickname,
        password=password
    )
    
    await state.clear()
    
    await message.answer(
        f"✅ <b>Регистрация успешна!</b>\n\n"
        f"👤 Никнейм: {nickname}\n"
        f"🔐 Пароль: {password}\n\n"
        f"⚠️ Сохраните эти данные!",
        parse_mode="HTML"
    )
    
    await show_main_menu(message)

# ========== ГЛАВНОЕ МЕНЮ ==========

async def show_main_menu(message: Message):
    user = db.get_user(message.from_user.id)
    sub_info = db.get_subscription_info(message.from_user.id)
    
    if sub_info and sub_info['active']:
        if sub_info['type'] == 'forever':
            sub_text = "✅ Подписка: <b>Навсегда</b>"
        else:
            sub_text = f"✅ Подписка: <b>{sub_info['days_left']} дн.</b>"
    else:
        sub_text = "❌ Подписка: <b>Отсутствует</b>"
    
    text = (
        f"🦅 <b>Raven Client</b>\n\n"
        f"👤 Привет, <b>{user['nickname']}</b>!\n"
        f"{sub_text}\n\n"
        f"Выберите действие:"
    )
    
    await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    
    if db.is_banned(callback.from_user.id):
        await callback.answer("🚫 Вы заблокированы!", show_alert=True)
        return
    
    user = db.get_user(callback.from_user.id)
    sub_info = db.get_subscription_info(callback.from_user.id)
    
    if sub_info and sub_info['active']:
        if sub_info['type'] == 'forever':
            sub_text = "✅ Подписка: <b>Навсегда</b>"
        else:
            sub_text = f"✅ Подписка: <b>{sub_info['days_left']} дн.</b>"
    else:
        sub_text = "❌ Подписка: <b>Отсутствует</b>"
    
    text = (
        f"🦅 <b>Raven Client</b>\n\n"
        f"👤 Привет, <b>{user['nickname']}</b>!\n"
        f"{sub_text}\n\n"
        f"Выберите действие:"
    )
    
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")

# ========== ПРОФИЛЬ ==========

@router.callback_query(F.data == "profile")
async def callback_profile(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    sub_info = db.get_subscription_info(callback.from_user.id)
    
    # Определяем статус подписки
    if sub_info and sub_info['active']:
        if sub_info['type'] == 'forever':
            sub_status = "♾ Навсегда"
            sub_end = "—"
        else:
            sub_status = f"✅ Активна ({sub_info['days_left']} дн.)"
            sub_end = sub_info['end'].strftime("%d.%m.%Y %H:%M")
    else:
        sub_status = "❌ Отсутствует"
        sub_end = "—"
    
    # Дата регистрации
    reg_date = datetime.fromisoformat(user['registered_at']).strftime("%d.%m.%Y")
    
    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🎮 Никнейм: <code>{user['nickname']}</code>\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"📅 Регистрация: {reg_date}\n\n"
        f"<b>📦 Подписка:</b>\n"
        f"├ Статус: {sub_status}\n"
        f"└ Окончание: {sub_end}\n\n"
        f"💰 Всего оплачено: <b>{user['total_paid']}₽</b>\n"
        f"🔑 Ключ: <code>{user['activated_key'] or 'Не активирован'}</code>"
    )
    
    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")

# ========== АКТИВАЦИЯ КЛЮЧА ==========

@router.callback_query(F.data == "activate_key")
async def callback_activate_key(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔑 <b>Активация ключа</b>\n\n"
        "Введите ключ активации:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ActivateKeyStates.waiting_key)

@router.message(ActivateKeyStates.waiting_key)
async def process_key(message: Message, state: FSMContext):
    key = message.text.strip().upper()
    
    success, result_message = db.activate_key(key, message.from_user.id)
    
    await state.clear()
    await message.answer(result_message, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")

# ========== ПОКУПКА ПОДПИСКИ ==========

@router.callback_query(F.data == "buy_subscription")
async def callback_buy_subscription(callback: CallbackQuery):
    text = (
        "💳 <b>Покупка подписки</b>\n\n"
        "Выберите срок подписки:\n\n"
        f"⏱ <b>1 день</b> — {PRICES['1_day']}₽\n"
        f"📅 <b>14 дней</b> — {PRICES['14_days']}₽\n"
        f"📆 <b>30 дней</b> — {PRICES['30_days']}₽\n"
        f"♾ <b>Навсегда</b> — {PRICES['forever']}₽"
    )
    
    await callback.message.edit_text(text, reply_markup=subscription_keyboard(), parse_mode="HTML")

@router.callback_query(F.data.startswith("buy_"))
async def callback_buy(callback: CallbackQuery):
    sub_type = callback.data.replace("buy_", "")
    
    if sub_type not in PRICES:
        await callback.answer("❌ Неверный тип подписки!")
        return
    
    price = PRICES[sub_type]
    name = SUBSCRIPTION_NAMES[sub_type]
    
    text = (
        f"💳 <b>Оплата подписки</b>\n\n"
        f"📦 Тариф: <b>{name}</b>\n"
        f"💰 Сумма: <b>{price}₽</b>\n\n"
        f"<b>Реквизиты для оплаты:</b>\n"
        f"├ 💳 Карта: <code>{PAYMENT_CARD}</code>\n"
        f"└ 📱 СБП: <code>{PAYMENT_SBP}</code>\n\n"
        f"⚠️ <b>ВАЖНО:</b> В комментарии к платежу укажите ваш ID: <code>{callback.from_user.id}</code>\n\n"
        f"После оплаты нажмите кнопку «Оплатил(а)»"
    )
    
    await callback.message.edit_text(text, reply_markup=payment_keyboard(sub_type), parse_mode="HTML")

@router.callback_query(F.data.startswith("paid_"))
async def callback_paid(callback: CallbackQuery):
    sub_type = callback.data.replace("paid_", "")
    price = PRICES.get(sub_type, 0)
    
    # Создаём платёж
    payment_id = db.create_payment(callback.from_user.id, price, sub_type)
    
    # Уведомляем админов
    user = db.get_user(callback.from_user.id)
    from keyboards import payment_confirm_keyboard
    
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"💰 <b>Новая заявка на оплату!</b>\n\n"
                f"👤 Пользователь: @{callback.from_user.username or 'Нет'}\n"
                f"🎮 Никнейм: {user['nickname']}\n"
                f"🆔 ID: <code>{callback.from_user.id}</code>\n\n"
                f"📦 Тариф: {SUBSCRIPTION_NAMES[sub_type]}\n"
                f"💰 Сумма: {price}₽\n"
                f"🔢 ID платежа: #{payment_id}",
                reply_markup=payment_confirm_keyboard(payment_id, callback.from_user.id),
                parse_mode="HTML"
            )
        except:
            pass
    
    await callback.message.edit_text(
        "✅ <b>Заявка отправлена!</b>\n\n"
        "Ожидайте подтверждения оплаты администратором.\n"
        "Обычно это занимает до 30 минут.\n\n"
        "Вы получите уведомление после подтверждения.",
        reply_markup=back_to_menu_keyboard(),
        parse_mode="HTML"
    )

# ========== СКАЧИВАНИЕ ==========

@router.callback_query(F.data == "download_client")
async def callback_download(callback: CallbackQuery):
    if not db.has_subscription(callback.from_user.id):
        await callback.answer("❌ У вас нет активной подписки!", show_alert=True)
        return
    
    user = db.get_user(callback.from_user.id)
    
    text = (
        "📥 <b>Скачивание Raven Client</b>\n\n"
        f"🎮 Ваш никнейм: <code>{user['nickname']}</code>\n"
        f"🔐 Ваш пароль: <code>{user['password']}</code>\n\n"
        "📎 Ссылка для скачивания:\n"
        "🔗 <a href='https://your-download-link.com'>Скачать Raven Client</a>\n\n"
        "⚠️ Используйте эти данные для авторизации в клиенте."
    )
    
    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML", disable_web_page_preview=True)

# ========== ПОМОЩЬ ==========

@router.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    text = (
        "❓ <b>Помощь</b>\n\n"
        "<b>🔑 Как активировать ключ?</b>\n"
        "Нажмите «Активировать ключ» и введите полученный ключ.\n\n"
        "<b>💳 Как купить подписку?</b>\n"
        "1. Нажмите «Купить подписку»\n"
        "2. Выберите тариф\n"
        "3. Оплатите по реквизитам\n"
        "4. Нажмите «Оплатил(а)»\n"
        "5. Дождитесь подтверждения\n\n"
        "<b>📥 Как скачать клиент?</b>\n"
        "После активации подписки нажмите «Скачать клиент».\n\n"
        "<b>🆘 Возникли проблемы?</b>\n"
        "Напишите администратору: @your_username"
    )
    
    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")