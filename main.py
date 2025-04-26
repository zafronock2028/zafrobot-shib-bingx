import os
import requests
import threading
import time
from flask import Flask
from telegram import Bot

# Cargar variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

app = Flask(__name__)
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def obtener_saldo():
    url = "https://api-swap-rest.bingx.com/openApi/swap/v2/user/balance"
    headers = {
        "X-BX-APIKEY": API_KEY,
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        for asset in data['data']:
            if asset['asset'] == 'USDT':
                return asset['balance']
        return None
    except Exception as e:
        print(f"Error al obtener saldo: {e}")
        return None

def enviar_mensajes_iniciales():
    try:
        bot.send_message(chat_id=CHAT_ID, text="🚀 Bot iniciado correctamente en Render.")
        time.sleep(1)

        saldo = obtener_saldo()
        if saldo:
            bot.send_message(chat_id=CHAT_ID, text=f"💰 Saldo disponible: {saldo} USDT")
        else:
            bot.send_message(chat_id=CHAT_ID, text="⚠️ No se pudo obtener el saldo.")

        time.sleep(1)
        bot.send_message(chat_id=CHAT_ID, text="🔎 Iniciando análisis... Buscando mejor oportunidad.")

    except Exception as e:
        print(f"Error enviando mensajes iniciales: {e}")

@app.route('/')
def home():
    return "Bot funcionando correctamente."

def iniciar_bot():
    time.sleep(2)  # Esperar unos segundos para asegurar que el servidor esté en línea
    enviar_mensajes_iniciales()

if __name__ == '__main__':
    threading.Thread(target=iniciar_bot).start()
    app.run(host='0.0.0.0', port=10000)