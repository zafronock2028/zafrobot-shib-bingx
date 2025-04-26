import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from flask import Flask

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Inicializar Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot Dinámico Pro está activo."

# Variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = int(os.getenv('CHAT_ID'))

# Inicializar el bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

async def enviar_mensaje(texto):
    await bot.send_message(chat_id=CHAT_ID, text=texto)

async def main():
    await enviar_mensaje("✅ ¡ZafroBot Dinámico Pro está funcionando correctamente!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    app.run(host="0.0.0.0", port=5000)