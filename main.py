import os
from flask import Flask
import time
import requests

app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

# Configuración del bot
PAIR = "SHIB-USDT"
TAKE_PROFIT_PERCENT = 1.5
STOP_LOSS_PERCENT = 1.0
TRADE_PERCENT = 0.80

def ejecutar_operacion():
    saldo = obtener_saldo_disponible()
    if saldo <= 0:
        return "Saldo insuficiente"

    cantidad_a_usar = saldo * TRADE_PERCENT
    precio_compra = obtener_precio_actual()

    comprar_token(cantidad_a_usar, precio_compra)

    precio_take_profit = precio_compra * (1 + TAKE_PROFIT_PERCENT / 100)
    precio_stop_loss = precio_compra * (1 - STOP_LOSS_PERCENT / 100)

    while True:
        precio_actual = obtener_precio_actual()

        if precio_actual >= precio_take_profit:
            vender_token()
            break

        if precio_actual <= precio_stop_loss:
            vender_token()
            break

        time.sleep(5)

def obtener_saldo_disponible():
    # Aquí iría la llamada real a la API de BingX
    return 100  # Modo demostración

def obtener_precio_actual():
    # Aquí iría la consulta al precio actual en BingX
    return 0.000023  # Modo demostración

def comprar_token(monto, precio):
    print(f"Comprando SHIB por {monto} USDT a {precio}")

def vender_token():
    print("Vendiendo SHIB")

@app.route('/')
def index():
    return 'Zafrobot SHIB BingX activo.'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
