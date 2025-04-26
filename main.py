import requests
import time
import hashlib
import hmac
import os

# Claves desde variables de entorno en Render
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

SYMBOL = "SHIB-USDT"
PRECISION = 6  # Número de decimales para SHIB
MONEDA_OBJETIVO = "USDT"

# === Función para enviar notificación a Telegram ===
def notificar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload)
    except:
        print("Error al enviar notificación Telegram")

# === Firma de solicitudes HMAC ===
def firmar(query_string, secret_key):
    return hmac.new(
        secret_key.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

# === Obtener saldo disponible USDT ===
def obtener_saldo_usdt():
    url = "https://open-api.bingx.com/openApi/user/balance"
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = firmar(query_string, SECRET_KEY)

    headers = {
        "X-BX-APIKEY": API_KEY
    }

    params = {
        "timestamp": timestamp,
        "signature": signature
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        for asset in data['data']['balances']:
            if asset['asset'] == MONEDA_OBJETIVO:
                return float(asset['free'])
    except Exception as e:
        print("Error al obtener saldo:", e)

    return 0.0

# === Obtener precio actual de SHIB ===
def obtener_precio_actual():
    url = f"https://open-api.bingx.com/openApi/market/ticker?symbol={SYMBOL}"
    try:
        response = requests.get(url)
        return float(response.json()['data'][0]['price'])
    except Exception as e:
        print("Error al obtener precio:", e)
        return 0.0

# === Crear orden de compra ===
def crear_orden_compra(cantidad, precio):
    url = "https://open-api.bingx.com/openApi/spot/v1/trade/order"
    timestamp = str(int(time.time() * 1000))

    body = {
        "symbol": SYMBOL,
        "side": "BUY",
        "type": "LIMIT",
        "price": round(precio, PRECISION),
        "quantity": cantidad,
        "timestamp": timestamp
    }

    query_string = '&'.join([f"{k}={body[k]}" for k in body])
    signature = firmar(query_string, SECRET_KEY)

    headers = {
        "X-BX-APIKEY": API_KEY
    }

    body["signature"] = signature
    try:
        response = requests.post(url, headers=headers, data=body)
        print("Orden de compra enviada:", response.json())
        return True
    except Exception as e:
        print("Error al crear orden:", e)
        return False

# === Crear orden de venta ===
def crear_orden_venta(cantidad, precio):
    url = "https://open-api.bingx.com/openApi/spot/v1/trade/order"
    timestamp = str(int(time.time() * 1000))

    body = {
        "symbol": SYMBOL,
        "side": "SELL",
        "type": "LIMIT",
        "price": round(precio, PRECISION),
        "quantity": cantidad,
        "timestamp": timestamp
    }

    query_string = '&'.join([f"{k}={body[k]}" for k in body])
    signature = firmar(query_string, SECRET_KEY)

    headers = {
        "X-BX-APIKEY": API_KEY
    }

    body["signature"] = signature
    try:
        response = requests.post(url, headers=headers, data=body)
        print("Orden de venta enviada:", response.json())
        return True
    except Exception as e:
        print("Error al vender:", e)
        return False

# === BOT DINÁMICO PRO ===
def zafrobot_dinamico_pro():
    print("=== ZafroBot Dinámico Pro Iniciado ===")

    saldo = obtener_saldo_usdt()
    if saldo < 3:
        print("Saldo insuficiente para operar.")
        notificar_telegram("⚠️ *Saldo insuficiente para operar.*")
        return

    capital = saldo * 0.80
    precio_entrada = obtener_precio_actual()

    if precio_entrada == 0:
        print("No se pudo obtener el precio.")
        return

    cantidad = round(capital / precio_entrada, PRECISION)
    crear_orden_compra(cantidad, precio_entrada)
    notificar_telegram(f"🟢 *Compra ejecutada en SHIB*\nCantidad: `{cantidad}`\nPrecio: `{precio_entrada}`")

    take_profit = precio_entrada * 1.02
    stop_loss = precio_entrada * 0.97

    while True:
        precio_actual = obtener_precio_actual()
        if precio_actual >= take_profit:
            crear_orden_venta(cantidad, precio_actual)
            ganancia = capital * 0.02
            saldo_final = saldo + ganancia
            notificar_telegram(f"✅ *Ganancia tomada:* +2%\nNuevo saldo: `${saldo_final:.2f}`\nÚnete al canal: https://t.me/GanandoConZafronock")
            break
        elif precio_actual <= stop_loss:
            crear_orden_venta(cantidad, precio_actual)
            notificar_telegram("❌ *Stop Loss activado, operación cerrada para proteger capital*")
            break
        time.sleep(10)

# === EJECUCIÓN PRINCIPAL ===
if __name__ == "__main__":
    zafrobot_dinamico_pro()
