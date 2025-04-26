import os
import asyncio
from aiogram import Bot
from flask import Flask

app = Flask(__name__)

# Variables de entorno
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Crear bot
bot = Bot(token=API_TOKEN)

@app.route('/')
async def home():
    return 'Bot funcionando correctamente.'

async def start_bot():
    await bot.send_message(chat_id=CHAT_ID, text="✅ Bot arrancado correctamente.")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    app.run(host='0.0.0.0', port=5000)