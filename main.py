import logging
import asyncio
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from flask import Flask
import threading

# --- Configuración ---
API_KEY = 'LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA'
SECRET_KEY = 'Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg'
TELEGRAM_BOT_TOKEN = '7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM'
CHAT_ID = '295613'  # tu chat_id
BASE_URL = 'https://open-api.bingx.com'

# --- Inicializar bot ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# --- Función para obtener el saldo de USDT en Spot ---
async def obtener_saldo():
    try:
        headers = {
            'X-BX-APIKEY': API_KEY
        }
        response = requests.get(f"{BASE_URL}/openApi/spot/v1/account/assets", headers=headers, timeout=10)
        if response.status_code == 200:
            datos = response.json()
            balances = datos.get('data', [])
            for balance in balances:
                if balance.get('asset') == 'USDT':
                    free_balance = float(balance.get('free', 0))
                    return round(free_balance, 2)
            return 0.0
        else:
            return None
    except Exception as e:
        logging.error(f"Error al consultar saldo: {e}")
        return None

# --- Comando /start ---
@dp.message(Command('start'))
async def start_handler(message: types.Message):
    await message.answer("✅ Bot activo y listo.\n👉 Usa /saldo para ver tu saldo Spot actualizado.")

# --- Comando /saldo ---
@dp.message(Command('saldo'))
async def saldo_handler(message: types.Message):
    await message.answer("⏳ Consultando saldo en tiempo real...")
    saldo = await obtener_saldo()
    if saldo is not None:
        await message.answer(
            f"🪙 *Saldo USDT disponible en Spot:*\n\n`{saldo}` *USDT*\n\n🕒 _Actualizado en tiempo real_",
            parse_mode='Markdown'
        )
    else:
        await message.answer("⚠️ No se pudo obtener el saldo. Intenta nuevamente en unos segundos.")

# --- Servidor Flask para mantener vivo Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot corriendo."

def iniciar_flask():
    app.run(host='0.0.0.0', port=10000)

# --- Main ---
async def main():
    flask_thread = threading.Thread(target=iniciar_flask)
    flask_thread.start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())