import os
import time
import requests
import asyncio
from flask import Flask
from telegram import Bot

# Variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Configuración de Flask
app = Flask(__name__)

# Inicializar bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Función para obtener el saldo disponible
def obtener_saldo():
    try:
        url = "https://open-api.bingx.com/openApi/spot/v1/account/balance"
        headers = {
            "X-BX-APIKEY": API_KEY
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        balances = response.json()["data"]["balances"]
        for asset in balances:
            if asset["asset"] == "USDT":
                return float(asset["free"])
        return 0.0
    except Exception as e:
        print(f"Error al obtener saldo: {e}")
        return None

# Función para enviar mensajes
async def enviar_mensaje(texto):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=texto)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

# Función principal
async def main():
    saldo = obtener_saldo()
    if saldo is not None:
        # Mensaje 1: Mostrar saldo
        await enviar_mensaje(f"✅ ZafroBot Iniciado\n\n💰 Saldo disponible: ${saldo:.2f} USDT\n⚡ ¡Listo para operar!")
        # Mensaje 2: Confirmar que está buscando oportunidades
        await enviar_mensaje("✅ Bot iniciado y activo.\n\nBuscando oportunidades... Te avisaré al detectar una entrada.")
    else:
        await enviar_mensaje("⚠️ Bot iniciado, pero no se pudo obtener el saldo.")

# Ejecutar en segundo plano
def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())

if __name__ == "__main__":
    run_bot()
    app.run(host='0.0.0.0', port=10000)
