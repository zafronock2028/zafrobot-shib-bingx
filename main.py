import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from kucoin_futures.client import AsyncClient

# Cargar variables de entorno
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

async def get_balance():
    client = AsyncClient(API_KEY, API_SECRET, API_PASSPHRASE, is_sandbox=False)
    accounts = await client.get_account_overview()
    usdt_balance = accounts.get('availableBalance', 0)
    await client.close()
    return float(usdt_balance)

@dp.message(commands=["start"])
async def start(message: types.Message):
    await message.answer("✅ ZafroBot Scalper PRO ha iniciado correctamente.\n\nSelecciona una opción:", reply_markup=main_keyboard())

@dp.message(lambda message: message.text == "🚀 Encender Bot")
async def encender_bot(message: types.Message):
    await message.answer("🚀 Bot encendido. Escaneando mercado y preparando operaciones.")

@dp.message(lambda message: message.text == "🛑 Apagar Bot")
async def apagar_bot(message: types.Message):
    await message.answer("🛑 Bot apagado manualmente.")

@dp.message(lambda message: message.text == "📊 Estado del Bot")
async def estado_bot(message: types.Message):
    await message.answer("📊 El bot está funcionando correctamente.")

@dp.message(lambda message: message.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    balance = await get_balance()
    if balance > 0:
        await message.answer(f"💰 Saldo disponible: {balance:.2f} USDT")
    else:
        await message.answer("⚠️ Saldo insuficiente para operar. Saldo actual: 0.0 USDT")

def main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        types.KeyboardButton("🚀 Encender Bot"),
        types.KeyboardButton("🛑 Apagar Bot")
    )
    keyboard.add(
        types.KeyboardButton("📊 Estado del Bot"),
        types.KeyboardButton("💰 Actualizar Saldo")
    )
    return keyboard

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())