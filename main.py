import logging
import hmac
import hashlib
import time
import os
import json

from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Configurar el bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# App Flask
app = Flask(__name__)

# Formateo de saldo bonito
def formatear_tarjeta(saldo):
    return (
        "╭─────────────────────╮\n"
        "📋 Saldo en Spot\n"
        "╰─────────────────────╯\n"
        "╭─────────────────────╮\n"
        f"💵 Moneda: USDT\n"
        f"📈 Disponible: {saldo:.2f}\n"
        "╰─────────────────────╯\n"
        "🕒 Consulta en tiempo real\n"
    )

# Función para obtener saldo
async def obtener_saldo_usdt():
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()

    headers = {
        "X-BX-APIKEY": API_KEY,
    }

    url = f"https://open-api.bingx.com/openApi/spot/v1/account/assets?{query_string}&signature={signature}"

    async with bot.session.get(url, headers=headers) as response:
        data = await response.json()

        if data["code"] == 0:
            assets = data["data"]["assets"]
            for asset in assets:
                if asset["asset"] == "USDT":
                    return float(asset["free"])
        return 0.0

# Manejador de comandos
@dp.message(commands=["start"])
async def start_handler(message: types.Message):
    await message.answer("👋 ¡Bienvenido a ZafroBot!\n\nEnvía el comando /saldo para ver tu saldo disponible.")

@dp.message(commands=["saldo"])
async def saldo_handler(message: types.Message):
    saldo = await obtener_saldo_usdt()
    texto = formatear_tarjeta(saldo)
    await message.answer(texto)

# Ruta Flask para recibir actualizaciones de Telegram
@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
async def webhook():
    update = types.Update(**request.json)
    await dp.feed_update(bot, update)
    return "OK"

# Ruta principal
@app.route("/", methods=["GET"])
def home():
    return "ZafroBot corriendo correctamente."

# Inicio de Webhook
async def on_startup():
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)

if __name__ == "__main__":
    import asyncio

    async def main():
        await on_startup()
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

    asyncio.run(main())