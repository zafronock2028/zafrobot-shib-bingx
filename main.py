# Importar librerías
import os
import time
import requests
import hashlib
import hmac
import urllib.parse
import telegram

# Variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Inicializar el bot de Telegram
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

# Función para enviar mensajes por Telegram
def enviar_mensaje(texto):
    bot.send_message(chat_id=CHAT_ID, text=texto)

# Función para firmar los parámetros con HMAC SHA256 (BingX usa esta firma)
def firmar_parametros(params):
    query_string = urllib.parse.urlencode(params)
    signature = hmac.new(SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

# Función para obtener el saldo de USDT
def obtener_saldo():
    url = "https://open-api.bingx.com/openApi/user/assets"
    timestamp = str(int(time.time() * 1000))
    params = {
        "timestamp": timestamp
    }
    params["signature"] = firmar_parametros(params)
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        if data["code"] == 0:
            balances = data["data"]["balances"]
            for balance in balances:
                if balance["asset"] == "USDT":
                    return float(balance["balance"])
        else:
            enviar_mensaje(f"⚠️ Error al obtener saldo: {data}")
    except Exception as e:
        enviar_mensaje(f"⚠️ Excepción obteniendo saldo: {e}")
    return None

# Función principal
def main():
    enviar_mensaje("⚡ *ZafroBot Notifier* ha arrancado con éxito.\nComprobando saldo disponible...")
    saldo = obtener_saldo()
    if saldo is not None:
        enviar_mensaje(f"✅ *Saldo actual detectado:* {saldo} USDT")
    else:
        enviar_mensaje("⚠️ No se pudo obtener el saldo, revisa la API.")

# Ejecutar el bot
if __name__ == "__main__":
    main()
