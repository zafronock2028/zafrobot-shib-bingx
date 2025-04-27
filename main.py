import os
import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand
from aiogram.filters import Command
from aiogram import F
from flask import Flask
from threading import Thread

# Configura el logging
logging.basicConfig(level=logging.INFO)

# Carga las API keys de las variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Inicializa el bot y el dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Función para obtener saldo de USDT en Spot
def obtener_saldo_usdt():
    url = "https://api.bingx.com/openApi/swap/v2/user/balance"
    headers = {
        "X-BX-APIKEY": API_KEY,
    }
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data["code"] == 0:
            assets = data["data"]["assets"]
            for asset in assets:
                if asset["asset"] == "USDT":
                    balance = float(asset["availableBalance"])
                    return balance
        return None
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return None

# Comando /start
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ Bot activo y listo.\n👉 Usa /saldo para ver tu saldo Spot actualizado.")

# Comando /saldo
@dp.message(Command("saldo"))
async def saldo(message: types.Message):
    await message.answer("⏳ Consultando saldo en tiempo real...")
    saldo = obtener_saldo_usdt()
    if saldo is not None:
        await message.answer(
            f"🪙 Saldo USDT disponible en Spot:\n\n**{saldo:.2f} USDT**\n\n🕒 _Actualizado en tiempo real_",
            parse_mode="Markdown"
        )
    else:
        await message.answer("⚠️ No se pudo obtener el saldo. Intenta nuevamente en unos segundos.")

# Servidor Flask para mantener Render activo
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running."

def run_webserver():
    app.run(host="0.0.0.0", port=10000)

# Función principal
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    Thread(target=run_webserver).start()
    asyncio.run(main())