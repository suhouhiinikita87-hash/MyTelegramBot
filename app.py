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
    'шопинг': '🛍️', 'здоровье': '💊', 'прочее': '📦'
}
CATEGORIES_INCOME = {
    'зарплата': '💰', 'фриланс': '💻', 'подарок': '🎁', 'прочее': '📦'
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
    markup.add('📈 График', '🗑 Сбросить всё')
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 
        f"💰 Привет, {message.from_user.first_name}!\n\n"
        f"Я трекер расходов и доходов.\n\n"
        f"📝 Просто напиши: «еда 500» или «зарплата 50000»\n\n"
        f"Или используй кнопки меню 👇",
        reply_markup=get_keyboard())

@bot.message_handler(func=lambda message: message.text == '💰 Добавить расход')
def ask_expense(message):
    msg = bot.send_message(message.chat.id, "Напиши: категория сумма\nПример: еда 500")
    bot.register_next_step_handler(msg, save_transaction, 'expense')

@bot.message_handler(func=lambda message: message.text == '💵 Добавить доход')
def ask_income(message):
    msg = bot.send_message(message.chat.id, "Напиши: категория сумма\nПример: зарплата 50000")
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
        bot.send_message(message.chat.id, f"✅ Расход: {category} - {amount} ₽")
    else:
        data[user_id]['incomes'].append(transaction)
        bot.send_message(message.chat.id, f"✅ Доход: {category} - {amount} ₽")
    
    save_data(data)

@bot.message_handler(func=lambda message: message.text == '📊 Статистика')
def show_stats(message):
    user_id = str(message.chat.id)
    data = load_data()
    
    if user_id not in data:
        bot.send_message(message.chat.id, "📭 Нет данных")
        return
    
    expenses = data[user_id]['expenses']
    incomes = data[user_id]['incomes']
    total_exp = sum(e['amount'] for e in expenses)
    total_inc = sum(i['amount'] for i in incomes)
    balance = total_inc - total_exp
    
    text = f"📊 СТАТИСТИКА\n\n💰 Доходы: {total_inc:,.0f} ₽\n💸 Расходы: {total_exp:,.0f} ₽\n📊 Баланс: {balance:+,.0f} ₽"
    bot.send_message(message.chat.id, text)

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
    
    text = f"📅 ЗА СЕГОДНЯ\n\n💰 Доходы: +{total_inc:,.0f} ₽\n💸 Расходы: -{total_exp:,.0f} ₽\n📊 Итого: {total_inc - total_exp:+,.0f} ₽"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda message: message.text == '📈 График')
def show_chart(message):
    user_id = str(message.chat.id)
    data = load_data()
    
    if user_id not in data or not data[user_id]['expenses']:
        bot.send_message(message.chat.id, "📭 Нет расходов")
        return
    
    exp_by_cat = {}
    for e in data[user_id]['expenses']:
        cat = e['category']
        exp_by_cat[cat] = exp_by_cat.get(cat, 0) + e['amount']
    
    total = sum(exp_by_cat.values())
    text = "📊 ГРАФИК РАСХОДОВ\n\n"
    
    for cat, amount in sorted(exp_by_cat.items(), key=lambda x: x[1], reverse=True):
        percent = (amount / total) * 100
        bar = '█' * int(percent / 2)
        text += f"{CATEGORIES.get(cat, '📦')} {cat}: {bar} {percent:.0f}%\n"
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda message: message.text == '🗑 Сбросить всё')
def reset_confirm(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Да", callback_data="reset_yes"))
    markup.add(types.InlineKeyboardButton("❌ Нет", callback_data="reset_no"))
    bot.send_message(message.chat.id, "Удалить все данные?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['reset_yes', 'reset_no'])
def handle_reset(call):
    if call.data == 'reset_yes':
        user_id = str(call.message.chat.id)
        data = load_data()
        if user_id in data:
            data[user_id] = {'expenses': [], 'incomes': []}
            save_data(data)
        bot.edit_message_text("✅ Данные удалены", call.message.chat.id, call.message.message_id)
    else:
        bot.edit_message_text("❌ Отменено", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: message.text and not message.text.startswith('/') and not message.text.startswith('💰') and not message.text.startswith('💵') and not message.text.startswith('📊') and not message.text.startswith('📅') and not message.text.startswith('📈') and not message.text.startswith('🗑'))
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
            data[user_id]['incomes'].append({
                'amount': amount, 'category': category,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'time': datetime.now().strftime('%H:%M:%S'),
                'timestamp': datetime.now().isoformat()
            })
            bot.reply_to(message, f"✅ Доход: {category} - {amount} ₽")
        else:
            if category not in CATEGORIES:
                category = 'прочее'
            data[user_id]['expenses'].append({
                'amount': amount, 'category': category,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'time': datetime.now().strftime('%H:%M:%S'),
                'timestamp': datetime.now().isoformat()
            })
            bot.reply_to(message, f"✅ Расход: {category} - {amount} ₽")
        save_data(data)
    else:
        bot.reply_to(message, "❓ Не понял. Напиши /start")

def run_bot():
    print("✅ Бот работает!")
    bot.infinity_polling()

@server.route('/')
def hello():
    return "OK"

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    port = int(os.environ.get('PORT', 5000))
    server.run(host='0.0.0.0', port=port)
