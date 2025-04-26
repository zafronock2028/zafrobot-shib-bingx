import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from flask import Flask
import requests

app = Flask(__name__)

# Variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Crear bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

async def obtener_saldo():
    try:
        url = "https://open-api.bingx.com/openApi/user/balance"
        headers = {
            "X-BX-APIKEY": API_KEY
        }
        params = {
            "currency": "USDT"
        }
        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        if data["code"] == 0:
            balance = float(data["data"]["balance"])
            return balance
        else:
            return None
    except Exception as e:
        print(f"Error al obtener saldo: {e}")
        return None

async def start_bot():
    try:
        saldo = await obtener_saldo()
        if saldo is not None:
            await bot.send_message(chat_id=CHAT_ID, text=f"✅ Bot vinculado exitosamente.\nSaldo disponible en Spot: {saldo:.2f} USDT")
        else:
            await bot.send_message(chat_id=CHAT_ID, text="⚠️ Bot vinculado, pero no se pudo obtener el saldo.")
    except Exception as e:
        await bot.send_message(chat_id=CHAT_ID, text=f"❌ Error al iniciar bot: {e}")

@app.route('/')
async def home():
    asyncio.create_task(start_bot())
    return 'Bot funcionando correctamente.'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)