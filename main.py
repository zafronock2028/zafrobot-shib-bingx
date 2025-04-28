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
API_KEY       = os.getenv("API_KEY")
API_SECRET    = os.getenv("SECRET_KEY")
API_PASSPHRASE= os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN= os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID       = int(os.getenv("CHAT_ID", 0))

# ─── Clientes ─────────────────────────────────────────────────────────────────
# KuCoin (síncrono)
kucoin = Client(API_KEY, API_SECRET, API_PASSPHRASE)
# Telegram
bot = Bot(token=TELEGRAM_TOKEN)
dp  = Dispatcher()

# ─── Estado global ─────────────────────────────────────────────────────────────
_last_balance: float = 0.0


# ─── Teclado principal ─────────────────────────────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🚀 Encender Bot"), KeyboardButton("🛑 Apagar Bot")],
        [KeyboardButton("📊 Estado del Bot"), KeyboardButton("💰 Actualizar Saldo")],
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
    # lanzamos la tarea periódica de chequeo
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
    """
    Invoca el cliente síncrono de KuCoin en un hilo y devuelve el disponible de USDT.
    """
    accounts = await asyncio.to_thread(
        kucoin.get_accounts,      # método síncrono
        "USDT",                   # currency
        "trade"                   # type
    )
    if not accounts:
        return 0.0
    # tomar el primer account
    return float(accounts[0].get("available", 0.0))


async def _task_chequear_saldo():
    """
    Cada 60s comprueba el saldo y notifica cambios (depósitos/retiros).
    """
    global _last_balance

    # inicializamos con el valor actual
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