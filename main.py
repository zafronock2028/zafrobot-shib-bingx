import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Inicializar KuCoin
api_key = os.getenv('API_KEY')
api_secret = os.getenv('SECRET_KEY')
api_passphrase = os.getenv('API_PASSPHRASE')

client = Client(api_key, api_secret, api_passphrase)

# Inicializar Bot
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
bot = Bot(token=bot_token, parse_mode=ParseMode.HTML)
dp = Dispatcher()

chat_id = os.getenv('CHAT_ID')

# Función para obtener saldo
def obtener_saldo_usdt():
    try:
        cuentas = client.get_account_list()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                return float(cuenta['available'])
    except Exception as e:
        print(f"Error obteniendo saldo: {e}")
    return 0.0

# Comandos
@dp.message(Command("start"))
async def cmd_start(message: Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")]
    ])
    await message.answer("✅ <b>ZafroBot Scalper PRO</b> ha iniciado correctamente.\n\nSelecciona una opción:", reply_markup=markup)

@dp.message(lambda message: message.text == "🚀 Encender Bot")
async def encender_bot(message: Message):
    await message.answer("🚀 Bot encendido. Escaneando mercado y preparando operaciones.")
    saldo = obtener_saldo_usdt()
    if saldo > 0:
        await message.answer(f"💰 Saldo disponible en KuCoin Trading: <b>{saldo:.2f} USDT</b>")
    else:
        await message.answer("⚠️ Saldo insuficiente para operar. Saldo actual: 0.0 USDT")

@dp.message(lambda message: message.text == "🛑 Apagar Bot")
async def apagar_bot(message: Message):
    await message.answer("🛑 Bot apagado correctamente.")

@dp.message(lambda message: message.text == "📊 Estado del Bot")
async def estado_bot(message: Message):
    await message.answer("📈 Estado actual del bot: 🟢 Encendido")

@dp.message(lambda message: message.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: Message):
    saldo = obtener_saldo_usdt()
    if saldo > 0:
        await message.answer(f"💰 Saldo actualizado en KuCoin Trading: <b>{saldo:.2f} USDT</b>")
    else:
        await message.answer("⚠️ Saldo insuficiente para operar. Saldo actual: 0.0 USDT")

# Configuración de logs
logging.basicConfig(level=logging.INFO)

# Iniciar bot
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())