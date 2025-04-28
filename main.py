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
CHAT_ID = int(os.getenv("CHAT_ID"))

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Inicializar cliente de KuCoin (Spot) y bot de Telegram\client = Client(API_KEY, SECRET_KEY, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Estado global del bot y tarea de escaneo
bot_encendido = False
scan_task = None

# Menú de opciones de Telegram
menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")]
    ],
    resize_keyboard=True
)

# Handler para /start
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    global bot_encendido
    bot_encendido = False
    await message.answer(
        "✅ ZafroBot Scalper PRO V1 iniciado.\nSelecciona una opción:",
        reply_markup=menu
    )

# Función para leer saldo USDT en Spot Trading
def leer_saldo_usdt() -> float:
    try:
        cuentas = client.get_accounts()
        for c in cuentas:
            if c.get("currency") == "USDT" and c.get("type") == "trade":
                return float(c.get("available", 0))
    except Exception as e:
        logging.error(f"Error leyendo saldo: {e}")
    return 0.0

# Tarea principal de escaneo de mercado\async def tarea_principal(chat_id: int):
    global bot_encendido
    while bot_encendido:
        saldo = leer_saldo_usdt()
        if saldo < 5:
            await bot.send_message(chat_id, f"⚠️ Saldo insuficiente: {saldo:.2f} USDT. Esperando…")
        else:
            await bot.send_message(chat_id, f"🔎 Escaneando mercado con {saldo:.2f} USDT disponibles…")
        await asyncio.sleep(30)

# Encender el bot
@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def encender(message: types.Message):
    global bot_encendido, scan_task
    if not bot_encendido:
        bot_encendido = True
        await message.answer("🟢 Bot encendido. Iniciando escaneo de mercado…")
        scan_task = asyncio.create_task(tarea_principal(message.chat.id))
    else:
        await message.answer("⚠️ El bot ya está encendido.")

# Apagar el bot
@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def apagar(message: types.Message):
    global bot_encendido, scan_task
    if bot_encendido:
        bot_encendido = False
        if scan_task:
            scan_task.cancel()
            scan_task = None
        await message.answer("🔴 Bot apagado. Operaciones detenidas.")
    else:
        await message.answer("⚠️ El bot ya está apagado.")

# Estado del bot
@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def estado(message: types.Message):
    estado_text = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"📊 Estado actual del bot: {estado_text}")

# Actualizar saldo
@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = leer_saldo_usdt()
    await message.answer(f"💰 Saldo disponible: {saldo:.2f} USDT")

# Punto de entrada\async def main():
    # Eliminar webhook para evitar conflictos
    await bot.delete_webhook(drop_pending_updates=True)
    # Iniciar polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
