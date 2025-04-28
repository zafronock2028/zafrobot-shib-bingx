import asyncio
import hmac
import base64
import hashlib
import time
import json
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
import logging
import os

# Configuración de variables de entorno
API_KEY = os.getenv("API_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Inicializar bot y dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Variable para controlar el estado del bot
bot_activo = False

# Función para firmar las solicitudes a KuCoin
def sign_request(endpoint, method="GET", body=""):
    now = int(time.time() * 1000)
    str_to_sign = f"{now}{method}{endpoint}{body}"
    signature = base64.b64encode(
        hmac.new(SECRET_KEY.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest()
    )
    passphrase = base64.b64encode(
        hmac.new(SECRET_KEY.encode('utf-8'), API_PASSPHRASE.encode('utf-8'), hashlib.sha256).digest()
    )
    headers = {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature.decode(),
        "KC-API-TIMESTAMP": str(now),
        "KC-API-PASSPHRASE": passphrase.decode(),
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }
    return headers

# Función para consultar el saldo de USDT
async def consultar_saldo():
    endpoint = "/api/v1/accounts?type=trade"
    url = f"https://api.kucoin.com{endpoint}"
    headers = sign_request(endpoint)
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        for asset in data.get('data', []):
            if asset['currency'] == 'USDT':
                return float(asset['available'])
        return 0.0
    except Exception as e:
        print(f"Error consultando saldo: {e}")
        return 0.0

# Función que simula la búsqueda de oportunidad de trading
async def buscar_oportunidades():
    while bot_activo:
        saldo = await consultar_saldo()
        if saldo >= 10:  # Monto mínimo para operar (puedes ajustar)
            await bot.send_message(CHAT_ID, f"✅ Detectado saldo disponible: {saldo} USDT\nBuscando oportunidades de scalping...")
            # Aquí iría tu lógica de análisis de mercado real.
        else:
            await bot.send_message(CHAT_ID, f"⚠️ Saldo insuficiente para operar. Saldo actual: {saldo} USDT")
        await asyncio.sleep(60)  # Espera 1 minuto entre chequeos

# Menú principal con botones
def menu_principal():
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Encender Bot", callback_data="encender")],
        [InlineKeyboardButton(text="🛑 Apagar Bot", callback_data="apagar")],
        [InlineKeyboardButton(text="📊 Estado del Bot", callback_data="estado")],
        [InlineKeyboardButton(text="💰 Actualizar Saldo", callback_data="saldo")]
    ])
    return markup

# Comando /start
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        "✅ ZafroBot Scalper PRO ha iniciado correctamente.\n\nSelecciona una opción:",
        reply_markup=menu_principal()
    )

# Callback query handler
@dp.callback_query()
async def callback_query_handler(callback_query: types.CallbackQuery):
    global bot_activo
    action = callback_query.data

    if action == "encender":
        bot_activo = True
        await callback_query.message.answer("🚀 Bot encendido. Escaneando mercado y preparando operaciones.")
        asyncio.create_task(buscar_oportunidades())
    elif action == "apagar":
        bot_activo = False
        await callback_query.message.answer("🛑 Bot apagado correctamente.")
    elif action == "estado":
        estado = "🟢 Encendido" if bot_activo else "🔴 Apagado"
        await callback_query.message.answer(f"📊 Estado actual del bot: {estado}")
    elif action == "saldo":
        saldo = await consultar_saldo()
        await callback_query.message.answer(f"💰 Saldo disponible en KuCoin Trading: {saldo:.2f} USDT")

# Main
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())