import logging
import asyncio
import os
import hmac
import hashlib
import time
import json

from aiohttp import ClientSession
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.filters import Command

# Cargar variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Crear Bot y Dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Formateo de saldo
def formatear_tarjeta(saldo):
    return (
        "╭───────┈✦ Saldo en Spot ✦┈───────╮\n"
        "╰➤ 💵 Moneda: USDT\n"
        f"╰➤ 📈 Disponible: {saldo:.2f}\n"
        "╰➤ 🕒 Consulta en tiempo real\n"
    )

# Función para obtener saldo USDT
async def obtener_saldo_usdt():
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()

    headers = {
        "X-BX-APIKEY": API_KEY
    }

    url = f"https://open-api.bingx.com/openApi/user/spot/assets?{query_string}&signature={signature}"

    async with ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json()

    usdt_balance = 0.0
    if data.get("code") == 0:
        for asset in data["data"]["assets"]:
            if asset["asset"] == "USDT":
                usdt_balance = float(asset["free"])
                break
    return usdt_balance

# Comando /start
@dp.message(Command("start"))
async def start_command(message: Message):
    await message.answer(
        "👋 ¡Bienvenido a ZafroBot!\n\n"
        "Este bot te ayuda a consultar tu saldo disponible de <b>USDT</b> en tu cuenta Spot de BingX en tiempo real.\n\n"
        "Envía el comando /saldo para ver tu saldo actualizado."
    )

# Comando /saldo
@dp.message(Command("saldo"))
async def saldo_command(message: Message):
    saldo = await obtener_saldo_usdt()
    respuesta = formatear_tarjeta(saldo)
    await message.answer(respuesta)

# Iniciar el bot
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())