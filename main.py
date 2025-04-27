import asyncio
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import requests
import time
import hmac
import hashlib

# Credenciales
BOT_TOKEN = '7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM'

API_KEY = 'LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA'
SECRET_KEY = 'Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg'

# Iniciar Bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Función para obtener saldo en BingX Spot
def get_spot_balance():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/balance"
    timestamp = str(int(time.time() * 1000))
    
    params = {
        "timestamp": timestamp
    }
    
    query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params)])
    signature = hmac.new(SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    
    final_url = f"{url}?{query_string}&signature={signature}"
    response = requests.get(final_url, headers=headers)
    
    try:
        result = response.json()
        for asset in result.get('data', []):
            if asset.get('asset') == 'USDT':
                balance = asset.get('balance')
                return balance
        return "No se encontró saldo en USDT."
    except Exception as e:
        return f"Error obteniendo saldo: {e}"

# Handler para /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✅ Bot activo y recibiendo mensajes correctamente.")
    saldo = get_spot_balance()
    await message.answer(f"💰 Tu saldo disponible en Spot (USDT) es: {saldo}")

# Mantener app viva
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot funcionando correctamente."

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Main
async def main():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())