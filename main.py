import requests
import time
import hmac
import hashlib
import os
import json

# Variables de entorno (en Render)
API_KEY = os.getenv('BINGX_API_KEY')
SECRET_KEY = os.getenv('BINGX_SECRET_KEY')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Parámetros
PAR_TRADING = "SHIB-USDT"
PORCENTAJE_ENTRADA = 0.80
TAKE_PROFIT = 1.02  # 2% de ganancia
STOP_LOSS = 0.98    # 2% de pérdida

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")

def firmar(query_string, secret_key):
    return hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def obtener_saldo_usdt():
    url = "https://open-api.bingx.com/openApi/swap/v2/user/balance"
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = firmar(query_string, SECRET_KEY)
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    response = requests.get(f"{url}?{query_string}&signature={signature}", headers=headers)
    data = response.json()
    if data.get('code') != 0:
        print(f"Error al obtener saldo: {data}")
        return 0
    for asset in data['data']['balances']:
        if asset['asset'] == "USDT":
            return float(asset['balance'])
    return 0

def obtener_precio_actual():
    url = f"https://open-api.bingx.com/openApi/spot/v1/ticker/price?symbol={PAR_TRADING}"
    response = requests.get(url)
    data = response.json()
    return float(data['data']['price'])

def colocar_orden_compra(cantidad):
    url = "https://open-api.bingx.com/openApi/spot/v1/trade/order"
    timestamp = str(int(time.time() * 1000))
    body = {
        "symbol": PAR_TRADING,
        "side": "BUY",
        "type": "MARKET",
        "quantity": cantidad,
        "timestamp": timestamp
    }
    query_string = '&'.join([f"{key}={body[key]}" for key in body])
    signature = firmar(query_string, SECRET_KEY)
    headers = {
        "X-BX-APIKEY": API_KEY,
        "Content-Type": "application/json"
    }
    response = requests.post(f"{url}?signature={signature}", headers=headers, json=body)
    return response.json()

def colocar_orden_venta(cantidad):
    url = "https://open-api.bingx.com/openApi/spot/v1/trade/order"
    timestamp = str(int(time.time() * 1000))
    body = {
        "symbol": PAR_TRADING,
        "side": "SELL",
        "type": "MARKET",
        "quantity": cantidad,
        "timestamp": timestamp
    }
    query_string = '&'.join([f"{key}={body[key]}" for key in body])
    signature = firmar(query_string, SECRET_KEY)
    headers = {
        "X-BX-APIKEY": API_KEY,
        "Content-Type": "application/json"
    }
    response = requests.post(f"{url}?signature={signature}", headers=headers, json=body)
    return response.json()

def zafrobot_dinamico_pro():
    print("=== ZafroBot Dinámico Pro Iniciado ===")
    saldo = obtener_saldo_usdt()
    if saldo < 5:
        print("Saldo insuficiente para operar.")
        enviar_telegram("⚠️ *Saldo insuficiente para operar.*")
        return

    capital_uso = saldo * PORCENTAJE_ENTRADA
    precio_inicio = obtener_precio_actual()
    print(f"Precio inicial: {precio_inicio}")

    cantidad_token = capital_uso / precio_inicio
    colocar_orden_compra(cantidad_token)
    enviar_telegram(f"✅ *Compra realizada*\nPrecio: {precio_inicio}")

    while True:
        time.sleep(10)
        precio_actual = obtener_precio_actual()
        print(f"Precio actual: {precio_actual}")

        if precio_actual >= precio_inicio * TAKE_PROFIT:
            colocar_orden_venta(cantidad_token)
            nuevo_saldo = obtener_saldo_usdt()
            enviar_telegram(f"✨ *¡Operación ganada!*\nGanancia: +2%\nNuevo saldo: ${nuevo_saldo:.2f}\nÚnete al canal: https://t.me/GanandoConZafronock")
            break
        elif precio_actual <= precio_inicio * STOP_LOSS:
            colocar_orden_venta(cantidad_token)
            nuevo_saldo = obtener_saldo_usdt()
            enviar_telegram(f"⚡ *¡Stop Loss activado!*\nPérdida controlada\nNuevo saldo: ${nuevo_saldo:.2f}\nÚnete al canal: https://t.me/GanandoConZafronock")
            break

if __name__ == "__main__":
    zafrobot_dinamico_pro()
