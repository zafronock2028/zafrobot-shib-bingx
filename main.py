import os
import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Client
from dotenv import load_dotenv

# Carga de variables de entorno
load_dotenv()
API_KEY           = os.getenv("API_KEY")
SECRET_KEY        = os.getenv("SECRET_KEY")
API_PASSPHRASE    = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN= os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID           = os.getenv("CHAT_ID")  # Asegúrate de que sea string

# Cliente KuCoin (Spot)
client = Client(API_KEY, SECRET_KEY, API_PASSPHRASE)

# Bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp  = Dispatcher()

# Estado interno
bot_encendido = False

# Teclado
keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(KeyboardButton("🚀 Encender Bot"), KeyboardButton("🛑 Apagar Bot"))
keyboard.add(KeyboardButton("📊 Estado del Bot"), KeyboardButton("💰 Actualizar Saldo"))

# Comando /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "✅ *ZafroBot Scalper PRO* está online.\n\nSelecciona una opción:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# Función para leer saldo USDT en Spot Trading
def leer_saldo_usdt() -> float:
    cuentas = client.get_accounts()
    for c in cuentas:
        if c["currency"]=="USDT" and c["type"]=="trade":
            return float(c["available"])
    return 0.0

# Encender bot
@dp.message(lambda m: m.text=="🚀 Encender Bot")
async def encender(message: Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await message.answer("🟢 Bot encendido. Iniciando escaneo de mercado…")
        asyncio.create_task(tarea_principal())
    else:
        await message.answer("⚠️ El bot ya está encendido.")

# Apagar bot
@dp.message(lambda m: m.text=="🛑 Apagar Bot")
async def apagar(message: Message):
    global bot_encendido
    bot_encendido = False
    await message.answer("🔴 Bot apagado. Operaciones detenidas.")

# Estado del bot
@dp.message(lambda m: m.text=="📊 Estado del Bot")
async def estado(message: Message):
    estado_text = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"📊 Estado actual del bot: *{estado_text}*", parse_mode="Markdown")

# Actualizar saldo
@dp.message(lambda m: m.text=="💰 Actualizar Saldo")
async def actualizar_saldo(message: Message):
    saldo = leer_saldo_usdt()
    await message.answer(f"💰 Saldo disponible en Spot: *{saldo:.2f} USDT*", parse_mode="Markdown")

# Tarea principal (escaneo y operaciones)
async def tarea_principal():
    while bot_encendido:
        saldo = leer_saldo_usdt()
        if saldo < 10:
            await bot.send_message(CHAT_ID, f"⚠️ Saldo insuficiente para operar: *{saldo:.2f} USDT*", parse_mode="Markdown")
            await asyncio.sleep(60)
            continue
        # Aquí iría tu lógica de scalping: análisis, órdenes market, TP/SL…
        await bot.send_message(CHAT_ID, f"🔎 Escaneando mercado con *{saldo:.2f} USDT* disponibles…", parse_mode="Markdown")
        await asyncio.sleep(30)  # ajusta intervalo según estrategia

# Punto de entrada
async def main():
    logging.basicConfig(level=logging.INFO)
    # Elimina cualquier webhook que pudiera estar activo
    await bot.delete_webhook(drop_pending_updates=True)
    # Inicia polling sin conflicto
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())