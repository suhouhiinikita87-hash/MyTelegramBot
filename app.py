import os
import telebot
from flask import Flask, request
import threading

# --- 1. Берем токен из переменных окружения Render ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("Переменная TELEGRAM_TOKEN не найдена!")

bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

# --- 2. Твои обработчики команд (остаются прежними) ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привет! Я бот, работающий на Render 24/7! 🚀")

@bot.message_handler(func=lambda message: True)
def echo(message):
    bot.reply_to(message, "Эхо: " + message.text)

# --- 3. Функция запуска бота в фоновом режиме (Polling) ---
def run_bot():
    print("Бот запущен и работает...")
    bot.infinity_polling()

# --- 4. Веб-сервер для Render (чтобы он не ругался на отсутствие порта) ---
@server.route('/')
def hello():
    return "Я бот, я жив!"

# Эта команда нужна, чтобы Render знал, по какому порту слушать
if __name__ == "__main__":
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    
    # Запускаем веб-сервер (это нужно для Render, чтобы он не упал с ошибкой "No open ports")
    port = int(os.environ.get('PORT', 5000))
    server.run(host='0.0.0.0', port=port)