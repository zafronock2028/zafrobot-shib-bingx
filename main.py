import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand
from kucoin.client import Client
import os

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

client = Client(API_KEY, API_SECRET, API_PASSPHRASE)

bot_running = False

async def set_commands():
    commands = [
        BotCommand(command="start", description="Iniciar el bot"),
    ]
    await bot.set_my_commands(commands)

@dp.message(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("✅ ZafroBot Scalper PRO ha iniciado correctamente.\n\nSelecciona una opción:", reply_markup=main_keyboard())

@dp.message(lambda message: message.text == "🚀 Encender Bot")
async def start_bot(message: types.Message):
    global bot_running
    bot_running = True
    await message.answer("🚀 Bot encendido. Escaneando mercado y preparando operaciones.")
    asyncio.create_task(run_bot())

@dp.message(lambda message: message.text == "🛑 Apagar Bot")
async def stop_bot(message: types.Message):
    global bot_running
    bot_running = False
    await message.answer("🛑 Bot apagado. No se están ejecutando operaciones.")

@dp.message(lambda message: message.text == "📊 Estado del Bot")
async def bot_status(message: types.Message):
    status = "activo" if bot_running else "inactivo"
    await message.answer(f"📈 Estado actual del bot: {status.upper()}")

@dp.message(lambda message: message.text == "💰 Actualizar Saldo")
async def update_balance(message: types.Message):
    try:
        accounts = client.get_accounts()
        usdt_balance = next((float(acc['available']) for acc in accounts if acc['currency'] == 'USDT' and acc['type'] == 'trade'), 0.0)
        await message.answer(f"💵 Saldo disponible: {usdt_balance} USDT")
    except Exception as e:
        await message.answer(f"⚠️ Error al obtener saldo: {e}")

def main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("🚀 Encender Bot", "🛑 Apagar Bot")
    keyboard.add("📊 Estado del Bot", "💰 Actualizar Saldo")
    return keyboard

async def run_bot():
    global bot_running
    while bot_running:
        await asyncio.sleep(10)  # Aquí en el futuro irá el análisis de mercado y trading automático

async def main():
    await set_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())