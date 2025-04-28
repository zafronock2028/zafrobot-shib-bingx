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

# Configurar variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Inicializar cliente de KuCoin (Spot)
client = Client(API_KEY, SECRET_KEY, API_PASSPHRASE)

# Inicializar Bot y Dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Estado interno del bot
bot_encendido = False

# Teclado de menú (campo 'keyboard' requerido)
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")]
    ],
    resize_keyboard=True
)

# Comando /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ ZafroBot Scalper PRO ha iniciado correctamente.\n\nSelecciona una opción:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# Función para leer saldo USDT en Spot Trading
def leer_saldo_usdt() -> float:
    cuentas = client.get_accounts()
    for cuenta in cuentas:
        if cuenta.get("currency") == "USDT" and cuenta.get("type") == "trade":
            return float(cuenta.get("available", 0))
    return 0.0

# Encender el bot
@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def encender_bot(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await message.answer("🟢 Bot encendido. Iniciando escaneo de mercado…")
        asyncio.create_task(tarea_principal())
    else:
        await message.answer("⚠️ El bot ya está encendido.")

# Apagar el bot
@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def apagar_bot(message: types.Message):
    global bot_encendido
    bot_encendido = False
    await message.answer("🔴 Bot apagado. Operaciones detenidas.")

# Estado del bot
@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def estado_bot(message: types.Message):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"📊 Estado actual del bot: *{estado}*", parse_mode="Markdown")

# Actualizar saldo
@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = leer_saldo_usdt()
    await message.answer(f"💰 Saldo disponible en Spot: *{saldo:.2f} USDT*", parse_mode="Markdown")

# Tarea principal de escaneo y trading
async def tarea_principal():
    while bot_encendido:
        saldo = leer_saldo_usdt()
        if saldo < 5:
            await bot.send_message(CHAT_ID, f"⚠️ Saldo insuficiente ({saldo:.2f} USDT). Esperando…")
            await asyncio.sleep(60)
            continue
        # Lógica de scalping placeholder
        await bot.send_message(CHAT_ID, f"🔎 Escaneando con {saldo:.2f} USDT disponibles…")
        await asyncio.sleep(30)

# Punto de entrada
async def main():
    logging.basicConfig(level=logging.INFO)
    # Eliminar cualquier webhook activo
    await bot.delete_webhook(drop_pending_updates=True)
    # Iniciar polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
