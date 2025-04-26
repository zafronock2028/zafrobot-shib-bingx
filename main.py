import requests
import time
import hmac
import hashlib
import json
import os

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Funciones
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def sign(params, secret_key):
    query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params)])
    return hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def get_balance():
    url = "https://open-api.bingx.com/openApi/swap/v2/user/balance"
    timestamp = str(int(time.time() * 1000))
    params = {
        "timestamp": timestamp
    }
    signature = sign(params, SECRET_KEY)
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    params["signature"] = signature
    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    if "data" in data and "balanceList" in data["data"]:
        for asset in data["data"]["balanceList"]:
            if asset["asset"] == "USDT":
                return float(asset["availableBalance"])
    return 0.0

def place_order(side, quantity):
    url = "https://open-api.bingx.com/openApi/spot/v1/trade/order"
    timestamp = str(int(time.time() * 1000))
    params = {
        "symbol": "SHIB-USDT",
        "side": side,
        "type": "MARKET",
        "quantity": quantity,
        "timestamp": timestamp
    }
    signature = sign(params, SECRET_KEY)
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    params["signature"] = signature
    response = requests.post(url, headers=headers, data=params)
    return response.json()

def get_price():
    url = "https://open-api.bingx.com/openApi/spot/v1/market/ticker"
    params = {"symbol": "SHIB-USDT"}
    response = requests.get(url, params=params)
    data = response.json()
    if "data" in data and "price" in data["data"]:
        return float(data["data"]["price"])
    return None

# Inicio
send_telegram_message("🚀 *ZafroBot Dinámico Pro* ha iniciado. Detectando saldo disponible...")

# Ciclo principal
while True:
    try:
        balance = get_balance()
        if balance > 5:
            send_telegram_message(f"💰 Saldo disponible detectado: *{balance:.2f} USDT*")
            quantity_to_buy = balance * 0.8  # Usa el 80% del saldo
            entry_price = get_price()

            if entry_price:
                send_telegram_message("🔎 Analizando oportunidad de entrada...")

                # Simulación simple de análisis: esperar una buena condición (puedes expandir esta lógica)
                time.sleep(5)  # Pequeño tiempo de espera antes de comprar

                # Ejecutar compra
                buy_order = place_order("BUY", quantity_to_buy / entry_price)
                if buy_order.get("code") == 0:
                    send_telegram_message("✅ Compra ejecutada exitosamente. Monitoreando precio para vender...")

                    buy_price = entry_price
                    take_profit_price = buy_price * 1.015  # +1.5%
                    stop_loss_price = buy_price * 0.98    # -2%

                    while True:
                        current_price = get_price()
                        if current_price:
                            if current_price >= take_profit_price:
                                # Venta Take Profit
                                quantity_to_sell = quantity_to_buy / current_price
                                sell_order = place_order("SELL", quantity_to_sell)
                                if sell_order.get("code") == 0:
                                    send_telegram_message(f"🎯 ¡Venta exitosa con ganancia de +1.5%! Precio: *{current_price:.8f}*")
                                break
                            elif current_price <= stop_loss_price:
                                # Venta Stop Loss
                                quantity_to_sell = quantity_to_buy / current_price
                                sell_order = place_order("SELL", quantity_to_sell)
                                if sell_order.get("code") == 0:
                                    send_telegram_message(f"⚡ Venta ejecutada por stop loss. Precio: *{current_price:.8f}*")
                                break
                        time.sleep(5)
        else:
            send_telegram_message("⚠️ No hay suficiente saldo disponible para operar. Esperando...")
        time.sleep(60)

    except Exception as e:
        send_telegram_message(f"❌ Error detectado: {str(e)}")
        time.sleep(60)
