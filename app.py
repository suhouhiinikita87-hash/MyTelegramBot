import os
import telebot
from telebot import types
from flask import Flask
import threading
import json
from datetime import datetime, timedelta

TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

DATA_FILE = 'finance.json'

CATEGORIES = {
    'еда': '🍕', 'транспорт': '🚗', 'кофе': '☕', 'развлечения': '🎮',
    'шопинг': '🛍️', 'здоровье': '💊', 'коммунальные': '💡', 'связь': '📱', 'прочее': '📦'
}
CATEGORIES_INCOME = {
    'зарплата': '💰', 'фриланс': '💻', 'подарок': '🎁', 'кэшбэк': '💳', 'прочее': '📦'
}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('💰 Добавить расход', '💵 Добавить доход')
    markup.add('📊 Статистика', '📅 За сегодня')
    markup.add('📈 График', '📆 Месячный отчёт')
    markup.add('🔥 Аналитика', '🎯 Бюджет')
    markup.add('📎 Экспорт CSV', '🏆 Достижения')
    markup.add('🗑 Сбросить всё')
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    # Создаём пользователя если его нет
    data = load_data()
    user_id = str(message.chat.id)
    if user_id not in data:
        data[user_id] = {'expenses': [], 'incomes': []}
        save_data(data)
    
    text = f"""💰 Привет, {message.from_user.first_name}!

📝 Я — твой финансовый помощник!

✅ Что я умею:
• Добавлять расходы и доходы
• Показывать статистику
• Строить графики
• Месячные отчёты
• Аналитику трендов
• Бюджетирование
• Экспорт в Excel
• Достижения

💡 Быстрый ввод: просто напиши «еда 500» или «зарплата 50000»

👇 Используй кнопки ниже для управления финансами!"""
    
    bot.send_message(message.chat.id, text, reply_markup=get_keyboard())

# ========== ДОБАВЛЕНИЕ РАСХОДОВ/ДОХОДОВ ==========

@bot.message_handler(func=lambda message: message.text == '💰 Добавить расход')
def ask_expense(message):
    msg = bot.send_message(message.chat.id, 
        "📝 *Добавление расхода*\n\n"
        "Напиши в формате: *категория сумма*\n\n"
        "📌 *Категории:*\n"
        + '\n'.join([f"{emoji} {cat}" for cat, emoji in CATEGORIES.items()]) +
        "\n\n✅ *Примеры:*\nеда 500\nтранспорт 200\nкофе 150", 
        parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_transaction, 'expense')

@bot.message_handler(func=lambda message: message.text == '💵 Добавить доход')
def ask_income(message):
    msg = bot.send_message(message.chat.id, 
        "📝 *Добавление дохода*\n\n"
        "Напиши в формате: *категория сумма*\n\n"
        "📌 *Категории:*\n"
        + '\n'.join([f"{emoji} {cat}" for cat, emoji in CATEGORIES_INCOME.items()]) +
        "\n\n✅ *Примеры:*\nзарплата 50000\nфриланс 15000\nподарок 3000", 
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
        bot.send_message(message.chat.id, f"✅ *Расход добавлен!*\n\n{emoji} {category}: {amount:,.0f} ₽", parse_mode='Markdown')
    else:
        data[user_id]['incomes'].append(transaction)
        emoji = CATEGORIES_INCOME.get(category, '📦')
        bot.send_message(message.chat.id, f"✅ *Доход добавлен!*\n\n{emoji} {category}: {amount:,.0f} ₽", parse_mode='Markdown')
    
    save_data(data)

# ========== СТАТИСТИКА ==========

@bot.message_handler(func=lambda message: message.text == '📊 Статистика')
def show_stats(message):
    user_id = str(message.chat.id)
    data = load_data()
    
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
    
    inc_by_cat = {}
    for i in incomes:
        cat = i['category']
        inc_by_cat[cat] = inc_by_cat.get(cat, 0) + i['amount']
    
    text = f"╔════════════════════════════════╗\n"
    text += f"║       📊 СТАТИСТИКА 📊         ║\n"
    text += f"╠════════════════════════════════╣\n"
    text += f"║ 💰 Доходы:  {total_inc:>12,.0f} ₽ ║\n"
    text += f"║ 💸 Расходы: {total_exp:>12,.0f} ₽ ║\n"
    text += f"║ 📊 Баланс:  {balance:>12,+.0f} ₽ ║\n"
    text += f"╠════════════════════════════════╣\n"
    text += f"║     📉 РАСХОДЫ ПО КАТЕГОРИЯМ   ║\n"
    text += f"╠════════════════════════════════╣\n"
    
    for cat, amt in sorted(exp_by_cat.items(), key=lambda x: x[1], reverse=True):
        emoji = CATEGORIES.get(cat, '📦')
        percent = (amt / total_exp * 100) if total_exp > 0 else 0
        text += f"║ {emoji} {cat[:12]:<12} {amt:>8,.0f} ({percent:>4.0f}%) ║\n"
    
    if inc_by_cat:
        text += f"╠════════════════════════════════╣\n"
        text += f"║     📈 ДОХОДЫ ПО КАТЕГОРИЯМ   ║\n"
        text += f"╠════════════════════════════════╣\n"
        for cat, amt in sorted(inc_by_cat.items(), key=lambda x: x[1], reverse=True):
            emoji = CATEGORIES_INCOME.get(cat, '📦')
            text += f"║ {emoji} {cat[:12]:<12} {amt:>8,.0f} ₽ ║\n"
    
    text += f"╚════════════════════════════════╝"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ========== ЗА СЕГОДНЯ ==========

@bot.message_handler(func=lambda message: message.text == '📅 За сегодня')
def show_today(message):
    user_id = str(message.chat.id)
    data = load_data()
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in data:
        bot.send_message(message.chat.id, "📭 Нет данных")
        return
    
    today_expenses = [e for e in data[user_id]['expenses'] if e['date'] == today]
    today_incomes = [i for i in data[user_id]['incomes'] if i['date'] == today]
    
    total_exp = sum(e['amount'] for e in today_expenses)
    total_inc = sum(i['amount'] for i in today_incomes)
    
    if not today_expenses and not today_incomes:
        bot.send_message(message.chat.id, f"📅 За сегодня ({datetime.now().strftime('%d.%m.%Y')}) операций нет!")
        return
    
    text = f"╔════════════════════════════════╗\n"
    text += f"║     📅 ЗА СЕГОДНЯ 📅          ║\n"
    text += f"╠════════════════════════════════╣\n"
    text += f"║ 📅 {datetime.now().strftime('%d.%m.%Y'):<26} ║\n"
    text += f"╠════════════════════════════════╣\n"
    
    if today_incomes:
        text += f"║ 💰 ДОХОДЫ:                   ║\n"
        for i in today_incomes:
            emoji = CATEGORIES_INCOME.get(i['category'], '📦')
            text += f"║    {emoji} {i['category'][:12]:<12} +{i['amount']:>8,.0f} ₽ ║\n"
    
    if today_expenses:
        if today_incomes:
            text += f"╠════════════════════════════════╣\n"
        text += f"║ 💸 РАСХОДЫ:                  ║\n"
        for e in today_expenses:
            emoji = CATEGORIES.get(e['category'], '📦')
            text += f"║    {emoji} {e['category'][:12]:<12} -{e['amount']:>8,.0f} ₽ ║\n"
    
    text += f"╠════════════════════════════════╣\n"
    text += f"║ ИТОГО: {total_inc - total_exp:>+14,.0f} ₽ ║\n"
    text += f"╚════════════════════════════════╝"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ========== ГРАФИК ==========

@bot.message_handler(func=lambda message: message.text == '📈 График')
def show_chart(message):
    user_id = str(message.chat.id)
    data = load_data()
    
    if user_id not in data or not data[user_id]['expenses']:
        bot.send_message(message.chat.id, "📭 Нет расходов для графика")
        return
    
    exp_by_cat = {}
    for e in data[user_id]['expenses']:
        cat = e['category']
        exp_by_cat[cat] = exp_by_cat.get(cat, 0) + e['amount']
    
    total = sum(exp_by_cat.values())
    
    text = f"╔════════════════════════════════╗\n"
    text += f"║      📊 ГРАФИК РАСХОДОВ 📊    ║\n"
    text += f"╠════════════════════════════════╣\n"
    
    for cat, amount in sorted(exp_by_cat.items(), key=lambda x: x[1], reverse=True):
        emoji = CATEGORIES.get(cat, '📦')
        percent = (amount / total) * 100
        bar_length = int(percent / 2)
        bar = '█' * bar_length + '░' * (25 - bar_length)
        text += f"║ {emoji} {cat[:10]:<10} {bar} {percent:>4.0f}% ║\n"
    
    text += f"╚════════════════════════════════╝\n"
    text += f"\n💰 Всего расходов: {total:,.0f} ₽"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ========== МЕСЯЧНЫЙ ОТЧЁТ ==========

@bot.message_handler(func=lambda message: message.text == '📆 Месячный отчёт')
def monthly_report(message):
    user_id = str(message.chat.id)
    data = load_data()
    
    if user_id not in data:
        bot.send_message(message.chat.id, "📭 Нет данных")
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
    
    text = f"╔════════════════════════════════╗\n"
    text += f"║     📆 МЕСЯЧНЫЙ ОТЧЁТ 📆      ║\n"
    text += f"╠════════════════════════════════╣\n"
    text += f"║ 📅 {now.strftime('%B %Y'):<26} ║\n"
    text += f"╠════════════════════════════════╣\n"
    text += f"║ 💰 Доходы:  {cur_inc_sum:>12,.0f} ₽ ║\n"
    text += f"║ 💸 Расходы: {cur_exp_sum:>12,.0f} ₽ ║\n"
    text += f"║ 📊 Баланс:  {cur_inc_sum - cur_exp_sum:>12,+.0f} ₽ ║\n"
    
    if last_exp_sum > 0 or last_inc_sum > 0:
        exp_change = ((cur_exp_sum - last_exp_sum) / last_exp_sum * 100) if last_exp_sum > 0 else 100
        inc_change = ((cur_inc_sum - last_inc_sum) / last_inc_sum * 100) if last_inc_sum > 0 else 100
        
        text += f"╠════════════════════════════════╣\n"
        text += f"║    📊 СРАВНЕНИЕ С ПРОШЛЫМ    ║\n"
        text += f"╠════════════════════════════════╣\n"
        text += f"║ 📉 Расходы: {exp_change:>+11,.1f}% ║\n"
        text += f"║ 📈 Доходы:  {inc_change:>+11,.1f}% ║\n"
    
    text += f"╚════════════════════════════════╝"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ========== АНАЛИТИКА ==========

@bot.message_handler(func=lambda message: message.text == '🔥 Аналитика')
def show_trends(message):
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
    
    # Дни недели с максимальными тратами
    weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    day_spends = {i: 0 for i in range(7)}
    for e in expenses:
        day = datetime.fromisoformat(e['timestamp']).weekday()
        day_spends[day] += e['amount']
    max_day = max(day_spends, key=day_spends.get)
    
    # Самая крупная трата
    max_expense = max(expenses, key=lambda x: x['amount'])
    max_emoji = CATEGORIES.get(max_expense['category'], '📦')
    
    text = f"╔════════════════════════════════╗\n"
    text += f"║        🔥 АНАЛИТИКА 🔥        ║\n"
    text += f"╠════════════════════════════════╣\n"
    text += f"║ 📊 ТРЕНДЫ:                    ║\n"
    text += f"║    Расходы {trend} на {abs(change):.1f}%   ║\n"
    text += f"╠════════════════════════════════╣\n"
    text += f"║ 📅 ПИК ТРАТ:                  ║\n"
    text += f"║    Больше всего по {weekdays[max_day]}м       ║\n"
    text += f"╠════════════════════════════════╣\n"
    text += f"║ 💎 САМАЯ КРУПНАЯ ТРАТА:       ║\n"
    text += f"║    {max_emoji} {max_expense['category'][:12]}: {max_expense['amount']:,.0f} ₽ ║\n"
    
    # Совет
    coffee_total = sum(e['amount'] for e in expenses if e['category'] == 'кофе')
    if coffee_total > 5000:
        text += f"╠════════════════════════════════╣\n"
        text += f"║ 💡 СОВЕТ:                     ║\n"
        text += f"║    На кофе потрачено          ║\n"
        text += f"║    {coffee_total:,.0f} ₽. Попробуй готовить дома! ║\n"
    
    text += f"╚════════════════════════════════╝"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ========== БЮДЖЕТ ==========

@bot.message_handler(func=lambda message: message.text == '🎯 Бюджет')
def budget_menu(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Установить бюджет", callback_data="set_budget"))
    markup.add(types.InlineKeyboardButton("📊 Проверить бюджет", callback_data="check_budget"))
    bot.send_message(message.chat.id, "🎯 **Управление бюджетом**\n\nУстанови лимит на месяц, и я буду показывать прогресс!", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data in ['set_budget', 'check_budget'])
def budget_handler(call):
    user_id = str(call.message.chat.id)
    data = load_data()
    
    if call.data == 'set_budget':
        msg = bot.send_message(call.message.chat.id, "💰 Введите сумму бюджета на месяц (например: 50000)")
        bot.register_next_step_handler(msg, save_budget)
        bot.answer_callback_query(call.id)
    else:
        if user_id in data and 'budget' in data[user_id]:
            budget = data[user_id]['budget']
            month_expenses = sum(e['amount'] for e in data[user_id]['expenses'] if e['date'].startswith(datetime.now().strftime('%Y-%m')))
            percent = (month_expenses / budget) * 100
            left = budget - month_expenses
            
            if percent < 80:
                status = "✅ ХОРОШО"
                status_emoji = "🟢"
            elif percent < 100:
                status = "⚠️ ВНИМАНИЕ"
                status_emoji = "🟡"
            else:
                status = "🔴 ПРЕВЫШЕН"
                status_emoji = "🔴"
            
            text = f"╔════════════════════════════════╗\n"
            text += f"║         🎯 БЮДЖЕТ 🎯          ║\n"
            text += f"╠════════════════════════════════╣\n"
            text += f"║ 💰 Лимит:    {budget:>12,.0f} ₽ ║\n"
            text += f"║ 💸 Потрачено: {month_expenses:>12,.0f} ₽ ║\n"
            text += f"║ 📊 Осталось: {left:>12,.0f} ₽ ║\n"
            text += f"║ 📈 Выполнено: {percent:>11.1f}% ║\n"
            text += f"╠════════════════════════════════╣\n"
            text += f"║ {status_emoji} Статус: {status:<19} ║\n"
            text += f"╚════════════════════════════════╝"
            
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

# ========== ЭКСПОРТ CSV ==========

@bot.message_handler(func=lambda message: message.text == '📎 Экспорт CSV')
def export_csv(message):
    user_id = str(message.chat.id)
    data = load_data()
    
    if user_id not in data or (not data[user_id]['expenses'] and not data[user_id]['incomes']):
        bot.send_message(message.chat.id, "📭 Нет данных для экспорта")
        return
    
    import io
    import csv
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Дата', 'Время', 'Категория', 'Сумма', 'Тип'])
    
    for e in data[user_id]['expenses']:
        writer.writerow([e['date'], e['time'], e['category'], e['amount'], 'Расход'])
    for i in data[user_id]['incomes']:
        writer.writerow([i['date'], i['time'], i['category'], i['amount'], 'Доход'])
    
    filename = f'finance_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    bot.send_document(message.chat.id, io.BytesIO(output.getvalue().encode('utf-8-sig')), visible_file_name=filename)
    bot.send_message(message.chat.id, "📎 Файл с данными отправлен! Можно открыть в Excel или Google Sheets")

# ========== ДОСТИЖЕНИЯ ==========

@bot.message_handler(func=lambda message: message.text == '🏆 Достижения')
def show_achievements(message):
    user_id = str(message.chat.id)
    data = load_data()
    
    if user_id not in data:
        bot.send_message(message.chat.id, "📭 Нет данных")
        return
    
    expenses = data[user_id]['expenses']
    incomes = data[user_id]['incomes']
    total_expenses = len(expenses)
    total_sum = sum(e['amount'] for e in expenses)
    
    achievements = []
    
    # Достижения по количеству трат
    if total_expenses >= 100:
        achievements.append("🏆 100 трат! Ты настоящий финансовый гуру!")
    elif total_expenses >= 50:
        achievements.append("🏅 50 трат! Отличный темп!")
    elif total_expenses >= 10:
        achievements.append("📊 10 трат! Первые шаги!")
    
    # Достижения по сумме
    if total_sum >= 1000000:
        achievements.append("💎 МИЛЛИОНЕР! Ты потратил больше миллиона!")
    elif total_sum >= 500000:
        achievements.append("💰 500к! Серьёзный уровень!")
    elif total_sum >= 100000:
        achievements.append("💵 100к! Клуб ста тысяч!")
    
    # Экономия (расходы уменьшились)
    month_ago = datetime.now() - timedelta(days=30)
    old_expenses = [e for e in expenses if datetime.fromisoformat(e['timestamp']) < month_ago]
    new_expenses = [e for e in expenses if datetime.fromisoformat(e['timestamp']) >= month_ago]
    old_sum = sum(e['amount'] for e in old_expenses)
    new_sum = sum(e['amount'] for e in new_expenses)
    if old_sum > 0 and new_sum < old_sum * 0.8:
        achievements.append("📉 ЭКОНОМИСТ! Ты сократил расходы на 20%!")
    
    # Достижение за наличие дохода
    if incomes:
        achievements.append("💼 Есть доход! Хороший знак!")
    
    if not achievements:
        achievements.append("🔰 Начинающий трекер. Добавляй больше трат и открывай достижения!")
    
    text = f"╔════════════════════════════════╗\n"
    text += f"║       🏆 ДОСТИЖЕНИЯ 🏆        ║\n"
    text += f"╠════════════════════════════════╣\n"
    
    for ach in achievements:
        text += f"║ {ach[:26]:<26} ║\n"
    
    text += f"╚════════════════════════════════╝\n\n"
    text += f"📊 Статистика:\n"
    text += f"💰 Всего трат: {total_expenses}\n"
    text += f"💸 На сумму: {total_sum:,.0f} ₽"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ========== СБРОС ==========

@bot.message_handler(func=lambda message: message.text == '🗑 Сбросить всё')
def reset_confirm(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Да, удалить всё", callback_data="reset_yes"))
    markup.add(types.InlineKeyboardButton("❌ Нет, отмена", callback_data="reset_no"))
    bot.send_message(message.chat.id, "⚠️ **ВНИМАНИЕ!** ⚠️\n\nВы уверены, что хотите удалить ВСЕ данные?\n\nЭто действие нельзя отменить!", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data in ['reset_yes', 'reset_no'])
def handle_reset(call):
    if call.data == 'reset_yes':
        user_id = str(call.message.chat.id)
        data = load_data()
        if user_id in data:
            data[user_id] = {'expenses': [], 'incomes': []}
            save_data(data)
        bot.edit_message_text("✅ Все данные удалены!", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Начните с чистого листа! /start")
    else:
        bot.edit_message_text("❌ Удаление отменено.", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)

# ========== БЫСТРЫЙ ВВОД ==========

@bot.message_handler(func=lambda message: message.text and not message.text.startswith('/') and not any(message.text.startswith(x) for x in ['💰', '💵', '📊', '📅', '📈', '📆', '🔥', '🎯', '📎', '🏆', '🗑']))
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
            bot.reply_to(message, f"✅ Доход добавлен: {emoji} {category} - {amount:,.0f} ₽")
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
            bot.reply_to(message, f"✅ Расход добавлен: {emoji} {category} - {amount:,.0f} ₽")
    else:
        bot.reply_to(message, "❓ Не понял. Напиши /start для меню\nИли добавь: категория сумма\nПример: еда 500 или зарплата 50000")

# ========== ЗАПУСК ==========

def run_bot():
    print("✅ БОТ ЗАПУЩЕН!")
    print("📊 Все функции бесплатны!")
    print("💰 Трекер расходов и доходов работает!")
    bot.infinity_polling()

@server.route('/')
def hello():
    return "Бот работает!"

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    port = int(os.environ.get('PORT', 5000))
    server.run(host='0.0.0.0', port=port)
