import logging
import requests
import time
import hmac
import hashlib
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from flask import Flask
import threading
import asyncio
import os

# Credenciales de BingX
api_key = 'LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA'
secret_key = 'Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg'

# Credenciales del bot de Telegram
BOT_TOKEN = '7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM'

# Inicializar el bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Flask app para mantener Render activo
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot ZafroBot Dinámico corriendo."

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    server = threading.Thread(target=run)
    server.start()

# Función para obtener saldo en Spot
def obtener_saldo_spot(api_key, secret_key):
    try:
        timestamp = str(int(time.time() * 1000))
        params = f'timestamp={timestamp}'
        signature = hmac.new(secret_key.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()
        
        headers = {
            'X-BX-APIKEY': api_key
        }
        
        url = f"https://open-api.bingx.com/openApi/spot/v1/account/balance?{params}&signature={signature}"
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data['code'] == 0:
            balances = data['data']['balances']
            for balance in balances:
                if balance['asset'] == 'USDT':
                    return float(balance['free'])
            return 0.0
        else:
            return f"Error en API BingX: {data.get('msg', 'Error desconocido')}"
    except Exception as e:
        return f"Error obteniendo saldo: {str(e)}"

# Comando /start (bienvenida)
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "**Bienvenido a ZafroBot Notifier**\n\n"
        "✅ Bot activo y listo.\n"
        "👉 Usa /saldo para ver tu saldo Spot actualizado.",
        parse_mode=ParseMode.MARKDOWN
    )

# Nuevo comando /saldo
@dp.message(Command("saldo"))
async def saldo_handler(message: Message):
    start_time = time.time()
    saldo = obtener_saldo_spot(api_key, secret_key)
    end_time = time.time()
    elapsed_time = round(end_time - start_time, 2)
    
    if isinstance(saldo, float):
        await message.answer(
            f"💰 Saldo en Spot (USDT): {saldo:.2f} USDT\n"
            f"🕒 _Saldo actualizado hace {elapsed_time} segundos._",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await message.answer(f"⚠️ {saldo}")

# Función principal segura
async def start_bot():
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            logging.error(f"Error en polling: {e}")
            logging.info("Reintentando en 5 segundos...")
            await asyncio.sleep(5)

# Lanzar Flask y Bot
if __name__ == "__main__":
    keep_alive()
    asyncio.run(start_bot())