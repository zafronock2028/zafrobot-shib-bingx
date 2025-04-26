import os
import time
import hmac
import hashlib
import requests
from flask import Flask
from telegram import Bot

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BASE_URL = "https://open-api.bingx.com"

# Configuración inicial
bot = Bot(token=TELEGRAM_BOT_TOKEN)
par = "SHIB-USDT"
profit_total = 0.0
operacion_abierta = False

# Funciones
def firmar_parametros(params):
    query_string = "&".join([f"{key}={params[key]}" for key in sorted(params)])
    return hmac.new(SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def obtener_saldo():
    timestamp = int(time.time() * 1000)
    params = {
        "timestamp": timestamp
    }
    params["signature"] = firmar_parametros(params)
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    try:
        response = requests.get(f"{BASE_URL}/openApi/wallet/v1/balance", headers=headers, params=params)
        data = response.json()
        if 'data' in data and 'balances' in data['data']:
            for balance in data['data']['balances']:
                if balance['asset'] == 'USDT':
                    return float(balance['availableBalance'])
    except Exception as e:
        print(f"Error obteniendo balance: {e}")
    return None

def obtener_precio_actual():
    try:
        response = requests.get(f"{BASE_URL}/openApi/spot/v1/ticker/price?symbol={par}")
        data = response.json()
        return float(data['data']['price'])
    except Exception as e:
        print(f"Error obteniendo precio: {e}")
        return None

def enviar_mensaje(mensaje):
    try:
        bot.send_message(chat_id=CHAT_ID, text=mensaje)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

# Mensaje de inicio
saldo_inicial = obtener_saldo()
if saldo_inicial:
    enviar_mensaje(f"✅ ZafroBot Iniciado\n\n💳 Saldo disponible: ${saldo_inicial:.2f} USDT\n⚡ ¡Listo para operar!")
else:
    enviar_mensaje("⚠️ Bot iniciado, pero no se pudo obtener el saldo.")

# Flask app para mantener Render activo
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot is running!"

# Lógica principal del bot
def bot_loop():
    global operacion_abierta
    global profit_total

    while True:
        if not operacion_abierta:
            saldo_actual = obtener_saldo()
            if saldo_actual and saldo_actual > 5:  # Mínimo requerido para operar
                precio_compra = obtener_precio_actual()
                if precio_compra:
                    enviar_mensaje(f"🟢 Compra ejecutada a ${precio_compra:.8f}")
                    operacion_abierta = True
                    precio_objetivo = precio_compra * 1.015  # Ganancia 1.5%
                    precio_stop = precio_compra * 0.98       # Pérdida -2%

                    while operacion_abierta:
                        precio_actual = obtener_precio_actual()
                        if precio_actual:
                            if precio_actual >= precio_objetivo:
                                ganancia = saldo_actual * 0.015
                                profit_total += ganancia
                                enviar_mensaje(f"✅ ¡Operación cerrada! Vendido a ${precio_actual:.8f}\nGanancia asegurada.\n💰 Saldo actual: ${obtener_saldo():.2f}")
                                enviar_mensaje(f"Trade PROFIT ✅\nProfit Diario: ${profit_total:.2f}")
                                operacion_abierta = False
                            elif precio_actual <= precio_stop:
                                perdida = saldo_actual * 0.02
                                profit_total -= perdida
                                enviar_mensaje(f"❌ ¡Stop Loss ejecutado! Vendido a ${precio_actual:.8f}\nPérdida registrada.\n💰 Saldo actual: ${obtener_saldo():.2f}")
                                enviar_mensaje(f"Trade LOSS ❌\nProfit Diario: ${profit_total:.2f}")
                                operacion_abierta = False
                        time.sleep(5)
            else:
                print("Saldo insuficiente para operar.")
        time.sleep(10)

if __name__ == '__main__':
    import threading
    threading.Thread(target=bot_loop).start()
    app.run(host='0.0.0.0', port=10000)
