import logging
import asyncio
import os
from kucoin.client import AsyncClient
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

# Configurar el registro de logs
logging.basicConfig(level=logging.INFO)

# Cargar variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Inicializar el bot y el dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Función para obtener saldo de USDT
async def obtener_saldo_usdt():
    client = await AsyncClient.create(API_KEY, SECRET_KEY)
    accounts = await client.get_accounts()
    saldo_usdt = 0.0
    for account in accounts:
        if account['currency'] == 'USDT' and account['type'] == 'trade':
            saldo_usdt = float(account['available'])
            break
    await client.close()
    return saldo_usdt

# Función para encender el bot
async def encender_bot(message: Message):
    await message.answer("🚀 Bot encendido. Escaneando mercado y preparando operaciones.")
    saldo = await obtener_saldo_usdt()
    if saldo > 0:
        await message.answer(f"✅ Saldo disponible para operar: {saldo} USDT")
    else:
        await message.answer("⚠️ Saldo insuficiente para operar. Saldo actual: 0.0 USDT")

# Función para apagar el bot
async def apagar_bot(message: Message):
    await message.answer("⛔ Bot apagado. Operaciones detenidas.")

# Función para mostrar el estado del bot
async def estado_bot(message: Message):
    saldo = await obtener_saldo_usdt()
    await message.answer(f"📊 Estado del bot:\nSaldo disponible: {saldo} USDT")

# Función para actualizar saldo
async def actualizar_saldo(message: Message):
    saldo = await obtener_saldo_usdt()
    await message.answer(f"💰 Saldo actualizado: {saldo} USDT")

# Configurar comandos de Telegram
@dp.message(Command("start"))
async def start_handler(message: Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🚀 Encender Bot"),
        types.KeyboardButton("⛔ Apagar Bot"),
    )
    markup.add(
        types.KeyboardButton("📊 Estado del Bot"),
        types.KeyboardButton("💰 Actualizar Saldo"),
    )
    await message.answer(
        "✅ *ZafroBot Scalper PRO* ha iniciado correctamente.\n\nSelecciona una opción:",
        parse_mode="Markdown",
        reply_markup=markup,
    )

@dp.message()
async def handle_message(message: Message):
    if message.text == "🚀 Encender Bot":
        await encender_bot(message)
    elif message.text == "⛔ Apagar Bot":
        await apagar_bot(message)
    elif message.text == "📊 Estado del Bot":
        await estado_bot(message)
    elif message.text == "💰 Actualizar Saldo":
        await actualizar_saldo(message)
    else:
        await message.answer("Comando no reconocido. Usa el menú.")

# Función principal
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())