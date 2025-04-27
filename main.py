import os
import asyncio
import aiohttp
import hmac
import hashlib
import base64
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Variables de entorno
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('SECRET_KEY')
API_PASSPHRASE = os.getenv('PHRASE')  # Clave de la trading password
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = int(os.getenv('CHAT_ID'))

# Inicializar bot y dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Estado global del bot
bot_activo = False

# Crear teclado de control
keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Encender Bot", callback_data="encender")],
    [InlineKeyboardButton(text="⛔ Apagar Bot", callback_data="apagar")],
    [InlineKeyboardButton(text="ℹ️ Ver Estado", callback_data="estado")],
    [InlineKeyboardButton(text="🔄 Actualizar Saldo", callback_data="saldo")]
])

# Función para firmar solicitudes KuCoin
def sign_request(endpoint, method='GET', body=''):
    now = int(time.time() * 1000)
    str_to_sign = str(now) + method + endpoint + body
    signature = base64.b64encode(hmac.new(API_SECRET.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest())
    passphrase = base64.b64encode(hmac.new(API_SECRET.encode('utf-8'), API_PASSPHRASE.encode('utf-8'), hashlib.sha256).digest())
    headers = {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature.decode(),
        "KC-API-TIMESTAMP": str(now),
        "KC-API-PASSPHRASE": passphrase.decode(),
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }
    return headers

# Comando de inicio
@dp.message(Command(commands=["start"]))
async def start_command(message: types.Message):
    if message.chat.id != CHAT_ID:
        return
    await message.answer(
        "🚀 ¡Bienvenido a ZafroBot Scalper PRO v1!\n\n"
        "Usa los botones para controlar el bot:\n\n"
        "✅ Encender Bot\n"
        "⛔ Apagar Bot\n"
        "ℹ️ Ver Estado\n"
        "🔄 Actualizar Saldo\n\n"
        "🔥 ¡Vamos por todo, Zafronock!",
        reply_markup=keyboard
    )

# Función para consultar saldo disponible en Trading Wallet
async def consultar_saldo():
    url = "https://api.kucoin.com/api/v1/accounts?type=trade"
    headers = sign_request("/api/v1/accounts?type=trade")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            usdt_balance = next((item for item in data['data'] if item['currency'] == 'USDT'), None)
            if usdt_balance:
                return float(usdt_balance['available'])
            return 0.0

# Función para mandar el estado actual
async def estado_actual(message: types.Message):
    saldo = await consultar_saldo()
    await message.answer(f"💰 Saldo disponible en Wallet de Trading: {saldo:.2f} USDT")

# Botón de acciones
@dp.callback_query()
async def botones_control(callback: types.CallbackQuery):
    global bot_activo

    if callback.message.chat.id != CHAT_ID:
        return

    if callback.data == "encender":
        bot_activo = True
        await callback.message.answer("✅ ZafroBot Scalper PRO está ahora ACTIVADO.")
    elif callback.data == "apagar":
        bot_activo = False
        await callback.message.answer("⛔ ZafroBot Scalper PRO ha sido APAGADO.")
    elif callback.data == "estado":
        await estado_actual(callback.message)
    elif callback.data == "saldo":
        saldo = await consultar_saldo()
        await callback.message.answer(f"🔄 Saldo actualizado: {saldo:.2f} USDT")

    await callback.answer()

# Ciclo de análisis continuo
async def ciclo_bot():
    global bot_activo
    while True:
        if bot_activo:
            # Aquí va el análisis real que estamos por integrar (scalping, volumen, impulso, etc.)
            await asyncio.sleep(10)  # Simulación de análisis de mercado cada 10s
        else:
            await asyncio.sleep(5)

# Lanzar bot
async def main():
    asyncio.create_task(ciclo_bot())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())