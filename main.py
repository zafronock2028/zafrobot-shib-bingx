import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Client

# ————————————————
# Cargar configuración
# ————————————————
load_dotenv()
API_KEY            = os.getenv("API_KEY")
SECRET_KEY         = os.getenv("SECRET_KEY")
API_PASSPHRASE     = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Asegúrate de que CHAT_ID sea un entero
try:
    CHAT_ID = int(os.getenv("CHAT_ID", "0"))
except ValueError:
    CHAT_ID = 0

# ————————————————
# Logging
# ————————————————
logging.basicConfig(level=logging.INFO)

# ————————————————
# Inicializaciones
# ————————————————
# KuCoin Spot client
client = Client(API_KEY, SECRET_KEY, API_PASSPHRASE)
# Telegram bot y dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp  = Dispatcher()

# Estado global
bot_running = False
scan_task   = None

# Teclado de comandos
menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")]
    ],
    resize_keyboard=True
)

# ————————————————
# Handlers
# ————————————————
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    global bot_running
    bot_running = False
    await message.answer(
        "✅ *ZafroBot Scalper PRO V1* iniciado.\nSelecciona una opción:",
        parse_mode="Markdown",
        reply_markup=menu
    )

def get_usdt_balance() -> float:
    """Suma el disponible de USDT en todas tus cuentas Spot."""
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

async def market_scan(chat_id: int):
    """Tarea de escaneo que envía un mensaje cada 30s."""
    global bot_running
    while bot_running:
        balance = get_usdt_balance()
        if balance < 5:
            await bot.send_message(chat_id, f"⚠️ Saldo insuficiente: {balance:.2f} USDT. Esperando…")
        else:
            await bot.send_message(chat_id, f"🔎 Escaneando mercado con {balance:.2f} USDT disponibles…")
        await asyncio.sleep(30)

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def cmd_turn_on(message: types.Message):
    global bot_running, scan_task
    if not bot_running:
        bot_running = True
        await message.answer("🟢 Bot encendido. Iniciando escaneo de mercado…")
        scan_task = asyncio.create_task(market_scan(message.chat.id))
    else:
        await message.answer("⚠️ El bot ya está encendido.")

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def cmd_turn_off(message: types.Message):
    global bot_running, scan_task
    if bot_running:
        bot_running = False
        if scan_task:
            scan_task.cancel()
            scan_task = None
        await message.answer("🔴 Bot apagado. Operaciones detenidas.")
    else:
        await message.answer("⚠️ El bot ya está apagado.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def cmd_status(message: types.Message):
    state = "🟢 Encendido" if bot_running else "🔴 Apagado"
    await message.answer(f"📊 Estado actual del bot: {state}")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def cmd_update_balance(message: types.Message):
    balance = get_usdt_balance()
    await message.answer(f"💰 Saldo disponible: {balance:.2f} USDT")

# ————————————————
# Punto de entrada
# ————————————————
async def main():
    # Eliminar webhook activo (evita conflictos polling vs webhook)
    await bot.delete_webhook(drop_pending_updates=True)
    # Iniciar polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())