# main.py
import os
import asyncio
import logging

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, Text
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from kucoin.client import UserClient

# 1️⃣ CARGA DE VARIABLES DE ENTORNO
load_dotenv()
TELEGRAM_TOKEN      = os.getenv("TELEGRAM_TOKEN")
KUCOIN_API_KEY      = os.getenv("KUCOIN_API_KEY")
KUCOIN_API_SECRET   = os.getenv("KUCOIN_API_SECRET")
KUCOIN_API_PASSPHRASE = os.getenv("KUCOIN_API_PASSPHRASE")
PROXY_URL           = os.getenv("PROXY_URL", None)  # opcional

# 2️⃣ LOGGING
logging.basicConfig(level=logging.INFO)

# 3️⃣ INSTANCIA DE TELEGRAM
bot = Bot(token=TELEGRAM_TOKEN)
dp  = Dispatcher()

# 4️⃣ INSTANCIA DE KUCOIN
kucoin_kwargs = {
    "key": KUCOIN_API_KEY,
    "secret": KUCOIN_API_SECRET,
    "passphrase": KUCOIN_API_PASSPHRASE,
}
if PROXY_URL:
    kucoin_kwargs["proxies"] = {"http": PROXY_URL, "https": PROXY_URL}
client = UserClient(**kucoin_kwargs)

# 5️⃣ ESTADO Y TAREA GLOBAL
is_running = False
task       = None

# 6️⃣ TECLADO PERSONALIZADO
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🚀 Encender Bot"), KeyboardButton("🔴 Apagar Bot")],
        [KeyboardButton("📊 Estado del Bot"), KeyboardButton("💰 Actualizar Saldo")],
        [KeyboardButton("🛠️ Debug Balances")],
    ],
    resize_keyboard=True
)

# 7️⃣ HANDLERS
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ ZafroBot Scalper PRO V1 iniciado.\nSelecciona una opción:",
        reply_markup=keyboard
    )

@dp.message(Text("🚀 Encender Bot"))
async def start_bot(message: types.Message):
    global is_running, task
    if not is_running:
        is_running = True
        task = asyncio.create_task(scan_market(message.chat.id))
        await message.answer("🟢 Bot encendido. Iniciando escaneo de mercado…", reply_markup=keyboard)
    else:
        await message.answer("⚠️ El bot ya está ejecutándose.", reply_markup=keyboard)

@dp.message(Text("🔴 Apagar Bot"))
async def stop_bot(message: types.Message):
    global is_running, task
    if is_running and task:
        task.cancel()
        is_running = False
        await message.answer("🔴 Bot detenido.", reply_markup=keyboard)
    else:
        await message.answer("⚠️ El bot no está en ejecución.", reply_markup=keyboard)

@dp.message(Text("💰 Actualizar Saldo"))
async def update_balance(message: types.Message):
    try:
        accounts = client.get_account_list("trade")
        usdt = next((a for a in accounts if a["currency"]=="USDT"), None)
        bal  = float(usdt["available"]) if usdt else 0.0
        await message.answer(f"💰 Saldo disponible: {bal:.2f} USDT", reply_markup=keyboard)
    except Exception as e:
        await message.answer(f"Error al obtener saldo: {e}", reply_markup=keyboard)

@dp.message(Text("📊 Estado del Bot"))
async def status_bot(message: types.Message):
    status = "🟢 Ejecutándose" if is_running else "🔴 Detenido"
    await message.answer(f"📊 Estado actual del bot: {status}", reply_markup=keyboard)

@dp.message(Text("🛠️ Debug Balances"))
async def debug_balances(message: types.Message):
    try:
        accounts = client.get_account_list("trade")
        lines = [
            f"{a['currency']} ({a['type']}): disponible={a['available']}, retenido={a['holds']}"
            for a in accounts
        ]
        text = "🔧 Debug Balances:\n" + "\n".join(lines)
        await message.answer(text, reply_markup=keyboard)
    except Exception as e:
        await message.answer(f"Error al debuguear balances: {e}", reply_markup=keyboard)

# 8️⃣ TAREA DE ESCANEO
async def scan_market(chat_id: int):
    try:
        while is_running:
            accounts = client.get_account_list("trade")
            usdt = next((a for a in accounts if a["currency"]=="USDT"), None)
            balance = float(usdt["available"]) if usdt else 0.0

            if balance > 0:
                await bot.send_message(chat_id, f"💰 ¡Nuevo saldo detectado: {balance:.2f} USDT! Preparando operaciones…")
                # Aquí iría tu lógica de trading...
                break
            else:
                await bot.send_message(chat_id, f"⚠️ Saldo insuficiente: {balance:.2f} USDT. Esperando…")

            await asyncio.sleep(60)  # espera 1 minuto
    except asyncio.CancelledError:
        pass

# 9️⃣ ARRANQUE DE POLLING (y borrado de webhook si lo hubiera)
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())