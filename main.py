import os
import asyncio
import aiohttp
import requests
from aiogram import Bot, Dispatcher, types
from flask import Flask

app = Flask(__name__)

# Variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
CHAT_ID = os.getenv('CHAT_ID')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Crear bot y dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

@app.route('/')
async def home():
    return 'Bot funcionando correctamente.'

async def obtener_saldo():
    headers = {
        'X-BX-APIKEY': API_KEY,
        'X-BX-APISECRET': SECRET_KEY
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://open-api.bingx.com/openApi/user/getBalance') as resp:
                data = await resp.json()
                balance_list = data.get('data', {}).get('balances', [])
                for coin in balance_list:
                    if coin.get('asset') == 'USDT':
                        return float(coin.get('balance', 0))
                return 0.0
    except Exception as e:
        return None

async def start_bot():
    try:
        saldo = await obtener_saldo()
        if saldo is not None:
            mensaje = f"✅ ¡Bot vinculado exitosamente!\nSaldo disponible: {saldo:.2f} USDT."
        else:
            mensaje = "⚠️ Error al obtener el saldo de BingX."
        await bot.send_message(chat_id=CHAT_ID, text=mensaje)
    except Exception as e:
        await bot.send_message(chat_id=CHAT_ID, text=f"Error en el bot: {e}")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    app.run(host='0.0.0.0', port=5000)