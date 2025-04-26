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
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Crear bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

# Obtener saldo de Spot en USDT desde BingX
def obtener_saldo():
    try:
        headers = {
            "X-BX-APIKEY": API_KEY
        }
        url = "https://open-api.bingx.com/openApi/user/assets"
        response = requests.get(url, headers=headers)
        data = response.json()
        balances = data.get('data', {}).get('balances', [])

        for asset in balances:
            if asset['asset'] == 'USDT':
                return asset['balance']

        return None
    except Exception as e:
        return None

# Página principal que lanza el bot
@app.route('/')
def home():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_bot())
    return 'Bot funcionando correctamente.'

# Función principal del bot
async def start_bot():
    try:
        saldo = obtener_saldo()

        mensaje_bienvenida = "✅ Bot vinculado exitosamente.\n\n"
        if saldo is not None:
            mensaje_bienvenida += f"💰 Saldo disponible en Spot: {saldo} USDT."
        else:
            mensaje_bienvenida += "⚠️ No se pudo obtener el saldo. Revisa tu API KEY y SECRET KEY."

        await bot.send_message(chat_id=CHAT_ID, text=mensaje_bienvenida)
    except Exception as e:
        await bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Error al iniciar el bot: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)