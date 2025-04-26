import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from flask import Flask
import requests

# Configurar logs
logging.basicConfig(level=logging.INFO)

# Variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Crear bot y dispatcher
bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# Función para obtener saldo en Spot
def obtener_saldo():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/assets"
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        if data['code'] == 0:
            for asset in data['data']:
                if asset['asset'] == 'USDT':
                    return float(asset['balance'])
        else:
            return None
    else:
        return None

# Comando /start
@dp.message(commands=['start'])
async def start_handler(message: types.Message):
    saldo = obtener_saldo()
    if saldo is not None:
        await message.answer(f"✅ ¡Bot vinculado correctamente!\n\n<b>Saldo disponible:</b> {saldo:.2f} USDT")
    else:
        await message.answer("⚠️ Bot vinculado, pero no se pudo obtener el saldo.\nVerifica tus API Keys.")

# Inicializar Flask
app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot funcionando correctamente.'

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    from threading import Thread

    # Lanzar el bot en segundo plano
    def run_bot():
        asyncio.run(main())

    Thread(target=run_bot).start()

    # Correr servidor Flask
    app.run(host='0.0.0.0', port=5000)