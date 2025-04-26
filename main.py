from flask import Flask
from threading import Thread
import asyncio
from aiogram import Bot, Dispatcher, types

import os

# Variables de entorno
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Define el servidor Flask para mantener vivo
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot está funcionando correctamente."

def run():
    app.run(host="0.0.0.0", port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Manejador de mensajes simples
@dp.message()
async def echo(message: types.Message):
    await message.answer("✅ Bot activo y recibiendo mensajes correctamente.")

async def main():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())