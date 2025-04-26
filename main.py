import os
import time
import requests
import hmac
import hashlib

# ENV VARS
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
CHAT_ID = os.getenv("CHAT_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

BINGX_API_URL = "https://open-api.bingx.com/openApi/swap/v2"

SYMBOL = "SHIB-USDT"
TRADE_AMOUNT_PERCENTAGE = 0.8
TAKE_PROFIT_PERCENT = 0.015
STOP_LOSS_PERCENT = 0.02

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    requests.post(url, data=payload)

def get_server_time():
    return str(int(time.time() * 1000))

def sign_request(params):
    query = "&".join([f"{key}={params[key]}" for key in sorted(params)])
    signature = hmac.new(SECRET_KEY.encode(), query.encode(), hashlib.sha256).hexdigest()
    return signature

def get_balance():
    endpoint = f"{BINGX_API_URL}/user/balance"
    timestamp = get_server_time()
    params = {
        "apiKey": API_KEY,
        "timestamp": timestamp
    }
    params["signature"] = sign_request(params)
    response = requests.get(endpoint, params=params)
    balance = float(response.json()["data"]["USDT"]["availableBalance"])
    return balance

def get_price():
    endpoint = f"{BINGX_API_URL}/quote/price"
    response = requests.get(endpoint, params={"symbol": SYMBOL})
    return float(response.json()["price"])

def place_order(side, quantity):
    endpoint = f"{BINGX_API_URL}/trade/order"
    timestamp = get_server_time()
    params = {
        "apiKey": API_KEY,
        "symbol": SYMBOL,
        "side": side,
        "positionSide": "LONG" if side == "BUY" else "SHORT",
        "type": "MARKET",
        "quantity": quantity,
        "timestamp": timestamp
    }
    params["signature"] = sign_request(params)
    response = requests.post(endpoint, data=params)
    return response.json()

def main():
    balance = get_balance()
    investment = balance * TRADE_AMOUNT_PERCENTAGE
    entry_price = get_price()
    quantity = investment / entry_price

    send_telegram_message("Buscando entrada ideal para scalping en SHIB/USDT...")

    while True:
        price = get_price()

        if price >= entry_price * (1 + TAKE_PROFIT_PERCENT):
            send_telegram_message(f"Ganancia detectada: Vendiendo con +1.5%. Precio: {price}")
            place_order("SELL", quantity)
            break
        elif price <= entry_price * (1 - STOP_LOSS_PERCENT):
            send_telegram_message(f"Pérdida controlada: Stop Loss activado. Precio: {price}")
            place_order("SELL", quantity)
            break

        time.sleep(3)

if __name__ == "__main__":
    main()
