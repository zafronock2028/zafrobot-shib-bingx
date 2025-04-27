import logging
import os
import hmac
import hashlib
import time
import json
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# Activar el logging para depuración
logging.basicConfig(level=logging.INFO)

# Variables directas
API_KEY = "LCRNrSVWUf1crSsLE5+rdPxjTUWdNVte"  # La tuya
SECRET_KEY = "Kckg5g1hCDsE9N83p8wpxDiWk9fc6TZY"  # La tuya
TELEGRAM_BOT_TOKEN = "8100886306:AAFRDnn32wMKXhZGfkThifFFGPhL0p6KFjw"  # Nuevo Token actualizado
CHAT_ID = "1130366010"  # Tu Chat ID correcto

# Inicializar el bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

# Formato del saldo
def formatear_tarjeta(saldo):
    return (
        "┌───────────────┐\n"
        "│ 📋 Saldo en Spot │\n"
        "├───────────────┤\n"
        f"│ 💵 Moneda: USDT │\n"
        f"│ 📈 Disponible: {saldo:.2f} │\n"
        "└───────────────┘\n"
        "🕒 Consulta en tiempo real"
    )

# Función para obtener saldo
async def obtener_saldo_usdt():
    url = "https://open-api.bingx.com/openApi/user/spot/assets"
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    params = {
        "timestamp": timestamp,
        "signature": signature
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                usdt_balance = next((item for item in data['data']['assets'] if item['asset'] == 'USDT'), None)
                if usdt_balance:
                    return float(usdt_balance['free'])
                else:
                    return 0.0
            else:
                logging.error(f"Error en la API: {resp.status}")
                return 0.0

# Comando /start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("👋 ¡Bienvenido a ZafroBot Notifier 2!\n\nEnvía /saldo para consultar tu saldo en tiempo real.")

# Comando /saldo
@dp.message_handler(commands=['saldo'])
async def saldo_handler(message: types.Message):
    saldo = await obtener_saldo_usdt()
    texto_saldo = formatear_tarjeta(saldo)
    await message.reply(texto_saldo)

# Iniciar bot
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)