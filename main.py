import logging
from aiogram import Bot, Dispatcher, executor, types
import aiohttp
import asyncio
import os
import hmac
import hashlib
import time
import json

# Variables de entorno (ya integradas con tus valores)
API_KEY = "LCRNrSVWUf1crSsLEEtrdDzylUWdNVteIJTnypigJV9HQ1AfMYhklxiNazKDNcrGq3vgQjuKspQTjFHeA"
SECRET_KEY = "KchOB6FYbU6pKmJcCt7ujQ0TdxrDL5i9"
TELEGRAM_BOT_TOKEN = "7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM"

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

# Formateo de saldo
def formatear_tarjeta(saldo):
    return (
        "╭───────────────────────╮\n"
        "│ 📋 Saldo en Spot        │\n"
        "├───────────────────────┤\n"
        "│ 💵 Moneda: USDT         │\n"
        f"│ 📈 Disponible: {saldo:.2f}     │\n"
        "├───────────────────────┤\n"
        "│ 🕒 Consulta en tiempo real │\n"
        "╰───────────────────────╯"
    )

# Función para obtener saldo
async def obtener_saldo_usdt():
    timestamp = str(int(time.time()) * 1000)
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()

    headers = {
        "X-BX-APIKEY": API_KEY
    }

    url = f"https://open-api.bingx.com/openApi/spot/v1/account/balance?{query_string}&signature={signature}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json()
            if data["code"] == 0:
                balances = data["data"]["balances"]
                for balance in balances:
                    if balance["asset"] == "USDT":
                        return float(balance["balance"])
            return None

# Comando /start
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("👋 ¡Bienvenido a ZafroBot!\n\nEste bot te ayuda a consultar tu saldo disponible de **USDT** en tu cuenta Spot de **BingX** en tiempo real.\n\nEnvía el comando /saldo para ver tu saldo actualizado.")

# Comando /saldo
@dp.message_handler(commands=["saldo"])
async def saldo(message: types.Message):
    saldo_usdt = await obtener_saldo_usdt()
    if saldo_usdt is not None:
        tarjeta = formatear_tarjeta(saldo_usdt)
        await message.answer(tarjeta)
    else:
        await message.answer("❌ No se pudo obtener el saldo de USDT.\nIntenta más tarde.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)