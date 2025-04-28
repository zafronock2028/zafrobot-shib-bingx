import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from kucoin.client import Client
from dotenv import load_dotenv

# Cargar las variables de entorno
load_dotenv()

# Inicializar API de KuCoin
api_key = os.getenv('API_KEY')
api_secret = os.getenv('SECRET_KEY')
api_passphrase = os.getenv('API_PASSPHRASE')

client = Client(api_key, api_secret, api_passphrase)

# Inicializar Bot de Telegram
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
bot = Bot(token=bot_token)
dp = Dispatcher()

chat_id = os.getenv('CHAT_ID')

# Función para obtener saldo disponible en Trading Spot en USDT
def obtener_saldo_usdt():
    try:
        cuentas = client.get_account_list()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                return float(cuenta['available'])
    except Exception as e:
        print(f"Error obteniendo saldo: {e}")
    return 0.0

# Comandos del bot
@dp.message(commands=["start"])
async def cmd_start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚀 Encender Bot", "🛑 Apagar Bot")
    markup.add("📊 Estado del Bot", "💰 Actualizar Saldo")
    await message.answer("✅ ZafroBot Scalper PRO ha iniciado correctamente.\n\nSelecciona una opción:", reply_markup=markup)

@dp.message(lambda message: message.text == "🚀 Encender Bot")
async def encender_bot(message: types.Message):
    await message.answer("🚀 Bot encendido. Escaneando mercado y preparando operaciones.")
    saldo = obtener_saldo_usdt()
    if saldo > 0:
        await message.answer(f"💰 Saldo disponible en KuCoin Trading: {saldo:.2f} USDT")
    else:
        await message.answer("⚠️ Saldo insuficiente para operar. Saldo actual: 0.0 USDT")

@dp.message(lambda message: message.text == "🛑 Apagar Bot")
async def apagar_bot(message: types.Message):
    await message.answer("🛑 Bot apagado correctamente.")

@dp.message(lambda message: message.text == "📊 Estado del Bot")
async def estado_bot(message: types.Message):
    await message.answer("📈 Estado actual del bot: 🟢 Encendido")

@dp.message(lambda message: message.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = obtener_saldo_usdt()
    if saldo > 0:
        await message.answer(f"💰 Saldo actualizado en KuCoin Trading: {saldo:.2f} USDT")
    else:
        await message.answer("⚠️ Saldo insuficiente para operar. Saldo actual: 0.0 USDT")

# Configuración de logs
logging.basicConfig(level=logging.INFO)

# Iniciar el bot
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())