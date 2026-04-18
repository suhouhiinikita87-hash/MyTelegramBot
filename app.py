import os
import telebot
from telebot import types
from flask import Flask
import threading
import json
from datetime import datetime
import os.path

# --- Токен из переменных окружения Railway ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("Переменная TELEGRAM_TOKEN не найдена!")

bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

# Файл для хранения расходов
DATA_FILE = 'expenses.json'

# Загрузка данных о расходах
def load_expenses():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# Сохранение расходов
def save_expenses(expenses):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(expenses, f, ensure_ascii=False, indent=2)

# --- КОМАНДА /start ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.chat.id)
    
    # Создаем клавиатуру
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    btn_add = types.KeyboardButton('➕ Добавить расход')
    btn_stats = types.KeyboardButton('📊 Статистика')
    btn_today = types.KeyboardButton('📅 Расходы за сегодня')
    btn_reset = types.KeyboardButton('🗑 Сбросить всё')
    
    markup.add(btn_add, btn_stats, btn_today, btn_reset)
    
    bot.send_message(
        message.chat.id,
        f"💰 Привет, {message.from_user.first_name}!\n\n"
        f"Я помогу тебе отслеживать расходы.\n\n"
        f"➕ Добавить расход - записать трату\n"
        f"📊 Статистика - посмотреть аналитику\n"
        f"📅 Расходы за сегодня - что потратил сегодня\n"
        f"🗑 Сбросить всё - удалить все данные\n\n"
        f"Или просто напиши: «кофе 150» или «еда 500»",
        reply_markup=markup
    )

# --- Обработчик добавления расхода (через кнопку) ---
@bot.message_handler(func=lambda message: message.text == '➕ Добавить расход')
def ask_for_expense(message):
    msg = bot.send_message(message.chat.id, "Напиши расход в формате:\n\n"
                           "📝 **категория сумма**\n\n"
                           "Примеры:\n"
                           "• еда 500\n"
                           "• транспорт 200\n"
                           "• кофе 150\n\n"
                           "Или просто сумму: 300 (категория будет «прочее»)", 
                           parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_expense_from_message)

def save_expense_from_message(message):
    user_id = str(message.chat.id)
    text = message.text.strip()
    
    # Разбираем сообщение
    parts = text.split()
    
    if len(parts) == 1 and parts[0].isdigit():
        # Только сумма
        amount = float(parts[0])
        category = "прочее"
    elif len(parts) >= 2 and parts[-1].isdigit():
        # Категория и сумма
        amount = float(parts[-1])
        category = ' '.join(parts[:-1]).lower()
    else:
        bot.send_message(message.chat.id, "❌ Неправильный формат. Попробуй ещё раз:\n\n"
                         "Напиши: **категория сумма**\nПример: еда 500", 
                         parse_mode='Markdown')
        return
    
    # Загружаем расходы
    expenses = load_expenses()
    if user_id not in expenses:
        expenses[user_id] = []
    
    # Добавляем расход
    expense = {
        'amount': amount,
        'category': category,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M:%S'),
        'timestamp': datetime.now().isoformat()
    }
    expenses[user_id].append(expense)
    save_expenses(expenses)
    
    bot.send_message(
        message.chat.id,
        f"✅ Добавлено: {category} - {amount} ₽\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

# --- Обработчик для текстовых сообщений (просто сумма или категория сумма) ---
@bot.message_handler(func=lambda message: message.text and not message.text.startswith('/') and not message.text.startswith('➕') and not message.text.startswith('📊') and not message.text.startswith('📅') and not message.text.startswith('🗑'))
def handle_text_expense(message):
    # Проверяем, не является ли сообщение цифрой или форматом "категория сумма"
    text = message.text.strip()
    parts = text.split()
    
    # Если похоже на расход (цифра в конце)
    if len(parts) >= 1 and parts[-1].isdigit():
        save_expense_from_message(message)
    else:
        bot.send_message(message.chat.id, 
                        "❓ Я не понял. Напиши /start для меню\n\n"
                        "Или добавь расход в формате:\n"
                        "• еда 500\n"
                        "• кофе 150\n"
                        "• 300 (будет сохранено как 'прочее')")

# --- Статистика ---
@bot.message_handler(func=lambda message: message.text == '📊 Статистика')
def show_stats(message):
    user_id = str(message.chat.id)
    expenses = load_expenses()
    
    if user_id not in expenses or not expenses[user_id]:
        bot.send_message(message.chat.id, "📭 У вас пока нет расходов. Добавьте первый расход!")
        return
    
    user_expenses = expenses[user_id]
    total = sum(e['amount'] for e in user_expenses)
    
    # Считаем по категориям
    categories = {}
    for e in user_expenses:
        cat = e['category']
        categories[cat] = categories.get(cat, 0) + e['amount']
    
    # Формируем сообщение
    stats_text = f"📊 **Ваша статистика расходов**\n\n"
    stats_text += f"💰 **Всего потрачено:** {total} ₽\n"
    stats_text += f"📝 **Количество трат:** {len(user_expenses)}\n"
    stats_text += f"📈 **Средний чек:** {total/len(user_expenses):.0f} ₽\n\n"
    stats_text += f"**📂 По категориям:**\n"
    
    # Сортируем по сумме (от больших к меньшим)
    sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)
    for cat, amount in sorted_cats[:10]:  # Показываем топ-10 категорий
        percent = (amount / total) * 100
        stats_text += f"• {cat}: {amount} ₽ ({percent:.1f}%)\n"
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

# --- Расходы за сегодня ---
@bot.message_handler(func=lambda message: message.text == '📅 Расходы за сегодня')
def show_today(message):
    user_id = str(message.chat.id)
    expenses = load_expenses()
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in expenses or not expenses[user_id]:
        bot.send_message(message.chat.id, "📭 У вас пока нет расходов.")
        return
    
    today_expenses = [e for e in expenses[user_id] if e['date'] == today]
    
    if not today_expenses:
        bot.send_message(message.chat.id, f"📅 За сегодня ({datetime.now().strftime('%d.%m.%Y')}) расходов нет! 🎉")
        return
    
    total_today = sum(e['amount'] for e in today_expenses)
    text = f"📅 **Расходы за сегодня ({datetime.now().strftime('%d.%m.%Y')})**\n\n"
    text += f"💰 Всего: {total_today} ₽\n\n"
    text += f"**📝 Список:**\n"
    
    for e in today_expenses:
        text += f"• {e['category']}: {e['amount']} ₽ ({e['time']})\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# --- Сбросить всё ---
@bot.message_handler(func=lambda message: message.text == '🗑 Сбросить всё')
def reset_confirm(message):
    markup = types.InlineKeyboardMarkup()
    btn_yes = types.InlineKeyboardButton('✅ Да, удалить всё', callback_data='reset_yes')
    btn_no = types.InlineKeyboardButton('❌ Нет, отмена', callback_data='reset_no')
    markup.add(btn_yes, btn_no)
    
    bot.send_message(message.chat.id, "⚠️ **ВНИМАНИЕ!** ⚠️\n\nВы уверены, что хотите удалить ВСЕ данные о расходах?\n\nЭто действие нельзя отменить!", 
                    parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['reset_yes', 'reset_no'])
def handle_reset(call):
    if call.data == 'reset_yes':
        user_id = str(call.message.chat.id)
        expenses = load_expenses()
        if user_id in expenses:
            expenses[user_id] = []
            save_expenses(expenses)
        bot.edit_message_text("✅ Все ваши расходы удалены!", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Начните с чистого листа! /start")
    else:
        bot.edit_message_text("❌ Удаление отменено.", call.message.chat.id, call.message.message_id)
    
    bot.answer_callback_query(call.id)

# --- Функция запуска бота ---
def run_bot():
    print("💰 Бот-трекер расходов запущен!")
    print("Доступные команды: /start")
    bot.infinity_polling()

# --- Веб-сервер для Railway ---
@server.route('/')
def hello():
    return "Бот-трекер расходов работает!"

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    server.run(host='0.0.0.0', port=port)
