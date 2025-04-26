import os
import time
import requests
import hmac
import hashlib
from flask import Flask
from telegram import Bot

# Variables de entorno
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
CHAT_ID = os.getenv('CHAT_ID')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Inicializar bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Variable para controlar si ya se notificó el inicio
inicio_enviado = False

# Función para obtener el saldo de USDT disponible en Spot
def obtener_saldo():
    url = "https://open-api.bingx.com/openApi/user/balance"
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}&recvWindow=5000"
    signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {
        'X-BX-APIKEY': API_KEY
    }
    final_url = f"{url}?{query_string}&signature={signature}"
    response = requests.get(final_url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        for balance in data['data']:
            if balance['asset'] == 'USDT':
                return float(balance['availableBalance'])
    return None

# Función para notificar inicio (solo una vez)
def notificar_inicio(saldo):
    global inicio_enviado
    if not inicio_enviado:
        mensaje = (
            "✅ ZafroBot Iniciado\n"
            "-----------------------------\n"
            f"💳 Saldo disponible: ${saldo} USDT\n"
            "-----------------------------\n"
            "⚡ ¡Listo para operar!"
        )
        bot.send_message(chat_id=CHAT_ID, text=mensaje)
        inicio_enviado = True

# Función principal
def main():
    while True:
        try:
            saldo = obtener_saldo()
            if saldo is not None:
                notificar_inicio(saldo)
            else:
                bot.send_message(chat_id=CHAT_ID, text="⚠️ Bot iniciado, pero no se pudo obtener el saldo.")
        except Exception as e:
            bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Error: {e}")
        time.sleep(60)  # Esperar 60 segundos

# Crear app Flask para que Render no detenga el servicio
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot está funcionando."

# Ejecutar
if __name__ == '__main__':
    import threading
    threading.Thread(target=main).start()
    app.run(host='0.0.0.0', port=10000)
