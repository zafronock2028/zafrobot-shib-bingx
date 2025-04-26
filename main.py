import time
import requests
import pytz
from datetime import datetime
from flask import Flask
from telegram import Bot

# Datos de entorno
API_KEY = "TU_API_KEY"
SECRET_KEY = "TU_SECRET_KEY"
TELEGRAM_BOT_TOKEN = "TU_TELEGRAM_BOT_TOKEN"
CHAT_ID = "TU_CHAT_ID"

# Configura tu par
SYMBOL = "SHIB-USDT"
API_URL = "https://open-api.bingx.com/openApi/swap/v2/user/balance"

# Inicializar Flask para mantener Render activo
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot Dinámico está corriendo."

def obtener_saldo():
    headers = {
        'X-BX-APIKEY': API_KEY,
    }
    try:
        response = requests.get(API_URL, headers=headers)
        response_json = response.json()
        for asset in response_json['data']:
            if asset['asset'] == 'USDT':
                return float(asset['availableMargin'])
    except Exception as e:
        print(f"Error al obtener saldo: {e}")
    return None

def enviar_mensaje(bot, texto):
    try:
        bot.send_message(chat_id=CHAT_ID, text=texto)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    # 1. Mensaje de bienvenida
    enviar_mensaje(bot, "✅ Bot iniciado exitosamente. ¡Bienvenido Zafronock!")

    # 2. Detectar saldo
    saldo = obtener_saldo()
    if saldo is not None:
        enviar_mensaje(bot, f"💰 Saldo detectado: ${saldo:.2f}")
    else:
        enviar_mensaje(bot, "⚠️ Bot iniciado, pero no se pudo obtener el saldo.")

    # 3. Mensaje de inicio de análisis
    enviar_mensaje(bot, "🧠 Comenzando análisis... Buscando la mejor oportunidad para invertir. ¡Prepárate!")

    # Aquí iría el loop de análisis y trading
    while True:
        time.sleep(30)
        # Aquí puedes luego añadir tu lógica de trading de scalping

if __name__ == "__main__":
    import threading
    threading.Thread(target=main).start()
    app.run(host="0.0.0.0", port=10000)