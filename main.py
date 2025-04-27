import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from binance import AsyncClient
from flask import Flask
import os

# Configura tus claves y tokens
API_KEY = "LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA"
API_SECRET = "Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg"
TELEGRAM_TOKEN = "7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM"  # Tu token real de bot Telegram

# Configurar el bot de Telegram
bot = Bot(token=TELEGRAM_TOKEN, parse_mode="Markdown")
dp = Dispatcher()

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Función para obtener el saldo de USDT en la cuenta spot
async def get_usdt_balance():
    client = await AsyncClient.create(API_KEY, API_SECRET)
    try:
        account_info = await client.get_account()
        balances = account_info.get('balances', [])
        for asset in balances:
            if asset['asset'] == 'USDT':
                usdt_balance = float(asset['free'])
                return usdt_balance
        return 0.0
    finally:
        await client.close_connection()

# Comando /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✅ *Bot activo y listo.*\n👉 Usa /saldo para ver tu saldo Spot actualizado.")

# Comando /saldo
@dp.message(Command("saldo"))
async def saldo_handler(message: types.Message):
    await message.answer("⏳ *Consultando saldo en tiempo real...*")
    try:
        saldo = await get_usdt_balance()
        saldo_text = f"💰 *Saldo USDT disponible en Spot:* \n`{saldo:.2f}` *USDT*\n\n🕓 _Actualizado en tiempo real_"
        await message.answer(saldo_text)
    except Exception as e:
        await message.answer(f"⚠️ No se pudo obtener el saldo. Error: {e}")

# Mantener la app activa (por Render)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot ZafroBot Notifier está corriendo."

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    app.run(host="0.0.0.0", port=os.environ.get('PORT', 10000))