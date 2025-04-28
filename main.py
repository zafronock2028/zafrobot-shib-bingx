import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Client

# Variables
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Conexión con KuCoin
client = Client(API_KEY, API_SECRET, API_PASSPHRASE)

# Conexión con Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Teclado personalizado
keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔵 Encender"), KeyboardButton(text="🔴 Apagar")],
    [KeyboardButton(text="💰 Actualizar Saldo"), KeyboardButton(text="📊 Estado")]
], resize_keyboard=True)

# Estado del bot
bot_activado = False

# Comando /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    global bot_activado
    bot_activado = False
    await message.answer("✅ ZafroBot Scalper PRO ha iniciado correctamente. Listo para recibir comandos.", reply_markup=keyboard)

# Encender bot
@dp.message(F.text == "🔵 Encender")
async def encender_bot(message: types.Message):
    global bot_activado
    if not bot_activado:
        bot_activado = True
        await message.answer("🟢 Bot Encendido. Analizando oportunidades del mercado.")
        asyncio.create_task(escanear_mercado())
    else:
        await message.answer("⚠️ El bot ya está encendido.")

# Apagar bot
@dp.message(F.text == "🔴 Apagar")
async def apagar_bot(message: types.Message):
    global bot_activado
    bot_activado = False
    await message.answer("🔴 Bot Apagado.")

# Actualizar saldo
@dp.message(F.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = client.get_account_list('trade', 'USDT')
    saldo_usdt = 0
    if saldo and saldo[0]['balance']:
        saldo_usdt = round(float(saldo[0]['balance']), 2)
    await message.answer(f"💳 Saldo actual en KuCoin Spot: {saldo_usdt} USDT")

# Estado del bot
@dp.message(F.text == "📊 Estado")
async def estado_bot(message: types.Message):
    estado = "🟢 Activado" if bot_activado else "🔴 Apagado"
    await message.answer(f"📊 Estado actual del bot: {estado}")

# Escanear mercado (simulación)
async def escanear_mercado():
    while bot_activado:
        # Aquí irá el análisis profesional del mercado para entrar en operaciones reales.
        await asyncio.sleep(60)  # Espera de ejemplo

# Notificar depósito
async def notificar_deposito():
    ultimo_saldo = 0
    while True:
        saldo = client.get_account_list('trade', 'USDT')
        saldo_actual = round(float(saldo[0]['balance']), 2) if saldo and saldo[0]['balance'] else 0
        if saldo_actual > ultimo_saldo:
            incremento = saldo_actual - ultimo_saldo
            await bot.send_message(CHAT_ID, f"💵 Depósito detectado: +{incremento:.2f} USDT")
        ultimo_saldo = saldo_actual
        await asyncio.sleep(300)

# Inicio principal
async def main():
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(notificar_deposito())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())