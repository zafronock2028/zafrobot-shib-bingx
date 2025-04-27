import requests
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from flask import Flask
from threading import Thread

# Tu token real de Telegram
TELEGRAM_TOKEN = '7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM'

# API Keys de BingX
API_KEY = 'LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA'
SECRET_KEY = 'Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg'

# Inicializar bot y dispatcher
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Función para consultar saldo Spot en BingX
def obtener_saldo_spot():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/balance"
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data['code'] == 0:
            balances = data['data']['balances']
            for balance in balances:
                if balance['asset'] == 'USDT':
                    return float(balance['free'])
            return 0.0
        else:
            return 0.0
    except Exception as e:
        print(f"Error consultando saldo: {e}")
        return 0.0

# Comando /start usando Aiogram 3
@dp.message(F.text == "/start")
async def start_handler(message: Message):
    saldo = obtener_saldo_spot()
    respuesta = (
        "✅ *Bot activo y recibiendo mensajes correctamente.*\n"
        f"💰 *Saldo en Spot (USDT): {saldo:.2f} USDT*"
    )
    await message.answer(respuesta, parse_mode="Markdown")

# Flask para mantenerlo vivo
app = Flask('')

@app.route('/')
def home():
    return "ZafroBot está funcionando correctamente."

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Iniciar todo
if __name__ == '__main__':
    keep_alive()
    asyncio.run(dp.start_polling(bot))