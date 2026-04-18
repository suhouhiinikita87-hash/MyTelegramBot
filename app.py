import os
import telebot
from flask import Flask
import threading

TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "✅ Бот работает! Версия с подпиской загружена правильно!")

def run_bot():
    print("Бот запущен")
    bot.infinity_polling()

@server.route('/')
def hello():
    return "OK"

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    port = int(os.environ.get('PORT', 5000))
    server.run(host='0.0.0.0', port=port)
