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

# ========== ЦЕНЫ НА ПОДПИСКУ ==========
SUBSCRIPTIONS = {
    1: {'days': 30, 'price': 50, 'name': '1 месяц', 'discount': 0},
    3: {'days': 90, 'price': 135, 'name': '3 месяца', 'discount': 10},
    6: {'days': 180, 'price': 240, 'name': '6 месяцев', 'discount': 20},
    12: {'days': 365, 'price': 420, 'name': '12 месяцев', 'discount': 30}
}

# ========== ФУНКЦИИ ПОДПИСКИ ==========
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
    data = load_data()
    user_id = str(user_id)
    if user_id not in data:
        data[user_id] = {'expenses': [], 'incomes': []}
    days = SUBSCRIPTIONS[months]['days']
    new_expiry = datetime.now() + timedelta(days=days)
    if 'premium_until' in data[user_id]:
        old_expiry = datetime.fromisoformat(data[user_id]['premium_until'])
        if old_expiry > datetime.now():
            new_expiry = old_expiry + timedelta(days=days)
    data[user_id]['premium_until'] = new_expiry.isoformat()
    data[user_id]['subscription_months'] = months
    save_data(data)
    return new_expiry

# ========== КЛАВИАТУРА ==========
def get_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('💰 Добавить расход', '💵 Добавить доход')
    markup.add('📊 Статистика', '📅 За сегодня')
    markup.add('📈 График', '⭐ ПРЕМИУМ')
    markup.add('🗑 Сбросить всё')
    return markup

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if is_premium(user_id):
        expiry = get_premium_expiry(user_id)
        expiry_str = expiry.strftime("%d.%m.%Y") if expiry else "неизвестно"
        status = f"👑 ПРЕМИУМ АКТИВЕН до {expiry_str} 👑"
    else:
        status = "🔓 БЕСПЛАТНЫЙ ТАРИФ 🔓\n⭐ Купи Premium за 50 Stars!"
    
    text = f"""💰 Привет, {message.from_user.first_name}!

{status}

📝 Просто напиши: «еда 500» или «зарплата 50000»

💎 ПРЕМИУМ (50 Stars/мес):
• Аналитика трендов
• Умный бюджет
• Экспорт CSV
• Напоминания
• Достижения
• Советы по экономии

📅 Чем дольше, тем выгоднее:
3 мес → 135 ⭐ (-10%)
6 мес → 240 ⭐ (-20%)
12 мес → 420 ⭐ (-30%)"""
    
    bot.send_message(message.chat.id, text, reply_markup=get_keyboard())

@bot.message_handler(func=lambda message: message.text == '⭐ ПРЕМИУМ')
def show_premium(message):
    text = """⭐ ПРЕМИУМ ПОДПИСКА ⭐

Выбери срок:

📅 1 месяц — 50 ⭐
📅 3 месяца — 135 ⭐ (экономия 15 ⭐)
📅 6 месяцев — 240 ⭐ (экономия 60 ⭐)
📅 12 месяцев — 420 ⭐ (экономия 180 ⭐)

💡 Чем дольше, тем выгоднее!"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for months, info in SUBSCRIPTIONS.items():
        markup.add(types.InlineKeyboardButton(
            f"📅 {info['name']} — {info['price']} ⭐",
            callback_data=f"buy_{months}"
        ))
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def process_purchase(call):
    months = int(call.data.split('_')[1])
    info = SUBSCRIPTIONS[months]
    
    prices = [types.LabeledPrice(label=f"Premium {info['name']}", amount=info['price'])]
    
    bot.send_invoice(
        call.message.chat.id,
        title=f"⭐ Premium - {info['name']}",
        description=f"Premium доступ на {info['days']} дней.\n\nФункции:\n• Аналитика трендов\n• Умный бюджет\n• Экспорт CSV\n• Напоминания\n• Достижения\n• Советы по экономии",
        invoice_payload=f"premium_{months}",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter=f"premium_{months}"
    )
    bot.answer_callback_query(call.id)

@bot.pre_checkout_query_handler(func=lambda query: True)
def on_pre_checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def on_payment(message):
    payload = message.successful_payment.invoice_payload
    months = int(payload.split('_')[1])
    expiry = activate_premium(message.chat.id, months)
    expiry_str = expiry.strftime("%d.%m.%Y")
    
    text = f"""✅ ОПЛАТА ПРОШЛА!

🎉 Premium активирован до {expiry_str}

🔥 Тебе доступны все функции:
• Аналитика трендов
• Умный бюджет
• Экспорт данных
• Напоминания
• Достижения

Используй /start для начала!"""
    
    bot.send_message(message.chat.id, text)
    start(message)

@bot.message_handler(commands=['check'])
def check(message):
    if is_premium(message.chat.id):
        expiry = get_premium_expiry(message.chat.id)
        text = f"👑 Статус: PREMIUM\n📅 Активен до: {expiry.strftime('%d.%m.%Y')}"
    else:
        text = "🔓 Статус: БЕСПЛАТНЫЙ\n⭐ Купи Premium: /premium"
    bot.send_message(message.chat.id, text)

# ========== ПРЕМИУМ-ФУНКЦИИ (с проверкой) ==========
@bot.message_handler(func=lambda message: message.text == '📊 Статистика')
def show_stats(message):
    user_id = str(message.chat.id)
    data = load_data()
    premium = is_premium(message.chat.id)
    
    if user_id not in data or (not data[user_id].get('expenses') and not data[user_id].get('incomes')):
        bot.send_message(message.chat.id, "📭 Нет данных")
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
    
    text = f"📊 СТАТИСТИКА\n\n💰 Доходы: {total_inc:,.0f} ₽\n💸 Расходы: {total_exp:,.0f} ₽\n📊 Баланс: {balance:+,.0f} ₽\n\n📉 Расходы по категориям:\n"
    
    for cat, amt in sorted(exp_by_cat.items(), key=lambda x: x[1], reverse=True)[:5]:
        text += f"{CATEGORIES.get(cat, '📦')} {cat}: {amt:,.0f} ₽\n"
    
    # Premium аналитика
    if premium:
        if expenses:
            avg = total_exp / len(expenses)
            text += f"\n🌟 ПРЕМИУМ АНАЛИТИКА:\n📊 Средний чек: {avg:,.0f} ₽"
        
        # Проверка бюджета
        if 'budget' in data[user_id]:
            budget = data[user_id]['budget']
            month_exp = sum(e['amount'] for e in expenses if e['date'].startswith(datetime.now().strftime('%Y-%m')))
            percent = (month_exp / budget) * 100
            if percent > 100:
                text += f"\n⚠️ Бюджет превышен на {percent-100:.0f}%!"
            elif percent > 80:
                text += f"\n⚠️ Осталось {budget-month_exp:,.0f} ₽ до лимита"
    else:
        text += f"\n\n⭐ Купи Premium за 50 Stars, чтобы видеть аналитику, бюджет и экспорт!"
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda message: message.text == '💰 Добавить расход')
def ask_expense(message):
    msg = bot.send_message(message.chat.id, "📝 Напиши: категория сумма\nПример: еда 500")
    bot.register_next_step_handler(msg, save_transaction, 'expense')

@bot.message_handler(func=lambda message: message.text == '💵 Добавить доход')
def ask_income(message):
    msg = bot.send_message(message.chat.id, "📝 Напиши: категория сумма\nПример: зарплата 50000")
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
        bot.send_message(message.chat.id, f"✅ Расход: {CATEGORIES.get(category, '📦')} {category} - {amount} ₽")
    else:
        data[user_id]['incomes'].append(transaction)
        bot.send_message(message.chat.id, f"✅ Доход: {CATEGORIES_INCOME.get(category, '📦')} {category} - {amount} ₽")
    
    save_data(data)

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
    bot.send_message(message.chat.id, "⚠️ Удалить все данные?", reply_markup=markup)

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

@bot.message_handler(func=lambda message: message.text and not message.text.startswith('/') and not any(message.text.startswith(x) for x in ['💰', '💵', '📊', '📅', '📈', '⭐', '🗑']))
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
            bot.reply_to(message, f"✅ Доход: {CATEGORIES_INCOME.get(category, '📦')} {category} - {amount} ₽")
        else:
            if category not in CATEGORIES:
                category = 'прочее'
            data[user_id]['expenses'].append({
                'amount': amount, 'category': category,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'time': datetime.now().strftime('%H:%M:%S'),
                'timestamp': datetime.now().isoformat()
            })
            bot.reply_to(message, f"✅ Расход: {CATEGORIES.get(category, '📦')} {category} - {amount} ₽")
        save_data(data)
    else:
        bot.reply_to(message, "❓ Не понял. Напиши /start")

# ========== ЗАПУСК ==========
def run_bot():
    print("✅ Бот с Premium подпиской работает!")
    bot.infinity_polling()

@server.route('/')
def hello():
    return "OK"

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    port = int(os.environ.get('PORT', 5000))
    server.run(host='0.0.0.0', port=port)
