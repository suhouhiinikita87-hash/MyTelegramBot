import os
import telebot
from telebot import types
from flask import Flask
import threading
import json
from datetime import datetime, timedelta

# --- Токен ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("Переменная TELEGRAM_TOKEN не найдена!")

bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

# Файл для хранения данных
DATA_FILE = 'finance.json'

# Категории с эмодзи
CATEGORIES = {
    'еда': '🍕',
    'транспорт': '🚗',
    'кофе': '☕',
    'развлечения': '🎮',
    'шопинг': '🛍️',
    'здоровье': '💊',
    'коммунальные': '💡',
    'связь': '📱',
    'прочее': '📦'
}

CATEGORIES_INCOME = {
    'зарплата': '💰',
    'фриланс': '💻',
    'подарок': '🎁',
    'кэшбэк': '💳',
    'прочее': '📦'
}

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПОДПИСКОЙ ==========

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_premium(user_id):
    """Проверяет, активна ли подписка у пользователя"""
    data = load_data()
    user_id = str(user_id)
    if user_id in data and 'premium_until' in data[user_id]:
        premium_until = datetime.fromisoformat(data[user_id]['premium_until'])
        if datetime.now() <= premium_until:
            return True
    return False

def activate_premium(user_id, days=30):
    """Активирует подписку на N дней"""
    data = load_data()
    user_id = str(user_id)
    
    if user_id not in data:
        data[user_id] = {'expenses': [], 'incomes': []}
    
    new_expiry = datetime.now() + timedelta(days=days)
    
    if 'premium_until' in data[user_id]:
        old_expiry = datetime.fromisoformat(data[user_id]['premium_until'])
        if old_expiry > datetime.now():
            new_expiry = old_expiry + timedelta(days=days)
    
    data[user_id]['premium_until'] = new_expiry.isoformat()
    save_data(data)
    return new_expiry

# ========== КОМАНДЫ ==========

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_expense = types.KeyboardButton('➖ Добавить расход')
    btn_income = types.KeyboardButton('➕ Добавить доход')
    btn_stats = types.KeyboardButton('📊 Статистика')
    btn_today = types.KeyboardButton('📅 За сегодня')
    btn_chart = types.KeyboardButton('📈 График')
    btn_monthly = types.KeyboardButton('📆 Месячный отчёт')
    btn_premium = types.KeyboardButton('🌟 Купить Premium')
    btn_reset = types.KeyboardButton('🗑 Сбросить всё')
    markup.add(btn_expense, btn_income, btn_stats, btn_today, btn_chart, btn_monthly, btn_premium, btn_reset)
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    if is_premium(message.chat.id):
        premium_status = "🌟 У вас активна **Premium подписка**! Доступны расширенные функции.\n\n"
    else:
        premium_status = "🔖 У вас **бесплатный тариф**. Купите Premium командой /premium за 50 Stars!\n\n"
    
    bot.send_message(
        message.chat.id,
        f"💰 Привет, {message.from_user.first_name}!\n\n"
        f"{premium_status}"
        f"📌 **Что я умею:**\n"
        f"➖ Добавить расход\n"
        f"➕ Добавить доход\n"
        f"📊 Статистика\n"
        f"📅 За сегодня\n"
        f"📈 График расходов\n"
        f"📆 Месячный отчёт\n"
        f"🌟 Купить Premium\n"
        f"🗑 Сбросить всё\n\n"
        f"💡 Быстрый ввод: «еда 500» или «зарплата 50000»",
        reply_markup=get_main_keyboard(),
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['premium'])
def send_premium_invoice(message):
    PRICE_IN_STARS = 50
    
    prices = [types.LabeledPrice(label="Premium подписка на 1 месяц", amount=PRICE_IN_STARS)]
    
    bot.send_invoice(
        message.chat.id,
        title="🌟 Premium подписка",
        description="Доступ к расширенной статистике, аналитике и прогнозам на 1 месяц!",
        invoice_payload="premium_subscription",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="premium_subscription",
        need_name=False,
        need_phone_number=False,
        need_email=False
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def on_pre_checkout_query(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def on_successful_payment(message):
    expiry_date = activate_premium(message.chat.id, days=30)
    expiry_str = expiry_date.strftime("%d.%m.%Y")
    
    bot.send_message(
        message.chat.id,
        f"✅ **Оплата прошла успешно!**\n\n"
        f"🎉 Поздравляю! Premium подписка активирована до **{expiry_str}**\n\n"
        f"Используйте /start, чтобы увидеть новые возможности!",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['check'])
def check_status(message):
    if is_premium(message.chat.id):
        data = load_data()
        user_id = str(message.chat.id)
        expiry_date = datetime.fromisoformat(data[user_id]['premium_until'])
        expiry_str = expiry_date.strftime("%d.%m.%Y")
        bot.send_message(
            message.chat.id,
            f"🌟 **Ваш статус: Premium**\nАктивен до: {expiry_str}",
            parse_mode='Markdown'
        )
    else:
        bot.send_message(
            message.chat.id,
            f"🔖 **Ваш статус: Бесплатный**\n\nКупите Premium командой /premium за 50 Stars!",
            parse_mode='Markdown'
        )

# ========== ДОБАВЛЕНИЕ РАСХОДОВ И ДОХОДОВ ==========

@bot.message_handler(func=lambda message: message.text == '➖ Добавить расход')
def ask_expense(message):
    msg = bot.send_message(message.chat.id, 
        "Напиши расход в формате:\n\n"
        "📝 **категория сумма**\n\n"
        "Доступные категории:\n"
        + '\n'.join([f"{emoji} {cat}" for cat, emoji in CATEGORIES.items()]) +
        "\n\nПример: еда 500", 
        parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_transaction, 'expense')

@bot.message_handler(func=lambda message: message.text == '➕ Добавить доход')
def ask_income(message):
    msg = bot.send_message(message.chat.id, 
        "Напиши доход в формате:\n\n"
        "📝 **категория сумма**\n\n"
        "Доступные категории:\n"
        + '\n'.join([f"{emoji} {cat}" for cat, emoji in CATEGORIES_INCOME.items()]) +
        "\n\nПример: зарплата 50000", 
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
        data[user_id]['expenses'].append(transaction)
        emoji = CATEGORIES.get(category, '📦')
        bot.send_message(message.chat.id, f"✅ Расход: {emoji} {category} - {amount} ₽")
    else:
        data[user_id]['incomes'].append(transaction)
        emoji = CATEGORIES_INCOME.get(category, '📦')
        bot.send_message(message.chat.id, f"✅ Доход: {emoji} {category} - {amount} ₽")
    
    save_data(data)

# ========== СТАТИСТИКА (с премиум-функциями) ==========

@bot.message_handler(func=lambda message: message.text == '📊 Статистика')
def show_stats(message):
    user_id = str(message.chat.id)
    data = load_data()
    
    if user_id not in data or (not data[user_id].get('expenses') and not data[user_id].get('incomes')):
        bot.send_message(message.chat.id, "📭 Нет данных. Добавьте первый расход или доход!")
        return
    
    expenses = data[user_id]['expenses']
    incomes = data[user_id]['incomes']
    
    total_expenses = sum(e['amount'] for e in expenses)
    total_incomes = sum(i['amount'] for i in incomes)
    balance = total_incomes - total_expenses
    
    exp_by_cat = {}
    for e in expenses:
        cat = e['category']
        exp_by_cat[cat] = exp_by_cat.get(cat, 0) + e['amount']
    
    stats_text = f"📊 **ФИНАНСОВАЯ СТАТИСТИКА**\n\n"
    stats_text += f"💰 Доходы: {total_incomes:,.0f} ₽\n"
    stats_text += f"💸 Расходы: {total_expenses:,.0f} ₽\n"
    stats_text += f"📊 Баланс: {balance:+,.0f} ₽\n\n"
    stats_text += f"**Расходы по категориям:**\n"
    for cat, amount in sorted(exp_by_cat.items(), key=lambda x: x[1], reverse=True):
        emoji = CATEGORIES.get(cat, '📦')
        stats_text += f"{emoji} {cat}: {amount:,.0f} ₽\n"
    
    # ПРЕМИУМ-ФУНКЦИИ (только для подписчиков)
    if is_premium(message.chat.id):
        avg_expense = total_expenses / len(expenses) if expenses else 0
        max_expense = max(expenses, key=lambda x: x['amount']) if expenses else None
        
        stats_text += f"\n🌟 **ПРЕМИУМ-АНАЛИТИКА** 🌟\n"
        stats_text += f"📊 Средний расход: {avg_expense:,.0f} ₽\n"
        if max_expense:
            emoji = CATEGORIES.get(max_expense['category'], '📦')
            stats_text += f"⚠️ Крупнейшая трата: {emoji} {max_expense['category']} — {max_expense['amount']:,.0f} ₽\n"
        
        week_ago = datetime.now() - timedelta(days=7)
        week_expenses = [e for e in expenses if datetime.fromisoformat(e['timestamp']) >= week_ago]
        if week_expenses:
            week_total = sum(e['amount'] for e in week_expenses)
            monthly_forecast = (week_total / 7) * 30
            stats_text += f"📈 Прогноз на месяц: {monthly_forecast:,.0f} ₽\n"
    else:
        stats_text += f"\n\n🔖 *Купите Premium командой /premium за 50 Stars, чтобы видеть средний чек, прогнозы и крупнейшие траты!*"
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

# ========== ОСТАЛЬНЫЕ ФУНКЦИИ (За сегодня, График, Месячный отчёт, Сброс, Быстрый ввод) ==========

@bot.message_handler(func=lambda message: message.text == '📅 За сегодня')
def show_today(message):
    user_id = str(message.chat.id)
    data = load_data()
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in data:
        bot.send_message(message.chat.id, "📭 Нет данных.")
        return
    
    today_expenses = [e for e in data[user_id]['expenses'] if e['date'] == today]
    today_incomes = [i for i in data[user_id]['incomes'] if i['date'] == today]
    
    total_exp = sum(e['amount'] for e in today_expenses)
    total_inc = sum(i['amount'] for i in today_incomes)
    
    if not today_expenses and not today_incomes:
        bot.send_message(message.chat.id, f"📅 За сегодня ({datetime.now().strftime('%d.%m.%Y')}) операций нет!")
        return
    
    text = f"📅 **ЗА СЕГОДНЯ** ({datetime.now().strftime('%d.%m.%Y')})\n\n"
    text += f"💰 Доходы: +{total_inc:,.0f} ₽\n"
    text += f"💸 Расходы: -{total_exp:,.0f} ₽\n"
    text += f"📊 Итого: {total_inc - total_exp:+,.0f} ₽\n\n"
    
    if today_incomes:
        text += f"**Доходы:**\n"
        for i in today_incomes:
            emoji = CATEGORIES_INCOME.get(i['category'], '📦')
            text += f"{emoji} {i['category']}: +{i['amount']:,.0f} ₽ ({i['time']})\n"
    
    if today_expenses:
        text += f"\n**Расходы:**\n"
        for e in today_expenses:
            emoji = CATEGORIES.get(e['category'], '📦')
            text += f"{emoji} {e['category']}: -{e['amount']:,.0f} ₽ ({e['time']})\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '📈 График')
def show_chart(message):
    user_id = str(message.chat.id)
    data = load_data()
    
    if user_id not in data or not data[user_id]['expenses']:
        bot.send_message(message.chat.id, "📭 Нет расходов для графика.")
        return
    
    exp_by_cat = {}
    for e in data[user_id]['expenses']:
        cat = e['category']
        exp_by_cat[cat] = exp_by_cat.get(cat, 0) + e['amount']
    
    total = sum(exp_by_cat.values())
    
    chart_text = "📊 **ГРАФИК РАСХОДОВ**\n\n"
    
    for cat, amount in sorted(exp_by_cat.items(), key=lambda x: x[1], reverse=True)[:8]:
        emoji = CATEGORIES.get(cat, '📦')
        percent = (amount / total) * 100
        bar_length = int(percent / 2)
        bar = '█' * bar_length + '░' * (50 - bar_length)
        chart_text += f"{emoji} {cat}:\n"
        chart_text += f"   {bar} {percent:.1f}% ({amount:,.0f} ₽)\n\n"
    
    bot.send_message(message.chat.id, chart_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '📆 Месячный отчёт')
def monthly_report(message):
    user_id = str(message.chat.id)
    data = load_data()
    
    if user_id not in data:
        bot.send_message(message.chat.id, "📭 Нет данных.")
        return
    
    now = datetime.now()
    current_month = now.strftime('%Y-%m')
    last_month = (now.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    
    current_expenses = [e for e in data[user_id]['expenses'] if e['date'].startswith(current_month)]
    current_incomes = [i for i in data[user_id]['incomes'] if i['date'].startswith(current_month)]
    last_expenses = [e for e in data[user_id]['expenses'] if e['date'].startswith(last_month)]
    last_incomes = [i for i in data[user_id]['incomes'] if i['date'].startswith(last_month)]
    
    cur_exp_sum = sum(e['amount'] for e in current_expenses)
    cur_inc_sum = sum(i['amount'] for i in current_incomes)
    last_exp_sum = sum(e['amount'] for e in last_expenses)
    last_inc_sum = sum(i['amount'] for i in last_incomes)
    
    report = f"📆 **МЕСЯЧНЫЙ ОТЧЁТ**\n\n"
    report += f"**{now.strftime('%B %Y')}** (текущий месяц)\n"
    report += f"💰 Доходы: {cur_inc_sum:,.0f} ₽\n"
    report += f"💸 Расходы: {cur_exp_sum:,.0f} ₽\n"
    report += f"📊 Баланс: {cur_inc_sum - cur_exp_sum:+,.0f} ₽\n"
    
    if last_exp_sum > 0 or last_inc_sum > 0:
        exp_change = ((cur_exp_sum - last_exp_sum) / last_exp_sum * 100) if last_exp_sum > 0 else 100
        inc_change = ((cur_inc_sum - last_inc_sum) / last_inc_sum * 100) if last_inc_sum > 0 else 100
        report += f"\n**Сравнение с прошлым месяцем:**\n"
        report += f"📉 Расходы: {exp_change:+.1f}%\n"
        report += f"📈 Доходы: {inc_change:+.1f}%\n"
    
    bot.send_message(message.chat.id, report, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '🌟 Купить Premium')
def premium_button_handler(message):
    send_premium_invoice(message)

@bot.message_handler(func=lambda message: message.text == '🗑 Сбросить всё')
def reset_confirm(message):
    markup = types.InlineKeyboardMarkup()
    btn_yes = types.InlineKeyboardButton('✅ Да, удалить всё', callback_data='reset_yes')
    btn_no = types.InlineKeyboardButton('❌ Нет, отмена', callback_data='reset_no')
    markup.add(btn_yes, btn_no)
    bot.send_message(message.chat.id, "⚠️ Удалить ВСЕ данные?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['reset_yes', 'reset_no'])
def handle_reset(call):
    if call.data == 'reset_yes':
        user_id = str(call.message.chat.id)
        data = load_data()
        if user_id in data:
            data[user_id] = {'expenses': [], 'incomes': []}
            save_data(data)
        bot.edit_message_text("✅ Все данные удалены!", call.message.chat.id, call.message.message_id)
    else:
        bot.edit_message_text("❌ Отменено.", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: message.text and not message.text.startswith('/') and not any(message.text.startswith(x) for x in ['➖', '➕', '📊', '📅', '📈', '📆', '🌟', '🗑']))
def quick_add(message):
    text = message.text.strip()
    parts = text.split()
    
    if len(parts) >= 2 and parts[-1].replace('.', '').isdigit():
        amount = float(parts[-1])
        category = ' '.join(parts[:-1]).lower()
        
        data = load_data()
        user_id = str(message.chat.id)
        if user_id not in data:
            data[user_id] = {'expenses': [], 'incomes': []}
        
        if category in CATEGORIES_INCOME:
            transaction = {
                'amount': amount,
                'category': category,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'time': datetime.now().strftime('%H:%M:%S'),
                'timestamp': datetime.now().isoformat()
            }
            data[user_id]['incomes'].append(transaction)
            save_data(data)
            emoji = CATEGORIES_INCOME.get(category, '📦')
            bot.reply_to(message, f"✅ Доход: {emoji} {category} - {amount} ₽")
        else:
            if category not in CATEGORIES:
                category = 'прочее'
            transaction = {
                'amount': amount,
                'category': category,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'time': datetime.now().strftime('%H:%M:%S'),
                'timestamp': datetime.now().isoformat()
            }
            data[user_id]['expenses'].append(transaction)
            save_data(data)
            emoji = CATEGORIES.get(category, '📦')
            bot.reply_to(message, f"✅ Расход: {emoji} {category} - {amount} ₽")
    else:
        bot.reply_to(message, "❓ Не понял. Напиши /start для меню")

# ========== ЗАПУСК БОТА ==========

def run_bot():
    print("💰 Финансовый бот с подпиской запущен!")
    bot.infinity_polling()

@server.route('/')
def hello():
    return "Финансовый бот работает!"

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    port = int(os.environ.get('PORT', 5000))
    server.run(host='0.0.0.0', port=port)
