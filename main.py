import logging
import asyncio
import os
import requests
from aiogram import Bot, Dispatcher, types
from flask import Flask

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Inicializar bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

# Función para consultar saldo USDT real en Spot
def obtener_saldo_spot():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/balance"
    headers = {
        "X-BX-APIKEY": API_KEY,
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        balances = response.json().get('data', [])
        
        # Buscar saldo USDT
        for asset in balances:
            if asset['asset'] == 'USDT':
                balance = float(asset['free'])
                return balance
        return 0.0
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return None

# Comando /start
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await message.answer("✅ Bot activo y listo.\n👉 Usa /saldo para ver tu saldo Spot actualizado.")

# Comando /saldo
@dp.message_handler(commands=['saldo'])
async def saldo_handler(message: types.Message):
    await message.answer("⏳ Consultando saldo en tiempo real...")
    saldo = obtener_saldo_spot()
    if saldo is not None:
        texto = f"""
💰 *Saldo USDT disponible en Spot:*
`{saldo:.2f}` USDT

🕒 _Actualizado en tiempo real_
        """
        await message.answer(texto, parse_mode='Markdown')
    else:
        await message.answer("⚠️ No se pudo obtener el saldo. Intenta nuevamente en unos segundos.")

# Crear app Flask para mantener vivo en Render
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot Notifier está corriendo."

# Función para iniciar el bot
async def iniciar_bot():
    await dp.start_polling()

# Ejecutar
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(iniciar_bot())
    app.run(host="0.0.0.0", port=10000)