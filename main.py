import os
import asyncio
import time
import hmac
import hashlib
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from flask import Flask
from threading import Thread

# --- Configuración ---
API_KEY = "LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA"
SECRET_KEY = "Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg"
BOT_TOKEN = "7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM"

bot = Bot(token=BOT_TOKEN, parse_mode="Markdown")
dp = Dispatcher()

# --- Flask para mantener Render activo ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot ZafroBot Notifier corriendo correctamente."

# --- Función para obtener saldo USDT en Spot ---
def obtener_saldo_spot_usdt():
    try:
        timestamp = str(int(time.time() * 1000))
        params = f"timestamp={timestamp}"
        signature = hmac.new(SECRET_KEY.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()

        url = f"https://open-api.bingx.com/openApi/spot/v1/account/balance?{params}&signature={signature}"
        headers = {
            'X-BX-APIKEY': API_KEY
        }

        response = requests.get(url, headers=headers)
        data = response.json()

        if data.get('code') == 0:
            balances = data['data']['balances']
            for balance in balances:
                if balance['asset'] == 'USDT':
                    return float(balance['free'])
        return None
    except Exception as e:
        print(f"Error al obtener saldo: {e}")
        return None

# --- Comando /start ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "✅ Bot activo y listo.\n"
        "👉 Usa /saldo para consultar tu saldo disponible en USDT."
    )

# --- Comando /saldo ---
@dp.message(Command("saldo"))
async def saldo(message: types.Message):
    await message.answer("⏳ Consultando saldo en tiempo real...")
    saldo_usdt = obtener_saldo_spot_usdt()
    if saldo_usdt is not None:
        await message.answer(
            f"💼 *ZafroBot Wallet*\n\n"
            f"💵 *Saldo disponible en Spot:*\n"
            f"`{saldo_usdt:.2f} USDT`\n\n"
            f"⏰ _Actualizado en tiempo real_"
        )
    else:
        await message.answer("⚠️ No se pudo obtener el saldo. Intenta nuevamente en unos segundos.")

# --- Función principal ---
async def main():
    await dp.start_polling(bot)

def run_flask():
    app.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(main())