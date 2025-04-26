import os
import time
import hmac
import hashlib
import requests
import threading
import datetime
from flask import Flask
from telegram import Bot

# Variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Configuración
PAIR = "SHIB-USDT"
BASE_URL = "https://open-api.bingx.com"
bot = Bot(token=TELEGRAM_BOT_TOKEN)
app = Flask(__name__)

# Estado del bot
operacion_abierta = False
precio_compra = 0
contador_operaciones = 0
ganancia_total = 0.0

def firmar_parametros(params):
    query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params)])
    signature = hmac.new(SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

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
        response = requests.get(f"{BASE_URL}/openApi/wallet/balance", headers=headers, params=params)
        data = response.json()
        for balance in data['data']['balance']:
            if balance['asset'] == 'USDT':
                return float(balance['available'])
    except Exception as e:
        print(f"Error obteniendo balance: {e}")
    return None

def obtener_precio():
    try:
        response = requests.get(f"{BASE_URL}/openApi/spot/v1/ticker/price?symbol={PAIR.replace('-', '')}")
        data = response.json()
        return float(data['data']['price'])
    except Exception as e:
        print(f"Error obteniendo precio: {e}")
    return None

def enviar_mensaje(texto):
    try:
        bot.send_message(chat_id=CHAT_ID, text=texto)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

def comprar():
    global operacion_abierta, precio_compra
    saldo = obtener_saldo()
    if saldo is None:
        enviar_mensaje("⚠️ Bot iniciado, pero no se pudo obtener el saldo.")
        return
    usdt_disponible = saldo * 0.8
    precio_actual = obtener_precio()
    if precio_actual:
        cantidad = usdt_disponible / precio_actual
        operacion_abierta = True
        precio_compra = precio_actual
        enviar_mensaje(f"✅ ¡Compra realizada!\n\nComprado a ${precio_actual:.8f}\nCantidad: {cantidad:.0f} {PAIR.split('-')[0]}")

def vender(precio_actual, ganancia):
    global operacion_abierta, precio_compra, contador_operaciones, ganancia_total
    operacion_abierta = False
    contador_operaciones += 1
    ganancia_total += ganancia
    if ganancia >= 0:
        enviar_mensaje(f"✅ ¡Operación cerrada! Vendido a ${precio_actual:.8f}.\nGanancia: +${ganancia:.2f} ✅\n\n💰Saldo actualizado: {obtener_saldo():.2f} USDT")
    else:
        enviar_mensaje(f"❌ ¡Operación cerrada con pérdida! Vendido a ${precio_actual:.8f}.\nPérdida: -${abs(ganancia):.2f} ❌\n\n💰Saldo actualizado: {obtener_saldo():.2f} USDT")

def evaluar_operacion():
    global operacion_abierta, precio_compra
    while True:
        if not operacion_abierta:
            comprar()
        else:
            precio_actual = obtener_precio()
            if precio_actual:
                cambio = (precio_actual - precio_compra) / precio_compra
                if cambio >= 0.015:  # +1.5%
                    saldo = obtener_saldo()
                    vender(precio_actual, saldo * 0.015)
                elif cambio <= -0.02:  # -2%
                    saldo = obtener_saldo()
                    vender(precio_actual, saldo * -0.02)
        time.sleep(5)

def resumen_diario():
    global contador_operaciones, ganancia_total
    while True:
        ahora = datetime.datetime.now()
        segundos_hasta_medianoche = (86400 - (ahora.hour * 3600 + ahora.minute * 60 + ahora.second))
        time.sleep(segundos_hasta_medianoche)
        enviar_mensaje(f"🧾 Resumen del día:\n\nTrades cerrados: {contador_operaciones}\nGanancia total: ${ganancia_total:.2f} USDT")
        contador_operaciones = 0
        ganancia_total = 0.0

@app.route('/')
def home():
    return "ZafroBot Dinámico Pro está activo."

if __name__ == "__main__":
    # Enviar mensaje inicial de saldo
    saldo_inicial = obtener_saldo()
    if saldo_inicial:
        enviar_mensaje(f"✅ ZafroBot Iniciado\n\n💵 Saldo disponible: ${saldo_inicial:.2f} USDT\n\n⚡ ¡Listo para operar!")
    else:
        enviar_mensaje("⚠️ Bot iniciado, pero no se pudo obtener el saldo.")

    threading.Thread(target=evaluar_operacion).start()
    threading.Thread(target=resumen_diario).start()
    app.run(host='0.0.0.0', port=10000)
