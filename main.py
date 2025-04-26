import os
import logging
from aiogram import Bot, Dispatcher, types, executor
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
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

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
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    saldo = obtener_saldo()
    if saldo is not None:
        await message.answer(f"¡Bienvenido, tu bot está vinculado correctamente!\nSaldo actual en Spot: {saldo:.2f} USDT")
    else:
        await message.answer("¡Bienvenido, tu bot está vinculado!\nNo se pudo obtener el saldo. Verifica tus API Keys.")

# Inicializar Flask
app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot funcionando correctamente.'

if __name__ == '__main__':
    from threading import Thread

    # Lanzar el bot en segundo plano
    def run_bot():
        executor.start_polling(dp, skip_updates=True)

    Thread(target=run_bot).start()

    # Correr servidor Flask
    app.run(host='0.0.0.0', port=5000)