import os
import telebot
from telebot import types
from flask import Flask
import threading

# --- Токен из переменных окружения Railway ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("Переменная TELEGRAM_TOKEN не найдена!")

bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

# --- КОМАНДА /start - приветствие с именем пользователя ---
@bot.message_handler(commands=['start'])
def start(message):
    # Получаем имя пользователя (если есть)
    user_first_name = message.from_user.first_name
    user_last_name = message.from_user.last_name
    user_full_name = f"{user_first_name} {user_last_name}" if user_last_name else user_first_name
    
    # Создаем клавиатуру с кнопками
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Кнопки
    btn_hello = types.KeyboardButton('👋 Сказать привет')
    btn_time = types.KeyboardButton('🕐 Время')
    btn_weather = types.KeyboardButton('☀️ Погода')
    btn_help = types.KeyboardButton('❓ Помощь')
    
    # Добавляем кнопки
    markup.add(btn_hello, btn_time, btn_weather, btn_help)
    
    # Приветственное сообщение с именем
    welcome_text = f"""🌟 Привет, {user_full_name}! 🌟

Я твой личный бот-помощник! 🤖

Нажми на любую кнопку ниже, чтобы я мог помочь тебе."""
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

# --- ОБРАБОТЧИКИ КНОПОК ---
@bot.message_handler(func=lambda message: message.text == '👋 Сказать привет')
def say_hello(message):
    user_name = message.from_user.first_name
    bot.reply_to(message, f"Привет, {user_name}! Рад тебя видеть! 😊")

@bot.message_handler(func=lambda message: message.text == '🕐 Время')
def tell_time(message):
    from datetime import datetime
    now = datetime.now()
    time_str = now.strftime("%H:%M:%S")
    date_str = now.strftime("%d.%m.%Y")
    bot.reply_to(message, f"📅 Сегодня {date_str}\n🕐 Точное время: {time_str}")

@bot.message_handler(func=lambda message: message.text == '☀️ Погода')
def tell_weather(message):
    # Простой ответ (можно позже подключить реальное API погоды)
    bot.reply_to(message, "☀️ Сегодня отличная погода для программирования!\n\n🌡️ Температура: +22°C\n💨 Ветер: 5 м/с\n💧 Влажность: 65%")

@bot.message_handler(func=lambda message: message.text == '❓ Помощь')
def help_command(message):
    help_text = """📖 **Что я умею:**

/start - Показать главное меню
👋 Сказать привет - Поздороваться со мной
🕐 Время - Узнать текущее время
☀️ Погода - Узнать погоду
❓ Помощь - Показать это сообщение

💡 Просто нажми на кнопку или напиши мне что-нибудь!"""
    
    bot.reply_to(message, help_text, parse_mode='Markdown')

# --- ЭХО ДЛЯ ВСЕХ ОСТАЛЬНЫХ СООБЩЕНИЙ ---
@bot.message_handler(func=lambda message: True)
def echo(message):
    # Проверяем, не является ли сообщение нажатием на кнопку
    if message.text.startswith('👋') or message.text.startswith('🕐') or message.text.startswith('☀️') or message.text.startswith('❓'):
        return  # Кнопки уже обработаны выше
    
    # Если просто текст - отвечаем эхом
    bot.reply_to(message, f"Ты написал: {message.text}\n\nНажми /start для открытия меню!")

# --- Функция запуска бота ---
def run_bot():
    print("Бот запущен и работает...")
    print("Доступные команды: /start")
    bot.infinity_polling()

# --- Веб-сервер для Railway ---
@server.route('/')
def hello():
    return "Я бот, я жив!"

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    server.run(host='0.0.0.0', port=port)
