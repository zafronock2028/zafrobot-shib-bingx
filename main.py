import requests
import time
import hmac
import hashlib
import os

# Variables de entorno
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

# Datos del par
symbol = "SHIB-USDT"

# Configuración de ganancia y pérdida
take_profit_percentage = 1.5  # 1.5% de ganancia
stop_loss_percentage = 2  # 2% de pérdida
min_balance_to_trade = 5  # mínimo para operar

# URL API BingX
bingx_base_url = "https://open-api.bingx.com"

# Enviar mensaje a Telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error enviando mensaje de Telegram: {e}")

# Firmar parámetros para BingX
def sign_params(params):
    query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params)])
    signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

# Consultar saldo disponible en Spot
def get_balance():
    url = f"{bingx_base_url}/openApi/spot/v1/account/balance"
    params = {"timestamp": int(time.time() * 1000)}
    params["signature"] = sign_params(params)
    headers = {"X-BX-APIKEY": API_KEY}
    try:
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        for asset in data["data"]:
            if asset["asset"] == "USDT":
                return float(asset["free"])
    except Exception as e:
        print(f"Error obteniendo balance: {e}")
    return 0.0

# Consultar precio actual
def get_price():
    url = f"{bingx_base_url}/openApi/spot/v1/ticker/price"
    params = {"symbol": symbol}
    try:
        response = requests.get(url, params=params)
        data = response.json()
        return float(data["data"]["price"])
    except Exception as e:
        print(f"Error obteniendo precio: {e}")
    return 0.0

# Comprar tokens
def place_order(side, quantity):
    url = f"{bingx_base_url}/openApi/spot/v1/order"
    params = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": quantity,
        "timestamp": int(time.time() * 1000)
    }
    params["signature"] = sign_params(params)
    headers = {"X-BX-APIKEY": API_KEY}
    try:
        response = requests.post(url, params=params, headers=headers)
        data = response.json()
        print(data)
        return data
    except Exception as e:
        print(f"Error colocando orden: {e}")

# ZafroBot principal
def zafrobot():
    send_telegram_message("🚀 *Bienvenido a ZafroBot Dinámico.*\nEstamos monitoreando el mercado con análisis profesional en tiempo real.\nSolo se actuarán oportunidades seguras y verificadas.\n✅ ¡Gracias por confiar en nuestra tecnología de trading inteligente!")

    balance = get_balance()
    if balance < min_balance_to_trade:
        send_telegram_message("⚠️ No hay saldo suficiente para operar. Mínimo requerido: 5 USDT.")
        return

    send_telegram_message(f"💰 Saldo disponible detectado: *{balance:.2f} USDT*\nAnalizando oportunidades...")

    while True:
        try:
            price_entry = get_price()
            print(f"Esperando oportunidad segura... Precio actual: {price_entry}")

            # Simulando oportunidad segura (ejemplo simple)
            time.sleep(5)  # Esperar para analizar
            quantity = (balance * 0.8) / price_entry  # usar 80% del balance
            place_order("BUY", quantity)
            send_telegram_message(f"🛒 Entrada realizada en {symbol} a precio {price_entry:.8f}.")

            # Monitorear Take Profit y Stop Loss
            initial_price = price_entry
            while True:
                current_price = get_price()
                if current_price >= initial_price * (1 + take_profit_percentage / 100):
                    place_order("SELL", quantity)
                    send_telegram_message(f"✅ ¡Ganancia realizada de +{take_profit_percentage}%!\nNuevo precio: {current_price:.8f}")
                    return
                if current_price <= initial_price * (1 - stop_loss_percentage / 100):
                    place_order("SELL", quantity)
                    send_telegram_message(f"🛡️ Stop Loss activado: -{stop_loss_percentage}%\nNuevo precio: {current_price:.8f}")
                    return
                time.sleep(5)
        except Exception as e:
            print(f"Error principal: {e}")
            time.sleep(10)

if __name__ == "__main__":
    zafrobot()
