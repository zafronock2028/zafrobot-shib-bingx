import os
import requests
import hmac
import hashlib
import time
from telegram import Bot

# Datos de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Inicializar bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Función para firmar los parámetros
def firmar_parametros(params):
    query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params)])
    return hmac.new(SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

# Función para obtener saldo
def obtener_saldo():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/balance"
    timestamp = str(int(time.time() * 1000))
    params = {
        "timestamp": timestamp
    }
    params["signature"] = firmar_parametros(params)
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    response = requests.get(url, headers=headers, params=params)
    try:
        data = response.json()
        if data.get('code') == 0:
            balances = data['data']['balances']
            for asset in balances:
                if asset['asset'] == "USDT":
                    return float(asset['free'])
            return 0.0
        else:
            return None
    except Exception as e:
        print(f"Error procesando saldo: {e}")
        return None

# Función para enviar el mensaje de inicio
def enviar_mensaje_inicio(saldo):
    if saldo is not None:
        mensaje = f"✅ ¡Bot activo!\n💰 Saldo disponible: ${saldo:.2f}"
    else:
        mensaje = "⚠️ Bot activo, pero no se pudo obtener el saldo."
    bot.send_message(chat_id=CHAT_ID, text=mensaje)

# Función principal
def main():
    saldo = obtener_saldo()
    enviar_mensaje_inicio(saldo)

if __name__ == "__main__":
    main()
