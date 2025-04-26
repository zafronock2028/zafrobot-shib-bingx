import os
import asyncio
import requests
from flask import Flask
from telegram import Bot

# Variables de entorno
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
API_KEY = os.environ.get('API_KEY')
SECRET_KEY = os.environ.get('SECRET_KEY')

# Instancia del bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Crear app Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot funcionando correctamente."

async def enviar_mensaje(texto):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=texto)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

async def obtener_saldo():
    try:
        headers = {
            "X-BBX-APIKEY": API_KEY,
            "X-BBX-SIGNATURE": SECRET_KEY,
        }
        response = requests.get("https://api-swap-rest.bingx.com/openApi/swap/v2/user/balance", headers=headers)
        data = response.json()

        usdt_balance = float(data["data"]["availableBalance"])
        saldo = round(usdt_balance, 2)
        return saldo
    except Exception as e:
        print(f"Error obteniendo saldo: {e}")
        return None

async def inicio_bot():
    # 1. Enviar mensaje de bienvenida
    await enviar_mensaje("✅ Bot iniciado correctamente. Bienvenido Zafronock.")

    # 2. Obtener y enviar saldo
    saldo = await obtener_saldo()
    if saldo is not None:
        await enviar_mensaje(f"💰 Saldo disponible: {saldo} USDT.")
    else:
        await enviar_mensaje("⚠️ No se pudo obtener el saldo.")

    # 3. Mensaje de inicio de análisis
    await enviar_mensaje("🔍 Iniciando análisis... Buscando mejor oportunidad.")

# Ejecutar
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(inicio_bot())
    app.run(host='0.0.0.0', port=10000)