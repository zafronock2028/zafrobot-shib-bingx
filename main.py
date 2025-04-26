import os
import asyncio
from aiogram import Bot, Dispatcher, types
from flask import Flask

app = Flask(__name__)

# Variables de entorno
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Crear bot y dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@app.route('/')
async def home():
    return 'Bot funcionando correctamente.'

async def start_bot():
    try:
        saldo = obtener_saldo()  # Aquí implementas tu lógica
        if saldo is not None:
            await bot.send_message(chat_id=CHAT_ID, text=f'Saldo: {saldo}')
        else:
            await bot.send_message(chat_id=CHAT_ID, text='No se pudo obtener el saldo.')
    except Exception as e:
        await bot.send_message(chat_id=CHAT_ID, text=f'Error: {e}')

def obtener_saldo():
    # Aquí va la lógica real para obtener el saldo
    return None

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    app.run(host='0.0.0.0', port=5000)