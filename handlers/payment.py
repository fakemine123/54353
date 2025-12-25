from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from database import db
from keyboards import (
    subscription_keyboard, payment_keyboard, back_to_menu_keyboard,
    payment_confirm_keyboard
)
from config import PRICES, SUBSCRIPTION_NAMES, PAYMENT_CARD, PAYMENT_SBP, ADMIN_IDS

router = Router()

class PaymentStates(StatesGroup):
    waiting_payment_proof = State()

# ========== ПОКУПКА ПОДПИСКИ ==========

@router.callback_query(F.data == "buy_subscription")
async def callback_buy_subscription(callback: CallbackQuery):
    """Меню выбора подписки"""
    
    # Проверяем бан
    if db.is_banned(callback.from_user.id):
        await callback.answer("🚫 Вы заблокированы!", show_alert=True)
        return
    
    text = (
        "💳 <b>Покупка подписки Raven Client</b>\n\n"
        "Выберите подходящий тариф:\n\n"
        f"⏱ <b>1 день</b> — {PRICES['1_day']}₽\n"
        f"   └ Идеально для теста\n\n"
        f"📅 <b>14 дней</b> — {PRICES['14_days']}₽\n"
        f"   └ Выгодно для начала\n\n"
        f"📆 <b>30 дней</b> — {PRICES['30_days']}₽\n"
        f"   └ Оптимальный выбор\n\n"
        f"♾ <b>Навсегда</b> — {PRICES['forever']}₽\n"
        f"   └ Максимальная выгода!"
    )
    
    await callback.message.edit_text(
        text, 
        reply_markup=subscription_keyboard(), 
        parse_mode="HTML"
    )

@router.callback_query(F.data.in_({"buy_1_day", "buy_14_days", "buy_30_days", "buy_forever"}))
async def callback_select_subscription(callback: CallbackQuery, state: FSMContext):
    """Выбор конкретной подписки"""
    
    sub_type = callback.data.replace("buy_", "")
    
    if sub_type not in PRICES:
        await callback.answer("❌ Неверный тип подписки!", show_alert=True)
        return
    
    price = PRICES[sub_type]
    name = SUBSCRIPTION_NAMES[sub_type]
    
    # Сохраняем выбор в состояние
    await state.update_data(selected_sub=sub_type, selected_price=price)
    
    text = (
        f"💳 <b>Оформление подписки</b>\n\n"
        f"📦 Тариф: <b>{name}</b>\n"
        f"💰 Стоимость: <b>{price}₽</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>💳 Реквизиты для оплаты:</b>\n\n"
        f"🏦 <b>Карта:</b>\n"
        f"<code>{PAYMENT_CARD}</code>\n\n"
        f"📱 <b>СБП (по номеру):</b>\n"
        f"<code>{PAYMENT_SBP}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚠️ <b>ВАЖНО!</b>\n"
        f"В комментарии к переводу укажите:\n"
        f"<code>{callback.from_user.id}</code>\n\n"
        f"После оплаты нажмите кнопку ниже 👇"
    )
    
    await callback.message.edit_text(
        text, 
        reply_markup=payment_keyboard(sub_type), 
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("paid_"))
async def callback_payment_done(callback: CallbackQuery, state: FSMContext):
    """Пользователь нажал "Оплатил" """
    
    sub_type = callback.data.replace("paid_", "")
    price = PRICES.get(sub_type, 0)
    name = SUBSCRIPTION_NAMES.get(sub_type, sub_type)
    
    # Создаём запись о платеже
    payment_id = db.create_payment(callback.from_user.id, price, sub_type)
    
    # Получаем данные пользователя
    user = db.get_user(callback.from_user.id)
    
    # Формируем сообщение для админов
    admin_text = (
        f"💰 <b>НОВАЯ ЗАЯВКА НА ОПЛАТУ!</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Пользователь:</b>\n"
        f"├ Никнейм: {user['nickname']}\n"
        f"├ Username: @{callback.from_user.username or 'Нет'}\n"
        f"├ ID: <code>{callback.from_user.id}</code>\n"
        f"└ Всего оплачено ранее: {user['total_paid']}₽\n\n"
        f"📦 <b>Заказ:</b>\n"
        f"├ Тариф: {name}\n"
        f"├ Сумма: {price}₽\n"
        f"└ ID платежа: #{payment_id}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )
    
    # Отправляем уведомление всем админам
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                admin_text,
                reply_markup=payment_confirm_keyboard(payment_id, callback.from_user.id),
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")
    
    # Отвечаем пользователю
    await callback.message.edit_text(
        f"✅ <b>Заявка на оплату отправлена!</b>\n\n"
        f"📦 Тариф: {name}\n"
        f"💰 Сумма: {price}₽\n"
        f"🔢 Номер заявки: #{payment_id}\n\n"
        f"⏳ Ожидайте подтверждения от администратора.\n"
        f"Обычно это занимает <b>до 30 минут</b>.\n\n"
        f"📬 Вы получите уведомление сразу после подтверждения!",
        reply_markup=back_to_menu_keyboard(),
        parse_mode="HTML"
    )
    
    await state.clear()

# ========== АДМИН: ПОДТВЕРЖДЕНИЕ ПЛАТЕЖЕЙ ==========

@router.callback_query(F.data.startswith("confirm_pay_"))
async def callback_confirm_payment(callback: CallbackQuery):
    """Админ подтверждает платёж"""
    
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    payment_id = int(callback.data.replace("confirm_pay_", ""))
    payment = db.confirm_payment(payment_id, callback.from_user.id)
    
    if not payment:
        await callback.answer("❌ Платёж не найден или уже обработан!", show_alert=True)
        return
    
    user = db.get_user(payment['user_id'])
    name = SUBSCRIPTION_NAMES.get(payment['subscription_type'], payment['subscription_type'])
    
    # Обновляем сообщение у админа
    await callback.message.edit_text(
        f"✅ <b>ПЛАТЁЖ ПОДТВЕРЖДЁН!</b>\n\n"
        f"🔢 ID платежа: #{payment_id}\n"
        f"👤 Пользователь: {user['nickname']} ({payment['user_id']})\n"
        f"📦 Тариф: {name}\n"
        f"💰 Сумма: {payment['amount']}₽\n\n"
        f"✅ Подтвердил: @{callback.from_user.username or callback.from_user.id}\n"
        f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        parse_mode="HTML"
    )
    
    # Уведомляем пользователя
    try:
        sub_info = db.get_subscription_info(payment['user_id'])
        
        if sub_info and sub_info['type'] == 'forever':
            end_text = "♾ Навсегда"
        elif sub_info:
            end_text = f"до {sub_info['end'].strftime('%d.%m.%Y %H:%M')}"
        else:
            end_text = "Активна"
        
        await callback.bot.send_message(
            payment['user_id'],
            f"🎉 <b>Оплата подтверждена!</b>\n\n"
            f"📦 Тариф: <b>{name}</b>\n"
            f"💰 Сумма: <b>{payment['amount']}₽</b>\n"
            f"📅 Подписка: <b>{end_text}</b>\n\n"
            f"Спасибо за покупку! Приятной игры! 🦅",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка уведомления пользователя: {e}")
    
    await callback.answer("✅ Платёж подтверждён!")

@router.callback_query(F.data.startswith("reject_pay_"))
async def callback_reject_payment(callback: CallbackQuery):
    """Админ отклоняет платёж"""
    
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    payment_id = int(callback.data.replace("reject_pay_", ""))
    
    # Получаем данные платежа до отклонения
    payments = db.get_pending_payments()
    payment = next((p for p in payments if p['id'] == payment_id), None)
    
    if not payment:
        await callback.answer("❌ Платёж не найден или уже обработан!", show_alert=True)
        return
    
    db.reject_payment(payment_id)
    
    user = db.get_user(payment['user_id'])
    name = SUBSCRIPTION_NAMES.get(payment['subscription_type'], payment['subscription_type'])
    
    # Обновляем сообщение у админа
    await callback.message.edit_text(
        f"❌ <b>ПЛАТЁЖ ОТКЛОНЁН!</b>\n\n"
        f"🔢 ID платежа: #{payment_id}\n"
        f"👤 Пользователь: {user['nickname']} ({payment['user_id']})\n"
        f"📦 Тариф: {name}\n"
        f"💰 Сумма: {payment['amount']}₽\n\n"
        f"❌ Отклонил: @{callback.from_user.username or callback.from_user.id}\n"
        f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        parse_mode="HTML"
    )
    
    # Уведомляем пользователя
    try:
        await callback.bot.send_message(
            payment['user_id'],
            f"❌ <b>Заявка на оплату отклонена</b>\n\n"
            f"📦 Тариф: {name}\n"
            f"💰 Сумма: {payment['amount']}₽\n\n"
            f"Возможные причины:\n"
            f"• Платёж не найден\n"
            f"• Неверная сумма\n"
            f"• Не указан ID в комментарии\n\n"
            f"Если вы уверены, что оплатили — обратитесь к администратору.",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка уведомления пользователя: {e}")
    
    await callback.answer("❌ Платёж отклонён!")

# ========== ПРОМОКОДЫ (бонус) ==========

class PromoStates(StatesGroup):
    waiting_promo = State()

@router.callback_query(F.data == "use_promo")
async def callback_use_promo(callback: CallbackQuery, state: FSMContext):
    """Использование промокода"""
    
    await callback.message.edit_text(
        "🎁 <b>Промокод</b>\n\n"
        "Введите промокод для получения скидки или бонуса:",
        reply_markup=back_to_menu_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(PromoStates.waiting_promo)

@router.message(PromoStates.waiting_promo)
async def process_promo(message: Message, state: FSMContext):
    """Обработка промокода"""
    
    promo = message.text.strip().upper()
    
    # Здесь можно добавить логику проверки промокодов
    # Пока заглушка
    
    await state.clear()
    await message.answer(
        "❌ Промокод не найден или уже использован.",
        reply_markup=back_to_menu_keyboard(),
        parse_mode="HTML"
    )

# ========== ИСТОРИЯ ПЛАТЕЖЕЙ ПОЛЬЗОВАТЕЛЯ ==========

@router.callback_query(F.data == "my_payments")
async def callback_my_payments(callback: CallbackQuery):
    """История платежей пользователя"""
    
    user_id = callback.from_user.id
    
    # Получаем платежи пользователя из базы
    from database import db
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM payments 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 10
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await callback.message.edit_text(
            "💳 <b>История платежей</b>\n\n"
            "У вас пока нет платежей.",
            reply_markup=back_to_menu_keyboard(),
            parse_mode="HTML"
        )
        return
    
    columns = ['id', 'user_id', 'amount', 'subscription_type', 'status', 
               'created_at', 'confirmed_at', 'confirmed_by']
    payments = [dict(zip(columns, row)) for row in rows]
    
    text = "💳 <b>История платежей</b>\n\n"
    
    status_emoji = {
        'pending': '⏳',
        'confirmed': '✅',
        'rejected': '❌'
    }
    
    for p in payments:
        emoji = status_emoji.get(p['status'], '❓')
        date = datetime.fromisoformat(p['created_at']).strftime("%d.%m.%Y")
        name = SUBSCRIPTION_NAMES.get(p['subscription_type'], p['subscription_type'])
        
        text += f"{emoji} #{p['id']} | {name} | {p['amount']}₽ | {date}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=back_to_menu_keyboard(),
        parse_mode="HTML"
    )