import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Client

# — Carga de entorno —
load_dotenv()
API_KEY            = os.getenv("API_KEY")
SECRET_KEY         = os.getenv("SECRET_KEY")
API_PASSPHRASE     = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
try:
    CHAT_ID = int(os.getenv("CHAT_ID", "0"))
except ValueError:
    CHAT_ID = 0

# — Logging —
logging.basicConfig(level=logging.INFO)

# — Inicializaciones —
client = Client(API_KEY, SECRET_KEY, API_PASSPHRASE)
bot    = Bot(token=TELEGRAM_BOT_TOKEN)
dp     = Dispatcher()

bot_running = False
scan_task   = None

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🚀 Encender Bot"), KeyboardButton("🛑 Apagar Bot")],
        [KeyboardButton("📊 Estado del Bot"), KeyboardButton("💰 Actualizar Saldo")],
        [KeyboardButton("🛠️ Debug Balances")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    global bot_running
    bot_running = False
    await message.answer(
        "✅ ZafroBot Scalper PRO V1 iniciado.\nSelecciona una opción:",
        parse_mode="Markdown",
        reply_markup=menu
    )

def get_usdt_balance() -> float:
    """Suma todo el USDT disponible en Spot."""
    total = 0.0
    try:
        accounts = client.get_accounts()
        for acc in accounts:
            if acc.get("currency") == "USDT":
                total += float(acc.get("available", 0))
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
    return total

async def market_scan(chat_id: int):
    global bot_running
    while bot_running:
        bal = get_usdt_balance()
        if bal < 5:
            await bot.send_message(chat_id, f"⚠️ Saldo insuficiente: {bal:.2f} USDT. Esperando…")
        else:
            await bot.send_message(chat_id, f"🔎 Escaneando mercado con {bal:.2f} USDT…")
        await asyncio.sleep(30)

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def turn_on(message: types.Message):
    global bot_running, scan_task
    if not bot_running:
        bot_running = True
        await message.answer("🟢 Bot encendido. Iniciando escaneo…")
        scan_task = asyncio.create_task(market_scan(message.chat.id))
    else:
        await message.answer("⚠️ El bot ya está encendido.")

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def turn_off(message: types.Message):
    global bot_running, scan_task
    bot_running = False
    if scan_task:
        scan_task.cancel()
        scan_task = None
    await message.answer("🔴 Bot apagado.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def status(message: types.Message):
    state = "🟢 Encendido" if bot_running else "🔴 Apagado"
    await message.answer(f"📊 Estado actual: {state}")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def update_balance(message: types.Message):
    bal = get_usdt_balance()
    await message.answer(f"💰 Saldo disponible: {bal:.2f} USDT")

@dp.message(lambda m: m.text == "🛠️ Debug Balances")
async def debug_balances(message: types.Message):
    """Muestra crudo lo que devuelve KuCoin para diagnosticar."""
    try:
        accounts = client.get_accounts()
        text = "\n".join(f\"{a['currency']} ({a['type']}): available={a['available']}\" for a in accounts if a['currency']=='USDT')
    except Exception as e:
        text = f"Error al debuguear balances: {e}"
    await message.answer(f"🔧 Debug USDT:\n{text or 'No hay USDT en ninguna cuenta.'}")

async def main():
    # Elimina cualquier webhook previo
    await bot.delete_webhook(drop_pending_updates=True)
    # Inicia polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())