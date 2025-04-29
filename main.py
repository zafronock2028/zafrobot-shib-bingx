import os
import asyncio
import logging
import random
from kucoin.client import Client as KucoinClient
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

# Configuración
load_dotenv()
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

# Inicializar
kucoin_client = KucoinClient(API_KEY, SECRET_KEY, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)
pares = ["SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT"]
bot_encendido = False

# Teclado Telegram
keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(KeyboardButton('🚀 Encender Bot'))
keyboard.add(KeyboardButton('🛑 Apagar Bot'))
keyboard.add(KeyboardButton('📊 Estado del Bot'))
keyboard.add(KeyboardButton('📋 Estado de Orden'))
keyboard.add(KeyboardButton('💰 Actualizar Saldo'))

# Funciones
async def obtener_saldo():
    cuentas = kucoin_client.get_accounts()
    for cuenta in cuentas:
        if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
            return float(cuenta['available'])
    return 0.0

async def escanear_mercado():
    global bot_encendido
    while bot_encendido:
        try:
            for par in pares:
                ticker = kucoin_client.get_ticker(par)
                precio = float(ticker['price'])
                volumen = float(ticker['volValue'])
                if volumen > 10000:
                    await bot.send_message(CHAT_ID, f"Análisis: {par} | Precio: {precio} | Volumen 24h: {volumen:.2f} USD")
        except Exception as e:
            logging.error(f"Error escaneando mercado: {e}")
        await asyncio.sleep(2)

# Comandos
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("✅ Bienvenido a ZafroBot Dinámico Pro", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "🚀 Encender Bot")
async def encender(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await message.answer("🟢 Bot encendido y analizando mercado...")
        asyncio.create_task(escanear_mercado())
    else:
        await message.answer("⚠️ El bot ya está encendido.")

@dp.message_handler(lambda message: message.text == "🛑 Apagar Bot")
async def apagar(message: types.Message):
    global bot_encendido
    bot_encendido = False
    await message.answer("🔴 Bot apagado.")

@dp.message_handler(lambda message: message.text == "📊 Estado del Bot")
async def estado(message: types.Message):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"Estado actual: {estado}")

@dp.message_handler(lambda message: message.text == "📋 Estado de Orden")
async def estado_orden(message: types.Message):
    await message.answer("📋 Todavía no hay operaciones abiertas.")

@dp.message_handler(lambda message: message.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = await obtener_saldo()
    await message.answer(f"💰 Saldo disponible: {saldo:.2f} USDT")

# Lanzar bot
async def main():
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
