# main.py
import os
import asyncio
import logging

from kucoin.client import Client
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

# ─── Configuración ────────────────────────────────────────────────────────────
API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID        = int(os.getenv("CHAT_ID", 0))

# ─── Clientes ─────────────────────────────────────────────────────────────────
kucoin = Client(API_KEY, API_SECRET, API_PASSPHRASE)
bot    = Bot(token=TELEGRAM_TOKEN)
dp     = Dispatcher()

# ─── Estado global ─────────────────────────────────────────────────────────────
_last_balance: float = 0.0

# ─── Teclado principal ─────────────────────────────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🚀 Encender Bot"),
            KeyboardButton(text="🛑 Apagar Bot"),
        ],
        [
            KeyboardButton(text="📊 Estado del Bot"),
            KeyboardButton(text="💰 Actualizar Saldo"),
        ],
    ],
    resize_keyboard=True,
)

# ─── Comandos de usuario ───────────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(msg):
    await msg.answer(
        "✅ ZafroBot Scalper PRO V1 iniciado.\nSelecciona una opción:",
        reply_markup=keyboard
    )

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def cmd_encender(msg):
    await msg.answer("🟢 Bot encendido. Iniciando escaneo de mercado…")
    asyncio.create_task(_task_chequear_saldo())

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def cmd_apagar(msg):
    await msg.answer("🔴 Bot apagado.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def cmd_estado(msg):
    await msg.answer("📊 Estado: Operando normalmente.")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def cmd_actualizar_saldo(msg):
    bal = await _get_balance()
    await msg.answer(f"💰 Saldo actual: {bal:.2f} USDT")

# ─── Funciones internas ───────────────────────────────────────────────────────

async def _get_balance() -> float:
    accounts = await asyncio.to_thread(kucoin.get_accounts, "USDT", "trade")
    if not accounts:
        return 0.0
    return float(accounts[0].get("available", 0.0))

async def _task_chequear_saldo():
    global _last_balance
    _last_balance = await _get_balance()
    while True:
        current = await _get_balance()
        if current > _last_balance:
            diff = current - _last_balance
            await bot.send_message(CHAT_ID, f"🎉 ¡Depositado {diff:.2f} USDT!")
        elif current < _last_balance:
            diff = _last_balance - current
            await bot.send_message(CHAT_ID, f"⚠️ Retiro de {diff:.2f} USDT detectado.")
        _last_balance = current
        await asyncio.sleep(60)

# ─── Arranque del bot ─────────────────────────────────────────────────────────

async def main():
    logging.info("Start polling")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())