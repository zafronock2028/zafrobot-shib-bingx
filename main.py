import requests
import time
import hashlib
import hmac

# === CONFIGURACIÓN ===

API_KEY = "LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA"
SECRET_KEY = "Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg"
SYMBOL = "SHIB-USDT"

TELEGRAM_BOT_TOKEN = "7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM"
TELEGRAM_CHAT_ID = "291650"

# === FUNCIONES AUXILIARES ===

def enviar_mensaje_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=data)

def obtener_saldo_usdt():
    url = "https://open-api.bingx.com/openApi/user/balance"
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    headers = {"X-BX-APIKEY": API_KEY}
    params = {"timestamp": timestamp, "signature": signature}
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    try:
        for asset in data.get('data', {}).get('balances', []):
            if asset['asset'] == 'USDT':
                return float(asset['free'])
    except Exception as e:
        print("Error procesando el saldo:", e)
    return 0.0

def obtener_precio_actual():
    url = f"https://open-api.bingx.com/openApi/market/ticker?symbol={SYMBOL}"
    response = requests.get(url)
    data = response.json()
    return float(data['data'][0]['price'])

def realizar_orden(tipo, cantidad):
    url = "https://open-api.bingx.com/openApi/spot/v1/trade/order"
    timestamp = str(int(time.time() * 1000))
    body = {
        "symbol": SYMBOL,
        "side": "BUY" if tipo == "compra" else "SELL",
        "type": "MARKET",
        "quantity": cantidad,
        "timestamp": timestamp
    }
    query = '&'.join([f"{k}={v}" for k, v in body.items()])
    signature = hmac.new(SECRET_KEY.encode(), query.encode(), hashlib.sha256).hexdigest()
    body["signature"] = signature
    headers = {"X-BX-APIKEY": API_KEY}
    return requests.post(url, headers=headers, data=body).json()

# === BOT PRINCIPAL ===

def zafrobot_dinamico():
    print("=== ZafroBot Dinámico Iniciado ===")

    saldo = obtener_saldo_usdt()
    if saldo < 5:
        print("Saldo insuficiente para operar.")
        return

    capital = saldo * 0.80
    precio_inicio = obtener_precio_actual()
    cantidad_token = capital / precio_inicio

    print(f"Comprando {cantidad_token:.2f} de {SYMBOL} a precio {precio_inicio}")
    realizar_orden("compra", cantidad_token)

    while True:
        precio_actual = obtener_precio_actual()
        variacion = (precio_actual - precio_inicio) / precio_inicio * 100

        if variacion >= 1.08:
            realizar_orden("venta", cantidad_token)
            nuevo_saldo = obtener_saldo_usdt()
            mensaje = (
                "✅ *¡Operación ganada!*\n"
                "📈 *Ganancia:* +1.08%\n"
                f"💰 *Nuevo saldo:* ${nuevo_saldo:.2f}\n\n"
                "Únete al canal oficial:\n👉 https://t.me/GanandoConZafronock"
            )
            enviar_mensaje_telegram(mensaje)
            break

        elif variacion <= -2:
            realizar_orden("venta", cantidad_token)
            mensaje = (
                "⚠️ *¡Stop Loss activado!*\n"
                "📉 *Pérdida:* -2%\n"
                "Se protegió el capital automáticamente."
            )
            enviar_mensaje_telegram(mensaje)
            break

        time.sleep(10)

# === EJECUCIÓN ===

if __name__ == "__main__":
    zafrobot_dinamico()
