import os
import time
import requests
import hmac
import hashlib
import json
import telegram
from flask import Flask

# Configuración
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

PAIR = "SHIB-USDT"
API_URL = "https://open-api.bingx.com"

bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

app = Flask(__name__)

# Variables globales
operacion_abierta = False
precio_compra = 0
ganancias_diarias = []
cantidad_compras = 0

# Funciones
def obtener_saldo():
    try:
        timestamp = str(int(time.time() * 1000))
        params = f"timestamp={timestamp}"
        signature = hmac.new(SECRET_KEY.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()

        headers = {
            "X-BX-APIKEY": API_KEY
        }

        response = requests.get(f"{API_URL}/openApi/swap/v2/user/balance?timestamp={timestamp}&signature={signature}", headers=headers)
        data = response.json()

        if data.get('code') == 0:
            for balance in data['data']:
                if balance['asset'] == 'USDT':
                    return float(balance['balance'])
        return None
    except Exception as e:
        print(f"Error al obtener saldo: {e}")
        return None

def enviar_mensaje(texto):
    bot.send_message(chat_id=CHAT_ID, text=texto)

def buscar_entrada():
    # Aquí deberías colocar tu estrategia de análisis técnico real
    return True  # Simulación de siempre encontrar oportunidad

def comprar():
    global operacion_abierta, precio_compra, cantidad_compras

    cantidad_compras += 1
    operacion_abierta = True
    precio_compra = obtener_precio_actual()
    enviar_mensaje(f"✅ Compra realizada en ${precio_compra:.8f}")

def vender(ganancia_perdida):
    global operacion_abierta, precio_compra, ganancias_diarias

    saldo_actual = obtener_saldo()

    if ganancia_perdida >= 0:
        enviar_mensaje(f"✅ ¡Operación cerrada! Vendido a ${obtener_precio_actual():.8f}. Ganancia asegurada.\n\n💰Saldo actual: ${saldo_actual:.2f}")
        ganancias_diarias.append(ganancia_perdida)
    else:
        enviar_mensaje(f"❌ Operación cerrada en pérdida: {ganancia_perdida:.2f} USD.\n\n💰Saldo actual: ${saldo_actual:.2f}")
        ganancias_diarias.append(ganancia_perdida)

    operacion_abierta = False
    precio_compra = 0

def obtener_precio_actual():
    # Aquí deberías hacer la consulta al precio actual en BingX
    # Por ahora simulado
    return 0.00002500  # Simulado

def calcular_ganancia_actual():
    precio_actual = obtener_precio_actual()
    return (precio_actual - precio_compra) * 100 / precio_compra

def resumen_diario():
    global ganancias_diarias
    if ganancias_diarias:
        resumen = "\n".join([
            f"Trade {i+1} {'PROFIT✅' if g > 0 else f'-${abs(g):.2f}❌'}"
            for i, g in enumerate(ganancias_diarias)
        ])
        total = sum(ganancias_diarias)
        enviar_mensaje(f"📊 Resumen diario:\n{resumen}\n\nGanancia total: ${total:.2f}")
        ganancias_diarias = []

# Bot principal
def bot_principal():
    saldo = obtener_saldo()

    if saldo is None:
        enviar_mensaje("⚠️ Bot iniciado, pero no se pudo obtener el saldo.")
    else:
        enviar_mensaje(f"✅ ZafroBot Iniciado\n------------------------\n💳 Saldo disponible: ${saldo:.2f} USDT\n------------------------\n⚡ ¡Listo para operar!")

    while True:
        if not operacion_abierta:
            if buscar_entrada():
                comprar()
        else:
            ganancia = calcular_ganancia_actual()
            if ganancia >= 1.5:
                vender(ganancia)
            elif ganancia <= -2:
                vender(ganancia)

        time.sleep(10)  # Esperar 10 segundos entre verificaciones

@app.route('/')
def home():
    return "ZafroBot Running"

if __name__ == '__main__':
    import threading
    threading.Thread(target=bot_principal).start()
    app.run(host='0.0.0.0', port=10000)
