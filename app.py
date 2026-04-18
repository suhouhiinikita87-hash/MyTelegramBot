import os
import telebot
from telebot import types
from flask import Flask
import threading
import json
from datetime import datetime, timedelta
import csv
import io

# --- Токен ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("Переменная TELEGRAM_TOKEN не найдена!")

bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

DATA_FILE = 'finance.json'
REMINDERS_FILE = 'reminders.json'

# Категории
CATEGORIES = {
    'еда': '🍕', 'транспорт': '🚗', 'кофе': '☕', 'развлечения': '🎮',
    'шопинг': '🛍️', 'здоровье': '💊', 'коммунальные': '💡', 'связь': '📱', 'прочее': '📦'
}
CATEGORIES_INCOME = {
    'зарплата': '💰', 'фриланс': '💻', 'подарок': '🎁', 'кэшбэк': '💳', 'прочее': '📦'
}

# Цены на подписки (в Telegram Stars)
SUBSCRIPTIONS = {
    1: {'days': 30, 'price': 50, 'name': '1 месяц', 'discount': 0},
    3: {'days': 90, 'price': 135, 'name': '3 месяца', 'discount': 10},
    6: {'days': 180, 'price': 240, 'name': '6 месяцев', 'discount': 20},
    12: {'days': 365, 'price': 420, 'name': '12 месяцев', 'discount': 30}
}

# ========== ОСНОВНЫЕ ФУНКЦИИ ==========

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_reminders(reminders):
    with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

def is_premium(user_id):
    data = load_data()
    user_id = str(user_id)
    if user_id in data and 'premium_until' in data[user_id]:
        premium_until = datetime.fromisoformat(data[user_id]['premium_until'])
        if datetime.now() <= premium_until:
            return True
    return False

def get_premium_expiry(user_id):
    data = load_data()
    user_id = str(user_id)
    if user_id in data and 'premium_until' in data[user_id]:
        return datetime.fromisoformat(data[user_id]['premium_until'])
    return None

def activate_premium(user_id, months=1):
    """Активирует подписку на указанное количество месяцев"""
    data = load_data()
    user_id = str(user_id)
    
    if user_id not in data:
        data[user_id] = {'expenses': [], 'incomes': []}
    
    # Получаем количество дней из конфига
    days = SUBSCRIPTIONS[months]['days']
    new_expiry = datetime.now() + timedelta(days=days)
    
    # Если уже есть активная подписка - продлеваем
    if 'premium_until' in data[user_id]:
        old_expiry = datetime.fromisoformat(data[user_id]['premium_until'])
        if old_expiry > datetime.now():
            new_expiry = old_expiry + timedelta(days=days)
    
    data[user_id]['premium_until'] = new_expiry.isoformat()
    data[user_id]['subscription_months'] = months
    save_data(data)
    return new_expiry, SUBSCRIPTIONS[months]['price']

def get_achievements(expenses, incomes):
    achievements = []
    total_expenses = len(expenses)
    total_sum = sum(e['amount'] for e in expenses)
    
    if total_expenses >= 100:
        achievements.append("🏆 100 трат! Ты настоящий трекер!")
    elif total_expenses >= 50:
        achievements.append("🏅 50 трат! Хороший темп!")
    
    if total_sum > 100000:
        achievements.append("💎 Клуб 100к! Ты много тратишь, но мы это контролируем!")
    
    month_ago = datetime.now() - timedelta(days=30)
    old_expenses = [e for e in expenses if datetime.fromisoformat(e['timestamp']) < month_ago]
    new_expenses = [e for e in expenses if datetime.fromisoformat(e['timestamp']) >= month_ago]
    old_sum = sum(e['amount'] for e in old_expenses)
    new_sum = sum(e['amount'] for e in new_expenses)
    if old_sum > 0 and new_sum < old_sum * 0.8:
        achievements.append("📉 Экономист месяца! Ты сократил расходы на 20%!")
    
    return achievements

# ========== КРАСИВОЕ МЕНЮ ==========

def get_main_keyboard():
    """Создаёт красивое меню"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Основные кнопки
    markup.add(
        types.KeyboardButton('💰 Добавить расход'),
        types.KeyboardButton('💵 Добавить доход')
    )
    markup.add(
        types.KeyboardButton('📊 Статистика'),
        types.KeyboardButton('📅 За сегодня')
    )
    markup.add(
        types.KeyboardButton('📈 График'),
        types.KeyboardButton('📆 Месячный отчёт')
    )
    
    # Premium-кнопки (будут видны всем, но с проверкой внутри)
    markup.add(
        types.KeyboardButton('🔥 Тренды'),
        types.KeyboardButton('🎯 Бюджет')
    )
    markup.add(
        types.KeyboardButton('📎 Экспорт CSV'),
        types.KeyboardButton('🔔 Напоминания')
    )
    markup.add(
        types.KeyboardButton('🏆 Достижения'),
        types.KeyboardButton('🗑 Сбросить всё')
    )
    
    # Яркая кнопка Premium
    markup.add(types.KeyboardButton('⭐ КУПИТЬ PREMIUM ⭐'))
    
    return markup

def get_premium_keyboard():
    """Клавиатура для выбора срока подписки"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for months, info in SUBSCRIPTIONS.items():
        price = info['price']
        name = info['name']
        discount = info['discount']
        
        # Добавляем значок экономии если есть скидка
        if discount > 0:
            button_text = f"📅 {name} — {price} ⭐ (экономия {discount}%)"
        else:
            button_text = f"📅 {name} — {price} ⭐"
        
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"buy_{months}"))
    
    return markup

# ========== КОМАНДЫ ==========

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    premium = is_premium(user_id)
    
    # Формируем красивый заголовок
    if premium:
        expiry = get_premium_expiry(user_id)
        expiry_str = expiry.strftime("%d.%m.%Y") if expiry else "неизвестно"
        header = f"👑 ПРЕМИУМ АККАУНТ 👑\n📅 Активен до: {expiry_str}\n\n"
    else:
        header = "🔓 БЕСПЛАТНЫЙ АККАУНТ 🔓\n\n"
    
    # Сравнение тарифов
    comparison = """
╔══════════════════════════════════════╗
║          📊 СРАВНЕНИЕ ТАРИФОВ        ║
╠══════════════════════════════════════╣
║ 🔓 БЕСПЛАТНЫЙ                        ║
║ ✓ Добавление расходов/доходов        ║
║ ✓ Базовая статистика                 ║
║ ✓ График расходов                    ║
║ ✓ Месячный отчёт                     ║
║ ✗ Тренды и аналитика                 ║
║ ✗ Бюджет и лимиты                    ║
║ ✗ Экспорт в CSV/Excel                ║
║ ✗ Напоминания                        ║
║ ✗ Достижения и ачивки                ║
║ ✗ Аномалии и советы                  ║
╠══════════════════════════════════════╣
║ ⭐ ПРЕМИУМ (50 Stars/мес)            ║
║ ✓ ВСЁ из бесплатного                 ║
║ ✓ Аналитика трендов                  ║
║ ✓ Умный бюджет                       ║
║ ✓ Экспорт данных                     ║
║ ✓ Ежедневные напоминания             ║
║ ✓ Достижения и награды               ║
║ ✓ Персональные советы по экономии    ║
║ ✓ Прогноз расходов                   ║
║ ✓ Аномалии и предупреждения          ║
╚══════════════════════════════════════╝
"""
    
    # Выгода при покупке на срок
    benefit = """
💎 **ЧЕМ ДОЛЬШЕ, ТЕМ ВЫГОДНЕЕ!** 💎

📅 1 месяц — 50 ⭐
📅 3 месяца — 135 ⭐ (экономия 15 ⭐)
📅 6 месяцев — 240 ⭐ (экономия 60 ⭐)
📅 12 месяцев — 420 ⭐ (экономия 180 ⭐)

➡️ Купи подписку на 12 месяцев и получи 3 месяца БЕСПЛАТНО!
"""
    
    full_text = f"💰 *Привет, {message.from_user.first_name}!*\n\n{header}{comparison}\n{benefit}"
    
    bot.send_message(
        message.chat.id,
        full_text,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(commands=['premium'])
def show_premium_options(message):
    """Показывает варианты подписки"""
    text = """
╔══════════════════════════════════════╗
║     ⭐ ПРЕМИУМ ПОДПИСКА ⭐           ║
╠══════════════════════════════════════╣
║  Выбери срок подписки:               ║
║                                      ║
║  📅 1 месяц  — 50 ⭐                 ║
║  📅 3 месяца — 135 ⭐ (-10%)         ║
║  📅 6 месяцев — 240 ⭐ (-20%)        ║
║  📅 12 месяцев — 420 ⭐ (-30%)       ║
╠══════════════════════════════════════╣
║  💡 Чем дольше подписка,             ║
║  тем больше ты экономишь!            ║
╚══════════════════════════════════════╝
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=get_premium_keyboard())

@bot.message_handler(func=lambda message: message.text == '⭐ КУПИТЬ PREMIUM ⭐')
def premium_button_handler(message):
    show_premium_options(message)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def process_premium_purchase(call):
    months = int(call.data.split('_')[1])
    subscription = SUBSCRIPTIONS[months]
    
    price = subscription['price']
    name = subscription['name']
    days = subscription['days']
    
    prices = [types.LabeledPrice(label=f"Premium на {name}", amount=price)]
    
    try:
        bot.send_invoice(
            call.message.chat.id,
            title=f"⭐ Premium подписка - {name}",
            description=f"Premium доступ на {days} дней.\n"
                       f"📊 Аналитика трендов\n"
                       f"🎯 Умный бюджет\n"
                       f"📎 Экспорт данных\n"
                       f"🔔 Напоминания\n"
                       f"🏆 Достижения\n"
                       f"💡 Советы по экономии",
            invoice_payload=f"premium_{months}",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter=f"premium_{months}",
            need_name=False,
            need_phone_number=False,
            need_email=False
        )
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Ошибка: {e}")
    
    bot.answer_callback_query(call.id)

@bot.pre_checkout_query_handler(func=lambda query: True)
def on_pre_checkout_query(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def on_successful_payment(message):
    # Получаем количество месяцев из payload
    payload = message.successful_payment.invoice_payload
    months = int(payload.split('_')[1])
    
    expiry_date, price = activate_premium(message.chat.id, months)
    expiry_str = expiry_date.strftime("%d.%m.%Y")
    
    # Поздравление с учетом срока
    if months == 1:
        period = "месяц"
    elif months in [2, 3, 4]:
        period = f"{months} месяца"
    else:
        period = f"{months} месяцев"
    
    text = f"""
╔══════════════════════════════════════╗
║     ✅ ОПЛАТА ПРОШЛА УСПЕШНО! ✅     ║
╠══════════════════════════════════════╣
║  🎉 Поздравляю! Ты приобрел         ║
║     Premium подписку на {period}!    ║
║                                      ║
║  ⭐ Сумма: {price} Stars              ║
║  📅 Активна до: {expiry_str}         ║
║                                      ║
║  🔥 Тебе открыты все функции:        ║
║  • Аналитика трендов                ║
║  • Умный бюджет                     ║
║  • Экспорт данных                   ║
║  • Напоминания                      ║
║  • Достижения                       ║
║  • Советы по экономии               ║
╠══════════════════════════════════════╣
║  💡 Используй /start, чтобы начать!  ║
╚══════════════════════════════════════╝
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown')
    
    # Обновляем меню
    start(message)

@bot.message_handler(commands=['check'])
def check_status(message):
    """Проверка статуса подписки"""
    if is_premium(message.chat.id):
        expiry = get_premium_expiry(message.chat.id)
        expiry_str = expiry.strftime("%d.%m.%Y") if expiry else "неизвестно"
        
        data = load_data()
        user_id = str(message.chat.id)
        months = data[user_id].get('subscription_months', 1)
        
        text = f"""
╔══════════════════════════════════════╗
║     👑 СТАТУС ПОДПИСКИ 👑            ║
╠══════════════════════════════════════╣
║  Статус: АКТИВНА                     ║
║  Тариф: PREMIUM                      ║
║  Срок: {months} месяцев               ║
║  Действует до: {expiry_str}          ║
╠══════════════════════════════════════╣
║  🔥 Все премиум-функции доступны!    ║
╚══════════════════════════════════════╝
"""
    else:
        text = """
╔══════════════════════════════════════╗
║     🔓 СТАТУС ПОДПИСКИ 🔓            ║
╠══════════════════════════════════════╣
║  Статус: НЕ АКТИВНА                  ║
║  Тариф: БЕСПЛАТНЫЙ                   ║
╠══════════════════════════════════════╣
║  ⭐ Купи Premium, чтобы получить:    ║
║  • Аналитику трендов                ║
║  • Умный бюджет                     ║
║  • Экспорт данных                   ║
║  • Напоминания                      ║
║  • Достижения                       ║
║                                      ║
║  💰 Всего от 50 Stars в месяц!       ║
╚══════════════════════════════════════╝
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ========== ВСЕ ПРЕМИУМ-ФУНКЦИИ (с проверкой подписки) ==========

@bot.message_handler(func=lambda message: message.text == '🔥 Тренды')
def show_trends(message):
    if not is_premium(message.chat.id):
        bot.send_message(message.chat.id, "🔒 *Только для Premium!*\n\nКупи подписку командой /premium или кнопкой ⭐ КУПИТЬ PREMIUM ⭐", parse_mode='Markdown')
        return
    
    user_id = str(message.chat.id)
    data = load_data()
    if user_id not in data or not data[user_id]['expenses']:
        bot.send_message(message.chat.id, "📭 Нет данных для анализа")
        return
    
    expenses = data[user_id]['expenses']
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    
    last_week = [e for e in expenses if datetime.fromisoformat(e['timestamp']) >= week_ago]
    prev_week = [e for e in expenses if two_weeks_ago <= datetime.fromisoformat(e['timestamp']) < week_ago]
    
    last_sum = sum(e['amount'] for e in last_week)
    prev_sum = sum(e['amount'] for e in prev_week)
    
    trend = "📈 РАСТУТ" if last_sum > prev_sum else "📉 ПАДАЮТ"
    change = ((last_sum - prev_sum) / prev_sum * 100) if prev_sum > 0 else 0
    
    text = f"""
╔══════════════════════════════════════╗
║          🔥 ТРЕНДЫ РАСХОДОВ 🔥       ║
╠══════════════════════════════════════╣
║  📅 Последние 7 дней: {last_sum:,.0f} ₽
║  📅 Предыдущие 7 дней: {prev_sum:,.0f} ₽
║                                      ║
║  📊 Расходы {trend} на {abs(change):.1f}%
╚══════════════════════════════════════╝
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '🎯 Бюджет')
def budget_menu(message):
    if not is_premium(message.chat.id):
        bot.send_message(message.chat.id, "🔒 *Только для Premium!*\n\nКупи подписку командой /premium или кнопкой ⭐ КУПИТЬ PREMIUM ⭐", parse_mode='Markdown')
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Установить бюджет", callback_data="set_budget"))
    markup.add(types.InlineKeyboardButton("📊 Проверить бюджет", callback_data="check_budget"))
    bot.send_message(message.chat.id, "🎯 **Управление бюджетом**\n\nУстанови лимит на месяц, и я буду предупреждать о превышении!", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data in ['set_budget', 'check_budget'])
def budget_handler(call):
    user_id = str(call.message.chat.id)
    data = load_data()
    if call.data == 'set_budget':
        msg = bot.send_message(call.message.chat.id, "💰 Введите сумму бюджета на месяц (например: 50000)")
        bot.register_next_step_handler(msg, save_budget)
    else:
        if user_id in data and 'budget' in data[user_id]:
            budget = data[user_id]['budget']
            month_expenses = sum(e['amount'] for e in data[user_id]['expenses'] if e['date'].startswith(datetime.now().strftime('%Y-%m')))
            percent = (month_expenses / budget) * 100
            if percent < 80:
                status = "✅ ХОРОШО"
            elif percent < 100:
                status = "⚠️ ВНИМАНИЕ"
            else:
                status = "🔴 ПРЕВЫШЕН!"
            
            text = f"""
╔══════════════════════════════════════╗
║            🎯 БЮДЖЕТ 🎯              ║
╠══════════════════════════════════════╣
║  💰 Лимит: {budget:,.0f} ₽
║  💸 Потрачено: {month_expenses:,.0f} ₽
║  📊 Выполнено: {percent:.1f}%
║                                      ║
║  Статус: {status}
╚══════════════════════════════════════╝
"""
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        else:
            bot.edit_message_text("❌ Бюджет не установлен. Используй '💰 Установить бюджет'", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)

def save_budget(message):
    user_id = str(message.chat.id)
    try:
        budget = float(message.text.strip())
        data = load_data()
        if user_id not in data:
            data[user_id] = {'expenses': [], 'incomes': []}
        data[user_id]['budget'] = budget
        save_data(data)
        bot.send_message(message.chat.id, f"✅ Бюджет установлен: {budget:,.0f} ₽ на месяц")
    except:
        bot.send_message(message.chat.id, "❌ Ошибка! Введите число, например: 50000")

@bot.message_handler(func=lambda message: message.text == '📎 Экспорт CSV')
def export_csv(message):
    if not is_premium(message.chat.id):
        bot.send_message(message.chat.id, "🔒 *Только для Premium!*\n\nКупи подписку командой /premium", parse_mode='Markdown')
        return
    
    user_id = str(message.chat.id)
    data = load_data()
    if user_id not in data or (not data[user_id]['expenses'] and not data[user_id]['incomes']):
        bot.send_message(message.chat.id, "📭 Нет данных для экспорта")
        return
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Дата', 'Время', 'Категория', 'Сумма', 'Тип'])
    for e in data[user_id]['expenses']:
        writer.writerow([e['date'], e['time'], e['category'], e['amount'], 'Расход'])
    for i in data[user_id]['incomes']:
        writer.writerow([i['date'], i['time'], i['category'], i['amount'], 'Доход'])
    
    bot.send_document(message.chat.id, io.BytesIO(output.getvalue().encode('utf-8-sig')), visible_file_name=f'finance_{datetime.now().strftime("%Y%m%d")}.csv')
    bot.send_message(message.chat.id, "📎 Файл отправлен! Можно открыть в Excel или Google Sheets")

@bot.message_handler(func=lambda message: message.text == '🔔 Напоминания')
def reminders_menu(message):
    if not is_premium(message.chat.id):
        bot.send_message(message.chat.id, "🔒 *Только для Premium!*\n\nКупи подписку командой /premium", parse_mode='Markdown')
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⏰ Установить время", callback_data="set_reminder"))
    markup.add(types.InlineKeyboardButton("❌ Отключить", callback_data="disable_reminder"))
    bot.send_message(message.chat.id, "🔔 **Напоминания о расходах**\n\nЯ буду присылать уведомление каждый день в выбранное время, чтобы ты не забыл записать траты.", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data in ['set_reminder', 'disable_reminder'])
def reminder_handler(call):
    user_id = str(call.message.chat.id)
    if call.data == 'set_reminder':
        msg = bot.send_message(call.message.chat.id, "⏰ Введите время в формате ЧЧ:ММ (например: 21:00)")
        bot.register_next_step_handler(msg, save_reminder)
    else:
        reminders = load_reminders()
        if user_id in reminders:
            del reminders[user_id]
            save_reminders(reminders)
        bot.edit_message_text("❌ Напоминания отключены", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)

def save_reminder(message):
    user_id = str(message.chat.id)
    try:
        time_str = message.text.strip()
        datetime.strptime(time_str, "%H:%M")
        reminders = load_reminders()
        reminders[user_id] = time_str
        save_reminders(reminders)
        bot.send_message(message.chat.id, f"✅ Напоминание установлено на {time_str} каждый день!")
    except:
        bot.send_message(message.chat.id, "❌ Неправильный формат! Пример: 21:00")

@bot.message_handler(func=lambda message: message.text == '🏆 Достижения')
def show_achievements(message):
    if not is_premium(message.chat.id):
        bot.send_message(message.chat.id, "🔒 *Только для Premium!*\n\nКупи подписку командой /premium", parse_mode='Markdown')
        return
    
    user_id = str(message.chat.id)
    data = load_data()
    if user_id not in data:
        bot.send_message(message.chat.id, "📭 Нет данных")
        return
    
    expenses = data[user_id]['expenses']
    incomes = data[user_id]['incomes']
    achievements = get_achievements(expenses, incomes)
    
    if achievements:
        text = "🏆 **ТВОИ ДОСТИЖЕНИЯ** 🏆\n\n" + "\n".join(achievements)
    else:
        text = "🏆 Пока нет достижений. Добавляй больше трат и экономь, чтобы открывать новые ачивки!"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ========== СТАТИСТИКА С ПРЕМИУМ-АНАЛИТИКОЙ ==========

@bot.message_handler(func=lambda message: message.text == '📊 Статистика')
def show_stats(message):
    user_id = str(message.chat.id)
    data = load_data()
    premium = is_premium(message.chat.id)
    
    if user_id not in data or (not data[user_id].get('expenses') and not data[user_id].get('incomes')):
        bot.send_message(message.chat.id, "📭 Нет данных. Добавьте первый расход или доход!")
        return
    
    expenses = data[user_id]['expenses']
    incomes = data[user_id]['incomes']
    total_exp = sum(e['amount'] for e in expenses)
    total_inc = sum(i['amount'] for i in incomes)
    balance = total_inc - total_exp
    
    exp_by_cat = {}
    for e in expenses:
        cat = e['category']
        exp_by_cat[cat] = exp_by_cat.get(cat, 0) + e['amount']
    
    text = f"""
╔══════════════════════════════════════╗
║         📊 СТАТИСТИКА 📊             ║
╠══════════════════════════════════════╣
║  💰 Доходы: {total_inc:,.0f} ₽
║  💸 Расходы: {total_exp:,.0f} ₽
║  📊 Баланс: {balance:+,.0f} ₽
╠══════════════════════════════════════╣
║  📉 РАСХОДЫ ПО КАТЕГОРИЯМ:
"""
    
    for cat, amt in sorted(exp_by_cat.items(), key=lambda x: x[1], reverse=True)[:5]:
        text += f"  {CATEGORIES.get(cat, '📦')} {cat}: {amt:,.0f} ₽\n"
    
    # Премиум-аналитика
    if premium:
        # Аномалии
        daily_avg = total_exp / 30 if len(expenses) > 0 else 0
        high_days = {}
        for e in expenses:
            if e['amount'] > daily_avg * 2:
                high_days[e['date']] = high_days.get(e['date'], 0) + e['amount']
        
        if high_days:
            text += f"\n⚠️ *Аномалии*: "
            for d, v in list(high_days.items())[:2]:
                text += f"{d} ({v:,.0f}₽) "
            text += "\n"
        
        # Совет
        coffee_total = sum(e['amount'] for e in expenses if e['category'] == 'кофе')
        if coffee_total > 5000:
            text += f"\n💡 *Совет*: На кофе потрачено {coffee_total:,.0f}₽. Попробуй готовить дома!"
        elif 'развлечения' in exp_by_cat and exp_by_cat['развлечения'] > total_exp * 0.3:
            text += f"\n💡 *Совет*: Развлечения составляют {exp_by_cat['развлечения']/total_exp*100:.0f}% расходов."
    
    text += "\n╚══════════════════════════════════════╝"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ========== БАЗОВЫЕ ФУНКЦИИ (добавление расходов/доходов, график, отчёт, сброс) ==========

@bot.message_handler(func=lambda message: message.text == '💰 Добавить расход')
def ask_expense(message):
    msg = bot.send_message(message.chat.id, 
        "📝 *Формат расхода:*\n\n"
        "Категория сумма\n\n"
        "📌 *Категории:*\n"
        + '\n'.join([f"{emoji} {cat}" for cat, emoji in CATEGORIES.items()]) +
        "\n\n✅ *Пример:* еда 500", 
        parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_transaction, 'expense')

@bot.message_handler(func=lambda message: message.text == '💵 Добавить доход')
def ask_income(message):
    msg = bot.send_message(message.chat.id, 
        "📝 *Формат дохода:*\n\n"
        "Категория сумма\n\n"
        "📌 *Категории:*\n"
        + '\n'.join([f"{emoji} {cat}" for cat, emoji in CATEGORIES_INCOME.items()]) +
        "\n\n✅ *Пример:* зарплата 50000", 
        parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_transaction, 'income')

def save_transaction(message, trans_type):
    user_id = str(message.chat.id)
    text = message.text.strip()
    parts = text.split()
    
    if len(parts) < 2 or not parts[-1].replace('.', '').isdigit():
        bot.send_message(message.chat.id, "❌ Неправильный формат. Пример: еда 500")
        return
    
    amount = float(parts[-1])
    category = ' '.join(parts[:-1]).lower()
    
    if trans_type == 'expense':
        if category not in CATEGORIES:
            category = 'прочее'
    else:
        if category not in CATEGORIES_INCOME:
            category = 'прочее'
    
    data = load_data()
    if user_id not in data:
        data[user_id] = {'expenses': [], 'incomes': []}
    
    transaction = {
        'amount': amount,
        'category': category,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M:%S'),
        'timestamp': datetime.now().isoformat()
    }
    
    if trans_type == 'expense':
        data[user_id]['expenses'].append(transaction
