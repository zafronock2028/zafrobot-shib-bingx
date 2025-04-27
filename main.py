import logging
import requests
import time
import hmac
import hashlib
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from flask import Flask
import threading
import os

# --- Tus Credenciales ---
api_key = 'LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA'
secret_key = 'Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg'
BOT_TOKEN = '7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM'
# --------------------------

# Inicializar bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Flask para mantener Render activo
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot Notifier PRO corriendo."

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    server = threading.Thread(target=run)
    server.start()

# Función para consultar saldo Spot por REST API
def obtener_saldo_spot():
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
            return None
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return None

# Comando /start
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "**Bienvenido a ZafroBot Notifier PRO**\n\n"
        "✅ Bot activo y listo.\n"
        "👉 Usa /saldo para ver tu saldo Spot actualizado.",
        parse_mode=ParseMode.MARKDOWN
    )

# Comando /saldo que consulta en vivo
@dp.message(Command("saldo"))
async def saldo_handler(message: Message):
    mensaje_espera = await message.answer(
        "💸 *Consultando saldo en vivo...*",
        parse_mode=ParseMode.MARKDOWN
    )

    saldo = obtener_saldo_spot()
    
    if saldo is not None:
        await asyncio.sleep(1)
        await mensaje_espera.edit_text(
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 *ZafroBot Wallet*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 *Saldo disponible en Spot:*\n"
            f"`{saldo:.2f} USDT`\n\n"
            f"🕒 _Actualizado en tiempo real_\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await mensaje_espera.edit_text(
            "⚠️ *No se pudo obtener el saldo.*\n"
            "_Por favor intenta nuevamente más tarde._",
            parse_mode=ParseMode.MARKDOWN
        )

# Función principal
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())