import os
import asyncio
import logging
import json
import hmac
import hashlib
import base64
import time
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('SECRET_KEY')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

bot_activo = False

# Mensaje de inicio
@dp.message(CommandStart())
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Encender Bot", callback_data="encender")],
        [InlineKeyboardButton(text="🛑 Apagar Bot", callback_data="apagar")],
        [InlineKeyboardButton(text="📊 Estado del Bot", callback_data="estado")],
        [InlineKeyboardButton(text="💰 Actualizar Saldo", callback_data="saldo")]
    ])
    await message.answer("✅ ZafroBot Scalper PRO ha iniciado correctamente.\n\nSelecciona una opción:", reply_markup=keyboard)

# Firmar solicitudes
def sign_request(endpoint, method="GET", body=""):
    now = str(int(time.time() * 1000))
    str_to_sign = now + method + endpoint + body
    signature = base64.b64encode(
        hmac.new(API_SECRET.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest()
    )
    headers = {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature.decode(),
        "KC-API-TIMESTAMP": now,
        "KC-API-PASSPHRASE": API_PASSPHRASE,
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }
    return headers

# Consultar saldo
async def consultar_saldo():
    url = "https://api.kucoin.com/api/v1/accounts?type=trade"
    headers = sign_request("/api/v1/accounts?type=trade")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            usdt_balance = 0
            for asset in data.get('data', []):
                if asset['currency'] == 'USDT':
                    usdt_balance = float(asset['available'])
            return usdt_balance

# Escanear mercado (ejemplo)
async def escanear_mercado():
    # Aquí iría tu lógica de scalping de 2% a 6% de ganancia
    while bot_activo:
        saldo = await consultar_saldo()
        if saldo >= 10:
            await bot.send_message(CHAT_ID, f"✅ Escaneando mercado con saldo disponible: ${saldo:.2f}")
            # Aquí se pondría la lógica real de trading
        else:
            await bot.send_message(CHAT_ID, "⚠️ Saldo insuficiente para operar.")
        await asyncio.sleep(15)  # esperar 15 segundos entre escaneos

# Callbacks de botones
@dp.callback_query()
async def callbacks(call: types.CallbackQuery):
    global bot_activo

    if call.data == "encender":
        if not bot_activo:
            bot_activo = True
            await call.message.answer("🚀 Bot encendido. Escaneando mercado y preparando operaciones.")
            asyncio.create_task(escanear_mercado())
        else:
            await call.message.answer("✅ El bot ya está activo.")

    elif call.data == "apagar":
        if bot_activo:
            bot_activo = False
            await call.message.answer("🛑 Bot apagado.")
        else:
            await call.message.answer("✅ El bot ya estaba apagado.")

    elif call.data == "estado":
        estado = "✅ Activo" if bot_activo else "🛑 Apagado"
        await call.message.answer(f"📊 Estado actual del bot: {estado}")

    elif call.data == "saldo":
        saldo = await consultar_saldo()
        await call.message.answer(f"💰 Saldo disponible para trading: ${saldo:.2f}")

# Ejecutar bot
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())