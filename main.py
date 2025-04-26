import os
import time
import requests
import pytz
from flask import Flask
from telegram import Bot

# Cargar variables de entorno
API_KEY = os.environ.get('API_KEY')
SECRET_KEY = os.environ.get('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# Crear instancia del bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Crear app Flask
app = Flask(__name__)

# Función para obtener el saldo de BingX
def obtener_saldo():
    try:
        url = "https://api-swap-rest.bingx.com/openApi/swap/v2/user/balance"
        headers = {
            "X-BX-APIKEY": API_KEY
        }
        response = requests.get(url, headers=headers)
        data = response.json()
        saldo = None

        if 'data' in data:
            balances = data['data']
            for balance in balances:
                if balance['asset'] == 'USDT':
                    saldo = float(balance['availableMargin'])
                    break

        return saldo

    except Exception as e:
        print(f"Error al obtener saldo: {e}")
        return None

# Función que se ejecuta al iniciar
def iniciar_bot():
    try:
        # Mensaje 1: Bot iniciado
        bot.send_message(chat_id=CHAT_ID, text="✅ Bot iniciado correctamente.")
        
        # Obtener saldo
        saldo = obtener_saldo()

        # Mensaje 2: Saldo detectado o error
        if saldo is not None:
            bot.send_message(chat_id=CHAT_ID, text=f"💰 Saldo disponible detectado: {saldo:.2f} USDT.")
        else:
            bot.send_message(chat_id=CHAT_ID, text="⚠️ No se pudo obtener el saldo.")

        # Mensaje 3: Iniciando análisis
        bot.send_message(chat_id=CHAT_ID, text="🔍 Iniciando análisis... Buscando mejor oportunidad.")

    except Exception as e:
        print(f"Error al iniciar el bot: {e}")

# Ruta principal para verificar que Flask corre
@app.route('/')
def home():
    return "Bot funcionando correctamente."

# Iniciar el bot al arrancar
if __name__ == '__main__':
    iniciar_bot()
    app.run(host='0.0.0.0', port=10000)