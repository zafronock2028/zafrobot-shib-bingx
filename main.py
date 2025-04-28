import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Client

# Cargar variables de entorno
load_dotenv()
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
try:
    CHAT_ID = int(CHAT_ID)
except:
    pass

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Inicializar cliente de KuCoin (Spot) y bot de Telegram
client = Client(API_KEY, SECRET_KEY, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Estado global del bot y tarea de escaneo
bot_running = False
scan_task = None

# Teclado de opciones para Telegram
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")]
    ],
    resize_keyboard=True
)

# Handler para /start
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    global bot_running
    bot_running = False
    await message.answer(
        "✅ ZafroBot Scalper PRO V1 iniciado.\nSelecciona una opción:",
        reply_markup=keyboard
    )

# Función para obtener saldo USDT en Spot (suma disponible de todas las cuentas)
def get_usdt_balance() -> float:
    try:
        accounts = client.get_accounts()
        total = 0.0
        for acc in accounts:
            if acc.get("currency") == "USDT":
                total += float(acc.get("available", 0))
        return total
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return 0.0

# Tarea de escaneo de mercado
async def market_scan(chat_id: int):
    global bot_running
    while bot_running:
        balance = get_usdt_balance()
        if balance < 5:
            await bot.send_message(chat_id, f"⚠️ Saldo insuficiente: {balance:.2f} USDT. Esperando…")
        else:
            await bot.send_message(chat_id, f"🔎 Escaneando mercado con {balance:.2f} USDT disponibles…")
        await asyncio.sleep(30)

# Handler para encender el bot
@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def turn_on(message: types.Message):
    global bot_running, scan_task
    if not bot_running:
        bot_running = True
        await message.answer("🟢 Bot encendido. Iniciando escaneo de mercado…")
        scan_task = asyncio.create_task(market_scan(message.chat.id))
    else:
        await message.answer("⚠️ El bot ya está encendido.")

# Handler para apagar el bot
@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def turn_off(message: types.Message):
    global bot_running, scan_task
    if bot_running:
        bot_running = False
        if scan_task:
            scan_task.cancel()
            scan_task = None
        await message.answer("🔴 Bot apagado. Operaciones detenidas.")
    else:
        await message.answer("⚠️ El bot ya está apagado.")

# Handler para mostrar estado del bot
@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def status(message: types.Message):
    state = "🟢 Encendido" if bot_running else "🔴 Apagado"
    await message.answer(f"📊 Estado actual del bot: {state}")

# Handler para actualizar saldo
@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def update_balance(message: types.Message):
    balance = get_usdt_balance()
    await message.answer(f"💰 Saldo disponible: {balance:.2f} USDT")

# Función principal\ async def main():
    # Eliminar webhook previo para evitar conflictos
    await bot.delete_webhook(drop_pending_updates=True)
    # Iniciar polling del bot
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
