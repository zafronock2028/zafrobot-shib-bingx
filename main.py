import requests
import time
import hmac
import hashlib
import os
import json

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Par a operar
SYMBOL = "SHIB-USDT"

# Parámetros de operación
PORCENTAJE_ENTRADA = 0.80  # 80%
OBJETIVO_GANANCIA = 1.02   # 2% arriba
STOP_LOSS = 0.98            # 2% abajo

def enviar_mensaje(texto):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def obtener_saldo_usdt():
    url = "https://open-api.bingx.com/openApi/user/balance"
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-BX-APIKEY": API_KEY
    }
    params = {
        "timestamp": timestamp,
        "signature": signature
    }
    response = requests.get(url, headers=headers, params=params)
    result = response.json()

    if "data" not in result or "balances" not in result["data"]:
        print("Error al obtener saldo:", result)
        return None
    
    for asset in result["data"]["balances"]:
        if asset["asset"] == "USDT":
            return float(asset["free"])
    
    return None

def obtener_precio_actual():
    url = f"https://api.bingx.com/openApi/spot/market/getLatestPrice?symbol={SYMBOL}"
    response = requests.get(url)
    result = response.json()

    if "data" in result and isinstance(result["data"], list) and len(result["data"]) > 0:
        return float(result["data"][0]["price"])
    else:
        print("Error al obtener precio:", result)
        return None

def comprar_shib(cantidad_shib, precio_actual):
    print(f"Simulando compra de {cantidad_shib} SHIB a precio {precio_actual}")
    return True

def vender_shib(cantidad_shib, precio_actual):
    print(f"Simulando venta de {cantidad_shib} SHIB a precio {precio_actual}")
    return True

def zafrobot_dinamico_pro():
    print("\n=== ZafroBot Dinámico Pro Iniciado ===")

    saldo = obtener_saldo_usdt()
    if saldo is None or saldo < 1:
        print("Saldo insuficiente para operar.")
        enviar_mensaje("⚠️ *Saldo insuficiente para operar.*")
        return
    
    saldo_operar = saldo * PORCENTAJE_ENTRADA
    precio_inicio = obtener_precio_actual()
    if precio_inicio is None:
        return
    
    cantidad_shib = saldo_operar / precio_inicio
    comprar_shib(cantidad_shib, precio_inicio)

    precio_take_profit = precio_inicio * OBJETIVO_GANANCIA
    precio_stop_loss = precio_inicio * STOP_LOSS

    while True:
        precio_actual = obtener_precio_actual()
        if precio_actual is None:
            time.sleep(10)
            continue
        
        if precio_actual >= precio_take_profit:
            vender_shib(cantidad_shib, precio_actual)
            ganancia = (precio_actual / precio_inicio - 1) * 100
            enviar_mensaje(f"✅ *¡Operación ganada!* +{ganancia:.2f}%\n\n_Saldo operativo creciendo cada día._\n\nÚnete: [Canal Oficial](https://t.me/GanandoConZafronock)")
            break
        
        if precio_actual <= precio_stop_loss:
            vender_shib(cantidad_shib, precio_actual)
            enviar_mensaje(f"⚠️ *Stop Loss activado.*\n\nProtegimos tu saldo para seguir operando.")
            break

        time.sleep(10)

if __name__ == "__main__":
    zafrobot_dinamico_pro()
