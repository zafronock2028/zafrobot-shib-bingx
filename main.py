import os
import time
import requests
import hmac
import hashlib
from flask import Flask

app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
BASE_URL = "https://open-api.bingx.com"

PAR = "SHIB-USDT"
TAKE_PROFIT = 0.01     # +1%
STOP_LOSS = -0.02      # -2%
PORCENTAJE_OPERAR = 0.80  # 80% del saldo
INTERVALO_VERIFICACION = 10  # en segundos

saldo_total_ganado = 0
numero_operaciones = 0

def firmar(query_string):
    return hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()

def obtener_saldo_usdt():
    timestamp = str(int(time.time() * 1000))
    query = f"timestamp={timestamp}"
    firma = firmar(query)
    url = f"{BASE_URL}/openApi/user/balance?{query}&signature={firma}"
    headers = {"X-BX-APIKEY": API_KEY}
    res = requests.get(url, headers=headers).json()
    return float(res['data']['balance']['available'])

def obtener_precio_actual():
    url = f"{BASE_URL}/openApi/quote/latestPrice?symbol={PAR}"
    res = requests.get(url).json()
    return float(res['data']['price'])

def colocar_orden_lado(lado, cantidad):
    timestamp = str(int(time.time() * 1000))
    query = f"symbol={PAR}&side={lado}&type=MARKET&quantity={cantidad}&timestamp={timestamp}"
    firma = firmar(query)
    url = f"{BASE_URL}/openApi/spot/v1/trade/order?{query}&signature={firma}"
    headers = {"X-BX-APIKEY": API_KEY, "Content-Type": "application/x-www-form-urlencoded"}
    res = requests.post(url, headers=headers).json()
    return res

def ejecutar_bot():
    global saldo_total_ganado, numero_operaciones

    while True:
        try:
            saldo = obtener_saldo_usdt()
            saldo_operar = saldo * PORCENTAJE_OPERAR
            precio_entrada = obtener_precio_actual()
            cantidad_shib = saldo_operar / precio_entrada

            print(f"Comprando SHIB con ${saldo_operar:.2f}")
            colocar_orden_lado("BUY", round(cantidad_shib, 2))

            while True:
                precio_actual = obtener_precio_actual()
                variacion = (precio_actual - precio_entrada) / precio_entrada

                if variacion >= TAKE_PROFIT:
                    colocar_orden_lado("SELL", round(cantidad_shib, 2))
                    ganancia = cantidad_shib * (precio_actual - precio_entrada)
                    saldo_total_ganado += ganancia
                    numero_operaciones += 1
                    print(f"[+] Venta con ganancia: +${ganancia:.2f}")
                    break

                elif variacion <= STOP_LOSS:
                    colocar_orden_lado("SELL", round(cantidad_shib, 2))
                    perdida = cantidad_shib * (precio_actual - precio_entrada)
                    saldo_total_ganado += perdida
                    numero_operaciones += 1
                    print(f"[-] Venta con pérdida: ${perdida:.2f}")
                    break

                time.sleep(INTERVALO_VERIFICACION)

        except Exception as e:
            print(f"Error: {str(e)}")
            time.sleep(15)

@app.route('/')
def estado():
    return f"Zafrobot Dinámico activo. Operaciones: {numero_operaciones}, Ganancia total: ${saldo_total_ganado:.2f}"

if __name__ == '__main__':
    ejecutar_bot()
