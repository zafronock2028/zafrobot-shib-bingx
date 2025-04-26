import os
import time
import hmac
import hashlib
import requests

# Variables de entorno
BINGX_API_KEY = os.getenv("BINGX_API_KEY")
BINGX_SECRET_KEY = os.getenv("BINGX_SECRET_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Configuración
PAIR = "SHIB-USDT"
TAKE_PROFIT_PERCENT = 1.5  # % de ganancia
STOP_LOSS_PERCENT = 2.0    # % de pérdida
CHECK_INTERVAL = 10        # Intervalo entre chequeos en segundos

# URLs de la API
BASE_URL = "https://open-api.bingx.com"

# Función para firmar las peticiones
def sign(params, secret_key):
    query_string = "&".join([f"{key}={params[key]}" for key in sorted(params)])
    return hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

# Función para enviar mensajes a Telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Error enviando mensaje Telegram: {e}")

# Función para obtener el saldo en USDT
def get_balance():
    timestamp = str(int(time.time() * 1000))
    params = {
        "timestamp": timestamp
    }
    signature = sign(params, BINGX_SECRET_KEY)
    headers = {
        "X-BX-APIKEY": BINGX_API_KEY
    }
    response = requests.get(f"{BASE_URL}/openApi/spot/v1/account/balance?timestamp={timestamp}&signature={signature}", headers=headers)
    data = response.json()
    for asset in data['data']['balances']:
        if asset['asset'] == 'USDT':
            return float(asset['free'])
    return 0.0

# Función para obtener el precio actual de SHIB/USDT
def get_current_price():
    response = requests.get(f"{BASE_URL}/openApi/spot/v1/ticker/price?symbol={PAIR}")
    data = response.json()
    return float(data['data']['price'])

# Función simulada de análisis seguro (por ahora 80% chance)
def analizar_entrada_segura(current_price):
    import random
    return random.random() < 0.8

# Función principal
def main():
    send_telegram_message("🚀 *ZafroBot Dinámico Pro (BingX) iniciado exitosamente!*")
    saldo = get_balance()
    send_telegram_message(f"💰 *Saldo detectado:* ${saldo:.2f} *USDT*")

    while True:
        try:
            saldo = get_balance()
            if saldo < 1:
                send_telegram_message("⚠️ *Saldo insuficiente para operar.*")
                time.sleep(60)
                continue

            current_price = get_current_price()

            if analizar_entrada_segura(current_price):
                usdt_para_compra = saldo * 0.8
                cantidad_shib = usdt_para_compra / current_price

                send_telegram_message(f"🛒 *Oportunidad detectada. Preparando compra de SHIB!* Precio actual: ${current_price:.8f}")

                precio_compra = current_price
                objetivo_take_profit = precio_compra * (1 + TAKE_PROFIT_PERCENT / 100)
                objetivo_stop_loss = precio_compra * (1 - STOP_LOSS_PERCENT / 100)

                while True:
                    precio_actual = get_current_price()

                    if precio_actual >= objetivo_take_profit:
                        send_telegram_message(f"✅ *¡Ganancia alcanzada! Precio actual:* ${precio_actual:.8f} (+{TAKE_PROFIT_PERCENT}%)")
                        break

                    if precio_actual <= objetivo_stop_loss:
                        send_telegram_message(f"🛑 *¡Stop Loss activado! Precio actual:* ${precio_actual:.8f} (-{STOP_LOSS_PERCENT}%)")
                        break

                    time.sleep(5)

            else:
                print("Esperando oportunidad segura...")

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            send_telegram_message(f"⚠️ *Error en ejecución:* {e}")
            time.sleep(60)

# Ejecutar
if __name__ == "__main__":
    main()
