import requests
import time
import pytz
import datetime
from flask import Flask
from telegram import Bot
import os

# Cargar variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

bot = Bot(token=TELEGRAM_BOT_TOKEN)
app = Flask(__name__)

def obtener_saldo():
    url = "https://open-api.bingx.com/openApi/swap/v2/user/balance"
    headers = {
        "X-BX-APIKEY": API_KEY,
    }
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        balance = float(data['data']['balance']['availableBalance'])
        return balance
    except Exception as e:
        print("Error al obtener saldo:", e)
        return None

async def enviar_mensaje(texto):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=texto)
    except Exception as e:
        print("Error enviando mensaje:", e)

async def main():
    # Mensaje de bienvenida
    await enviar_mensaje("✅ Bot iniciado correctamente.")

    # Intentar obtener el saldo
    saldo = obtener_saldo()
    if saldo is not None:
        await enviar_mensaje(f"💰 Saldo disponible: {saldo:.2f} USDT")
    else:
        await enviar_mensaje("⚠️ No se pudo obtener el saldo.")

    # Mensaje de inicio de análisis
    await enviar_mensaje("🔎 Iniciando análisis... Buscando mejor oportunidad.")

# Ejecutar todo después de que Flask arranque
@app.before_first_request
def iniciar_bot():
    import asyncio
    asyncio.create_task(main())

@app.route('/')
def home():
    return "Bot funcionando correctamente."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)