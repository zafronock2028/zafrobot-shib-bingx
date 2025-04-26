from flask import Flask
from threading import Thread
import os
import time
import requests
from aiogram import Bot, Dispatcher, types
import asyncio

# --- Keep Alive ---
app = Flask('')

@app.route('/')
def home():
    return "ZafroBot está funcionando correctamente."

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Telegram Bot ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

async def send_notification():
    await bot.send_message(chat_id=CHAT_ID, text="✅ Prueba de notificación enviada correctamente.")

async def main():
    while True:
        await send_notification()
        await asyncio.sleep(600)  # Cada 10 minutos (puedes cambiar el tiempo)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())