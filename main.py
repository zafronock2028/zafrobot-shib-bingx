import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, Update
from aiogram.enums import ParseMode
from aiohttp import web
import aiohttp
import asyncio
import os
import hmac
import hashlib
import time
import json

# API y claves
API_KEY = "LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA"
SECRET_KEY = "Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg"
TELEGRAM_BOT_TOKEN = "7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM"
WEBHOOK_URL = "https://zafrobot-shib-bingx.onrender.com/webhook"

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Formatear saldo bonito
def formatear_tarjeta(saldo):
    return (
        "┌───────────────────────────────┐\n"
        "│     📋 Saldo en Spot           │\n"
        "├───────────────────────────────┤\n"
        f"│ 💵 Moneda: USDT                │\n"
        f"│ 📈 Disponible: {saldo:.2f}            │\n"
        "├───────────────────────────────┤\n"
        "│ 🕒 Consulta en tiempo real     │\n"
        "└───────────────────────────────┘"
    )

# Consulta de saldo
async def obtener_saldo_usdt():
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    url = f"https://open-api.bingx.com/openApi/spot/v1/account/balance?{query_string}&signature={signature}"

    headers = {
        "X-BX-APIKEY": API_KEY,
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                balances = data.get("data", {}).get("balances", [])
                for balance in balances:
                    if balance.get("asset") == "USDT":
                        return float(balance.get("balance", 0))
            return 0

# Handlers
@dp.message(F.text == "/start")
async def start(message: Message):
    bienvenida = (
        "👋 *¡Bienvenido a ZafroBot!*\n\n"
        "Este bot te ayuda a consultar tu saldo disponible de *USDT* en tu cuenta Spot de *BingX* en tiempo real.\n\n"
        "Envía el comando /saldo para ver tu saldo actualizado."
    )
    await message.answer(bienvenida, parse_mode=ParseMode.MARKDOWN)

@dp.message(F.text == "/saldo")
async def saldo(message: Message):
    saldo_actual = await obtener_saldo_usdt()
    respuesta = formatear_tarjeta(saldo_actual)
    await message.answer(respuesta)

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()

# Webhook
async def handle_webhook(request):
    body = await request.read()
    update = Update.model_validate_json(body)
    await dp.feed_update(bot, update)
    return web.Response()

# Configurar server
app = web.Application()
app.router.add_post("/webhook", handle_webhook)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))