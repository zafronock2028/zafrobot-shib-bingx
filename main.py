import logging
import requests
import time
import hmac
import hashlib
import json
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from flask import Flask
import threading
import asyncio
import os

# Tus credenciales de BingX
api_key = 'LCRNrSVWUf1crSsLEEtrdDzyIUWdNVteIJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA'
secret_key = 'Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg'

# Token de tu bot de Telegram
BOT_TOKEN = '7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM'

# Inicializar bot y dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Crear servidor Flask para mantener Render activo
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot Notifier PRO corriendo."

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    server = threading.Thread(target=run)
    server.start()

# Función para obtener saldo actualizado en Spot
def obtener_saldo_spot_usdt(api_key, secret_key):
    try:
        timestamp = str(int(time.time() * 1000))
        params = f'timestamp={timestamp}'
        signature = hmac.new(secret_key.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()

        headers = {
            'X-BX-APIKEY': api_key
        }

        url = f"https://open-api.bingx.com/openApi/spot/v1/account/balance?{params}&signature={signature}"
        response = requests.get(url, headers=headers)
        data = response.json()

        if data['code'] == 0:
            balances = data['data']['balances']
            for balance in balances:
                if balance['asset'] == 'USDT':
                    free_balance = float(balance['free'])
                    return free_balance
            return 0.0
        else:
            logging.error(f"Error en API BingX: {data.get('msg', 'Error desconocido')}")
            return None
    except Exception as e:
        logging.error(f"Error obteniendo saldo Spot: {str(e)}")
        return None

# Comando /start
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer("✅ Bot activo y listo.\n👉 Usa /saldo para ver tu saldo Spot actualizado.")

# Comando /saldo
@dp.message(Command(commands=["saldo"]))
async def saldo_handler(message: Message):
    await message.answer("⏳ Consultando saldo en tiempo real...")
    saldo = obtener_saldo_spot_usdt(api_key, secret_key)
    if saldo is not None:
        await message.answer(
            f"🪙 <b>ZafroBot Wallet</b>\n\n"
            f"💰 Saldo USDT disponible en Spot:\n<b>{saldo:.2f} USDT</b>\n\n"
            f"🕒 <i>Actualizado en tiempo real</i>",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer("⚠️ No se pudo obtener el saldo. Intenta nuevamente en unos segundos.")

# Función principal
async def main():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())