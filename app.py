import os
import telebot
from telebot import types
from flask import Flask
import threading
import json
from datetime import datetime, timedelta
import os.path

# --- Токен из переменных окружения Railway ---
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

# Загрузка данных
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# Сохранение данных
def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Создание основной клавиатуры
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_expense = types.KeyboardButton('➖ Добавить расход')
    btn_income = types.KeyboardButton('➕ Добавить доход')
    btn_stats = types.KeyboardButton('📊 Статистика')
    btn_today = types.KeyboardButton('📅 За сегодня')
    btn_chart = types.KeyboardButton('📈 График')
    btn_monthly = types.KeyboardButton('📆 Месячный отчёт')
    btn_reset = types.KeyboardButton('🗑 Сбросить всё')
    markup.add(btn_expense, btn_income, btn_stats, btn_today, btn_chart, btn_monthly, btn_reset)
    return markup

# --- КОМАНДА /start ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        f"💰 Привет, {message.from_user.first_name}!\n\n"
        f"Я помогу тебе отслеживать финансы!\n\n"
        f"📌 Что я умею:\n"
        f"➖ Добавить расход\n"
        f"➕ Добавить доход\n"
        f"📊 Статистика (всего, по категориям)\n"
        f"📅 За сегодня\n"
        f"📈 График расходов\n"
        f"📆 Месячный отчёт\n"
        f"🗑 Сбросить всё\n\n"
        f"💡 Просто напиши: «еда 500» или «зарплата 50000»",
        reply_markup=get_main_keyboard()
    )

# --- Добавление расхода ---
@bot.message_handler(func=lambda message: message.text == '➖ Добавить расход')
def ask_expense(message):
    msg = bot.send_message(message.chat.id, 
        "Напиши расход в формате:\n\n"
        "📝 **категория сумма**\n\n"
        "Доступные категории:\n"
        + '\n'.join([f"{emoji} {cat}" for cat, emoji in CATEGORIES.items()]) +
        "\n\nПример: еда 500", parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_transaction, 'expense')

# --- Добавление дохода ---
@bot.message_handler(func=lambda message: message.text == '➕ Добавить доход')
def ask_income(message):
    msg = bot.send_message(message.chat.id, 
        "Напиши доход в формате:\n\n"
        "📝 **категория сумма**\n\n"
        "Доступные категории:\n"
        + '\n'.join([f"{emoji} {cat}" for cat, emoji in CATEGORIES_INCOME.items()]) +
        "\n\nПример: зарплата 50000", parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_transaction, 'income')

def save_transaction(message, trans_type):
    user_id = str(message.chat.id)
    text = message.text.strip()
    parts = text.split()
    
    if len(parts) < 2 or not parts[-1].replace('.', '').isdigit():
        bot.send_message(message.chat.id, "❌ Неправильный формат. Попробуй: категория сумма\nПример: еда 500")
        return
    
    amount = float(parts[-1])
    category = ' '.join(parts[:-1]).lower()
    
    # Проверяем категорию
    if trans_type == 'expense':
        if category not in CATEGORIES:
            category = 'прочее'
    else:
        if category not in CATEGORIES_INCOME:
            category = 'прочее'
    
    data = load_data()
    if user_id not in data:
        data[user_id] = {'expenses': [], 'incomes': [], 'budget': None}
    
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
        bot.send_message(message.chat.id, f"✅ Расход добавлен: {emoji} {category} - {amount} ₽")
    else:
        data[user_id]['incomes'].append(transaction)
        emoji = CATEGORIES_INCOME.get(category, '📦')
        bot.send_message(message.chat.id, f"✅ Доход добавлен: {emoji} {category} - {amount} ₽")
    
    save_data(data)

# --- Статистика ---
@bot.message_handler(func=lambda message: message.text == '📊 Статистика')
def show_stats(message):
    user_id = str(message.chat.id)
    data = load_data()
    
    if user_id not in data or (not data[user_id]['expenses'] and not data[user_id]['incomes']):
        bot.send_message(message.chat.id, "📭 Нет данных. Добавьте первый расход или доход!")
        return
    
    expenses = data[user_id]['expenses']
    incomes = data[user_id]['incomes']
    
    total_expenses = sum(e['amount'] for e in expenses)
    total_incomes = sum(i['amount'] for i in incomes)
    balance = total_incomes - total_expenses
    
    # Расходы по категориям
    exp_by_cat = {}
    for e in expenses:
        cat = e['category']
        exp_by_cat[cat] = exp_by_cat.get(cat, 0) + e['amount']
    
    # Доходы по категориям
    inc_by_cat = {}
    for i in incomes:
        cat = i['category']
        inc_by_cat[cat] = inc_by_cat.get(cat, 0) + i['amount']
    
    stats_text = f"📊 **ФИНАНСОВАЯ СТАТИСТИКА**\n\n"
    stats_text += f"💰 **Доходы:** {total_incomes:,.0f} ₽\n"
    stats_text += f"💸 **Расходы:** {total_expenses:,.0f} ₽\n"
    stats_text += f"📊 **Баланс:** {balance:+,.0f} ₽\n\n"
    
    if exp_by_cat:
        stats_text += f"**📉 Расходы по категориям:**\n"
        for cat, amount in sorted(exp_by_cat.items(), key=lambda x: x[1], reverse=True):
            emoji = CATEGORIES.get(cat, '📦')
            percent = (amount / total_expenses) * 100 if total_expenses > 0 else 0
            stats_text += f"{emoji} {cat}: {amount:,.0f} ₽ ({percent:.1f}%)\n"
    
    if inc_by_cat:
        stats_text += f"\n**📈 Доходы по категориям:**\n"
        for cat, amount in sorted(inc_by_cat.items(), key=lambda x: x[1], reverse=True):
            emoji = CATEGORIES_INCOME.get(cat, '📦')
            stats_text += f"{emoji} {cat}: {amount:,.0f} ₽\n"
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

# --- За сегодня ---
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
        if today_incomes:
            text += f"\n**Расходы:**\n"
        else:
            text += f"**Расходы:**\n"
        for e in today_expenses:
            emoji = CATEGORIES.get(e['category'], '📦')
            text += f"{emoji} {e['category']}: -{e['amount']:,.0f} ₽ ({e['time']})\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# --- График (текстовый) ---
@bot.message_handler(func=lambda message: message.text == '📈 График')
def show_chart(message):
    user_id = str(message.chat.id)
    data = load_data()
    
    if user_id not in data or not data[user_id]['expenses']:
        bot.send_message(message.chat.id, "📭 Нет расходов для графика.")
        return
    
    # Группируем расходы по категориям
    exp_by_cat = {}
    for e in data[user_id]['expenses']:
        cat = e['category']
        exp_by_cat[cat] = exp_by_cat.get(cat, 0) + e['amount']
    
    total = sum(exp_by_cat.values())
    
    # Создаём текстовый график
    chart_text = "📊 **ГРАФИК РАСХОДОВ**\n\n"
    
    for cat, amount in sorted(exp_by_cat.items(), key=lambda x: x[1], reverse=True)[:8]:
        emoji = CATEGORIES.get(cat, '📦')
        percent = (amount / total) * 100
        bar_length = int(percent / 2)  # Максимум 50 символов
        bar = '█' * bar_length + '░' * (50 - bar_length)
        chart_text += f"{emoji} {cat}:\n"
        chart_text += f"   {bar} {percent:.1f}% ({amount:,.0f} ₽)\n\n"
    
    bot.send_message(message.chat.id, chart_text, parse_mode='Markdown')

# --- Месячный отчёт ---
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
    
    # Текущий месяц
    current_expenses = [e for e in data[user_id]['expenses'] if e['date'].startswith(current_month)]
    current_incomes = [i for i in data[user_id]['incomes'] if i['date'].startswith(current_month)]
    
    # Прошлый месяц
    last_expenses = [e for e in data[user_id]['expenses'] if e['date'].startswith(last_month)]
    last_incomes = [i for i indata[user_id]['incomes'] if i['date'].startswith(last_month)]
    
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

# --- Сброс ---
@bot.message_handler(func=lambda message: message.text == '🗑 Сбросить всё')
def reset_confirm(message):
    markup = types.InlineKeyboardMarkup()
    btn_yes = types.InlineKeyboardButton('✅ Да, удалить всё', callback_data='reset_yes')
    btn_no = types.InlineKeyboardButton('❌ Нет, отмена', callback_data='reset_no')
    markup.add(btn_yes, btn_no)
    
    bot.send_message(message.chat.id, "⚠️ **ВНИМАНИЕ!** ⚠️\n\nВы уверены, что хотите удалить ВСЕ данные?\n\nЭто действие нельзя отменить!", 
                    parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['reset_yes', 'reset_no'])
def handle_reset(call):
    if call.data == 'reset_yes':
        user_id = str(call.message.chat.id)
        data = load_data()
        if user_id in data:
            data[user_id] = {'expenses': [], 'incomes': [], 'budget': None}
            save_data(data)
        bot.edit_message_text("✅ Все данные удалены!", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Начните с чистого листа! /start")
    else:
        bot.edit_message_text("❌ Удаление отменено.", call.message.chat.id, call.message.message_id)
    
    bot.answer_callback_query(call.id)

# --- Обработка быстрого текста ---
@bot.message_handler(func=lambda message: message.text and not message.text.startswith('/') and not any(message.text.startswith(x) for x in ['➖', '➕', '📊', '📅', '📈', '📆', '🗑']))
def quick_add(message):
    text = message.text.strip()
    parts = text.split()
    
    if len(parts) >= 2 and parts[-1].replace('.', '').isdigit():
        amount = float(parts[-1])
        category = ' '.join(parts[:-1]).lower()
        
        data = load_data()
        user_id = str(message.chat.id)
        if user_id not in data:
            data[user_id] = {'expenses': [], 'incomes': [], 'budget': None}
        
        # Проверяем, доход это или расход
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
            bot.reply_to(message, f"✅ Доход добавлен: {emoji} {category} - {amount} ₽")
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
            bot.reply_to(message, f"✅ Расход добавлен: {emoji} {category} - {amount} ₽")
    else:
        bot.reply_to(message, "❓ Не понял. Напиши /start для меню\nИли добавь: категория сумма\nПример: еда 500 или зарплата 50000")

# --- Запуск бота ---
def run_bot():
    print("💰 Финансовый бот запущен!")
    print("Доступны: расходы, доходы, статистика, графики, отчёты")
    bot.infinity_polling()

@server.route('/')
def hello():
    return "Финансовый бот работает!"

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    server.run(host='0.0.0.0', port=port)
