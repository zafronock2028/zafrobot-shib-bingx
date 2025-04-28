import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Client

load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

client = Client(API_KEY, SECRET_KEY, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

bot_encendido = False
user_chat_id = None

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    global user_chat_id, bot_encendido
    user_chat_id = message.chat.id
    bot_encendido = False
    await message.answer(
        "✅ ZafroBot Scalper PRO V1 iniciado.\n\nSelecciona una opción:",
        reply_markup=keyboard
    )

def leer_saldo_usdt() -> float:
    cuentas = client.get_accounts()
    for cuenta in cuentas:
        if cuenta.get("currency") == "USDT" and cuenta.get("type") == "trade":
            return float(cuenta.get("available", 0))
    return 0.0

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def encender_bot(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await message.answer("🟢 Bot encendido. Iniciando escaneo de mercado…")
        asyncio.create_task(tarea_principal())
    else:
        await message.answer("⚠️ El bot ya está encendido.")

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def apagar_bot(message: types.Message):
    global bot_encendido
    bot_encendido = False
    await message.answer("🔴 Bot apagado. Operaciones detenidas.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def estado_bot(message: types.Message):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"📊 Estado actual del bot: {estado}")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = leer_saldo_usdt()
    await message.answer(f"💰 Saldo disponible: {saldo:.2f} USDT")

async def tarea_principal():
    global bot_encendido, user_chat_id
    while bot_encendido:
        saldo = leer_saldo_usdt()
        if saldo < 5:
            await bot.send_message(user_chat_id, f"⚠️ Saldo insuficiente: {saldo:.2f} USDT. Esperando…")
        else:
            await bot.send_message(user_chat_id, f"🔎 Escaneando mercado con {saldo:.2f} USDT disponibles…")
        await asyncio.sleep(30)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
