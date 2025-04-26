import asyncio
import requests
from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from flask import Flask
import os

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
CHAT_ID = int(os.getenv("CHAT_ID"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Inicializar bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Inicializar Flask
app = Flask(__name__)

# Función para consultar el saldo en BingX
def obtener_saldo():
    url = "https://open-api.bingx.com/openApi/user/assets"
    headers = {
        "X-BX-APIKEY": API_KEY,
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            balances = data["data"]["balances"]
            for balance in balances:
                if balance["asset"] == "USDT":
                    return balance["availableMargin"]
    return None

# Función para enviar el saldo
async def enviar_saldo():
    saldo = obtener_saldo()
    if saldo is not None:
        mensaje = f"Saldo disponible: {saldo} USDT"
    else:
        mensaje = "⚠️ Bot vinculado, pero no se pudo obtener el saldo.\nVerifica tus API Keys."
    await bot.send_message(chat_id=CHAT_ID, text=mensaje)

# Nuevo handler de /start usando Router
@router.message(Command("start"))
async def start_command(message: types.Message):
    await enviar_saldo()

# Endpoint de Flask
@app.route('/')
def home():
    return "ZafroBot Dinámico Pro está activo!"

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    app.run(host="0.0.0.0", port=5000)