import requests
import time
import hmac
import hashlib
import os
import json
from telegram import Bot

# Variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Inicializar el bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Función para enviar mensajes a Telegram
def enviar_mensaje(mensaje):
    try:
        bot.send_message(chat_id=CHAT_ID, text=mensaje)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

# Función para firmar los parámetros
def firmar_parametros(params):
    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    signature = hmac.new(SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

# Función para obtener saldo
def obtener_saldo():
    url = 'https://open-api.bingx.com/openApi/spot/v1/account/assets'
    timestamp = str(int(time.time() * 1000))
    params = {
        'timestamp': timestamp
    }
    params['signature'] = firmar_parametros(params)
    headers = {
        'X-BX-APIKEY': API_KEY
    }
    try:
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        if 'data' in data:
            for asset in data['data']['balances']:
                if asset['asset'] == 'USDT':
                    return float(asset['free'])
        else:
            print(f"Error en respuesta de saldo: {data}")
            return None
    except Exception as e:
        print(f"Error obteniendo balance: {e}")
        return None

# Función principal
def main():
    enviar_mensaje("✅ Bot iniciado correctamente.")
    while True:
        saldo = obtener_saldo()
        if saldo is not None:
            print(f"Saldo actual: {saldo} USDT")
        else:
            print("No se pudo obtener el saldo.")
        time.sleep(60)  # Esperar 1 minuto antes de volver a consultar

if __name__ == "__main__":
    main()
