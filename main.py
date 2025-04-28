import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Client

# — Cargar variables de entorno —
load_dotenv()
API_KEY            = os.getenv("API_KEY")
SECRET_KEY         = os.getenv("SECRET_KEY")
API_PASSPHRASE     = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Asegúrate de que CHAT_ID sea entero
try:
    CHAT_ID = int(os.getenv("CHAT_ID", "0"))
except ValueError:
    CHAT_ID = 0

# — Configurar logging —
logging.basicConfig(level=logging.INFO)

# — Inicializar clientes —
client = Client(API_KEY, SECRET_KEY, API_PASSPHRASE)  # KuCoin Spot
bot    = Bot(token=TELEGRAM_BOT_TOKEN)
dp     = Dispatcher()

# — Estado global —
bot_running = False
scan_task   = None

# — Teclado de menú —
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="🛠️ Debug Balances")]
    ],
    resize_keyboard=True
)

# — Handlers —
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    global bot_running
    bot_running = False
    await message.answer(
        "✅ *ZafroBot Scalper PRO V1* iniciado.\nSelecciona una opción:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

def get_usdt_balance() -> float:
    """Suma el USDT disponible en todas tus cuentas Spot."""
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
    """Envía un mensaje cada 30 s con tu balance o advertencia."""
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

@dp.message(lambda m: m.text == "🛠️ Debug Balances")
async def cmd_debug_balances(message: types.Message):
    try:
        accounts = client.get_accounts()
        lines = [
            f"{acc['currency']} ({acc['type']}): available={acc['available']}"
            for acc in accounts if acc.get("currency") == "USDT"
        ]
        text = "\n".join(lines) if lines else "No hay USDT en ninguna cuenta."
    except Exception as e:
        text = f"Error al debuguear balances: {e}"
    await message.answer(f"🔧 Debug USDT:\n{text}")

# — Punto de entrada —
async def main():
    # Elimina cualquier webhook previo para evitar conflictos
    await bot.delete_webhook(drop_pending_updates=True)
    # Inicia polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())