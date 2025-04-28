from kucoin.client import Client
import asyncio
from aiogram import Bot, Dispatcher, types
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Configuración
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Inicializar cliente de KuCoin SPOT
client = Client(API_KEY, API_SECRET, API_PASSPHRASE)

# Inicializar bot de Telegram
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# Variables de control
bot_encendido = False

# Funciones
async def consultar_saldo():
    balances = client.get_accounts()
    for balance in balances:
        if balance['currency'] == 'USDT' and balance['type'] == 'trade':
            return float(balance['available'])
    return 0.0

async def enviar_mensaje(texto):
    await bot.send_message(chat_id=CHAT_ID, text=texto)

async def analizar_y_operar():
    global bot_encendido
    while bot_encendido:
        saldo = await consultar_saldo()
        if saldo < 5:
            await enviar_mensaje("⚠️ Saldo insuficiente para operar. Saldo actual: {:.2f} USDT".format(saldo))
            await asyncio.sleep(60)
            continue

        # Aquí colocarías tu lógica de análisis (por ahora es ejemplo)
        await enviar_mensaje("Buscando oportunidad de trading...")

        await asyncio.sleep(10)  # Esperar unos segundos antes de analizar de nuevo

# Handlers de Telegram
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("✅ *ZafroBot Scalper PRO* ha iniciado correctamente.\n\nSelecciona una opción:", parse_mode="Markdown")

@dp.message_handler(lambda message: message.text == "🚀 Encender Bot")
async def encender_bot(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await message.answer("🚀 Bot encendido. Escaneando mercado y preparando operaciones.")
        asyncio.create_task(analizar_y_operar())
    else:
        await message.answer("⚡ El bot ya está encendido.")

@dp.message_handler(lambda message: message.text == "🛑 Apagar Bot")
async def apagar_bot(message: types.Message):
    global bot_encendido
    if bot_encendido:
        bot_encendido = False
        await message.answer("🛑 Bot apagado exitosamente.")
    else:
        await message.answer("⚡ El bot ya está apagado.")

@dp.message_handler(lambda message: message.text == "📊 Estado del Bot")
async def estado_bot(message: types.Message):
    estado = "Encendido" if bot_encendido else "Apagado"
    await message.answer(f"📈 Estado actual del Bot: {estado}")

@dp.message_handler(lambda message: message.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = await consultar_saldo()
    await message.answer(f"💰 Saldo actual disponible: {saldo:.2f} USDT")

# Función principal
async def main():
    from aiogram import executor
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())