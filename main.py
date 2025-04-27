import logging
import os
import hmac
import hashlib
import time
import json
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram import Router

# Configuración
API_KEY = "LCRNrSVWUf1crSsLE5+rdPxjTUWdNVte"
SECRET_KEY = "Kckg5g1hCDsE9N83p8wpxDiWk9fc6TZY"
TELEGRAM_BOT_TOKEN = "8100886306:AAFRDnn32wMKXhZGfkThifFFGPhL0p6KFjw"
CHAT_ID = "1130366010"

# Inicializar bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
router = Router()

# Formato de saldo
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

# Función para consultar saldo
async def obtener_saldo_usdt():
    url = "https://open-api.bingx.com/openApi/user/spot/assets"
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    headers = {"X-BX-APIKEY": API_KEY}
    params = {"timestamp": timestamp, "signature": signature}

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

# Handler de /start
@router.message(F.text == "/start")
async def start_handler(message: Message):
    await message.answer("👋 ¡Bienvenido a ZafroBot Notifier 2!\n\nEnvía /saldo para consultar tu saldo actualizado.")

# Handler de /saldo
@router.message(F.text == "/saldo")
async def saldo_handler(message: Message):
    saldo = await obtener_saldo_usdt()
    texto = formatear_tarjeta(saldo)
    await message.answer(texto)

# Iniciar polling
async def main():
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())