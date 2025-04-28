import logging
import os
import asyncio
import aiohttp
import hmac
import hashlib
import base64
import time
from aiogram import Bot, Dispatcher, types, executor

# ----------------------------------------
# CONFIGURACIÓN INICIAL
# ----------------------------------------

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('SECRET_KEY')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

bot_activo = False

# ----------------------------------------
# FUNCIONES PARA KUCOIN
# ----------------------------------------

async def sign_request(method, endpoint, body=""):
    now = int(time.time() * 1000)
    str_to_sign = f"{now}{method}{endpoint}{body}"
    signature = base64.b64encode(hmac.new(API_SECRET.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest()).decode()
    passphrase = base64.b64encode(hmac.new(API_SECRET.encode('utf-8'), API_PASSPHRASE.encode('utf-8'), hashlib.sha256).digest()).decode()
    headers = {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": str(now),
        "KC-API-PASSPHRASE": passphrase,
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }
    return headers

async def consultar_saldo():
    url = "https://api.kucoin.com/api/v1/accounts?type=trade"
    headers = await sign_request("GET", "/api/v1/accounts?type=trade")

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                for account in data.get('data', []):
                    if account['currency'] == 'USDT':
                        return float(account['available'])
                return 0.0
            else:
                return 0.0

# ----------------------------------------
# FUNCIONES DEL BOT
# ----------------------------------------

async def estrategia_scalping():
    while bot_activo:
        saldo = await consultar_saldo()
        if saldo > 0:
            await bot.send_message(chat_id=os.getenv('CHAT_ID'), text=f"✅ Analizando mercado con saldo disponible: {saldo} USDT")
            # Aquí iría la estrategia de trading profesional que programamos
            await asyncio.sleep(15)  # cada 15 segundos analiza
        else:
            await bot.send_message(chat_id=os.getenv('CHAT_ID'), text="⚠️ No hay saldo disponible para operar.")
            await asyncio.sleep(30)  # si no hay saldo, espera más

# ----------------------------------------
# COMANDOS DEL TELEGRAM
# ----------------------------------------

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ["✅ Encender Bot", "⛔ Apagar Bot", "ℹ️ Ver Estado", "🔄 Actualizar Saldo"]
    keyboard.add(*buttons)
    await message.answer(
        "✅ ZafroBot Scalper PRO ha iniciado correctamente. ¡Listo para recibir comandos!\n\nSelecciona una opción:",
        reply_markup=keyboard
    )

@dp.message_handler(lambda message: message.text == "✅ Encender Bot")
async def encender_bot(message: types.Message):
    global bot_activo
    if not bot_activo:
        bot_activo = True
        await message.answer("✅ Bot ACTIVADO. Escaneando saldo y mercado...")
        asyncio.create_task(estrategia_scalping())
    else:
        await message.answer("✅ El bot ya está activo.")

@dp.message_handler(lambda message: message.text == "⛔ Apagar Bot")
async def apagar_bot(message: types.Message):
    global bot_activo
    bot_activo = False
    await message.answer("⛔ Bot APAGADO.")

@dp.message_handler(lambda message: message.text == "ℹ️ Ver Estado")
async def ver_estado(message: types.Message):
    estado = "✅ Activo" if bot_activo else "⛔ Apagado"
    await message.answer(f"ℹ️ Estado actual del bot: {estado}")

@dp.message_handler(lambda message: message.text == "🔄 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = await consultar_saldo()
    await message.answer(f"💰 Tu saldo actual disponible en KuCoin (Trading Wallet) es: {saldo} USDT")

# ----------------------------------------
# INICIAR EL BOT
# ----------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)