import hmac
import hashlib
import time
import requests
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types
import asyncio
import os

# === CONFIGURACIÓN DEL BOT Y API BINGX ===
API_KEY = "LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA"
SECRET_KEY = "Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot funcionando correctamente."

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

async def get_spot_balance():
    url = "https://open-api.bingx.com/openApi/user/getBalance"
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    params = {
        "timestamp": timestamp,
        "signature": signature
    }
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    
    try:
        balances = data['data']['balance']
        for asset in balances:
            if asset['asset'] == 'USDT':
                return asset['balance']
    except Exception as e:
        print(f"Error obteniendo saldo: {e}")
    return None

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("✅ Bot activo y recibiendo mensajes correctamente.")
    balance = await get_spot_balance()
    if balance:
        await message.answer(f"💰 Saldo disponible en Spot: {balance} USDT")
    else:
        await message.answer("⚠️ No se pudo obtener el saldo de Spot. Revisa tus llaves API.")

async def main():
    keep_alive()
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())