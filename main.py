import os
import time
import requests
import hmac
import hashlib
import json

# Variables de entorno (Render)
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

# Configuración
PAIR = 'SHIB_USDT'
SPOT_URL = 'https://open-api.bingx.com/openApi/spot/v1'
HEADERS = {'X-BX-APIKEY': API_KEY}
TAKE_PROFIT = 1.015  # 1.5% arriba
STOP_LOSS = 0.98     # 2% abajo
PERCENTAGE_TO_USE = 0.8  # 80% del saldo disponible
CHECK_INTERVAL = 10  # segundos

# Función para enviar mensaje a Telegram
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Error enviando Telegram: {e}")

# Función para firmar solicitudes
def sign_request(params):
    query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params)])
    signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

# Obtener saldo disponible en USDT
def get_balance():
    timestamp = str(int(time.time() * 1000))
    params = {'timestamp': timestamp}
    params['signature'] = sign_request(params)
    response = requests.get(f"{SPOT_URL}/account/balance", headers=HEADERS, params=params)
    balances = response.json()
    if balances['code'] == 0:
        for asset in balances['data']['balances']:
            if asset['asset'] == 'USDT':
                return float(asset['free'])
    return 0

# Obtener precio actual de SHIB
def get_price():
    response = requests.get(f"https://open-api.bingx.com/openApi/spot/v1/ticker/price?symbol={PAIR}")
    price_info = response.json()
    if price_info['code'] == 0:
        return float(price_info['data']['price'])
    return None

# Crear orden spot market
def create_order(side, quantity):
    timestamp = str(int(time.time() * 1000))
    params = {
        'symbol': PAIR,
        'side': side,
        'type': 'MARKET',
        'quantity': quantity,
        'timestamp': timestamp
    }
    params['signature'] = sign_request(params)
    response = requests.post(f"{SPOT_URL}/order", headers=HEADERS, params=params)
    return response.json()

# Análisis profesional simple para oportunidad
def detect_opportunity(current_price):
    # Placeholder sencillo: podríamos agregar análisis real más avanzado aquí
    return True  # Simula siempre oportunidad (podemos sofisticarlo después)

# BOT principal
def main():
    while True:
        try:
            balance = get_balance()
            if balance <= 0:
                print("Sin saldo suficiente, esperando...")
                time.sleep(60)
                continue

            usdt_to_use = balance * PERCENTAGE_TO_USE
            current_price = get_price()
            if current_price is None:
                print("No se pudo obtener precio actual, reintentando...")
                time.sleep(30)
                continue

            if detect_opportunity(current_price):
                send_telegram("🚀 ¡Oportunidad detectada! Entrada probable segura en SHIB/USDT. Analizando ejecución...")

                quantity = round(usdt_to_use / current_price, 0)  # Ajusta según cantidad permitida
                order = create_order('BUY', quantity)
                if order.get('code') == 0:
                    entry_price = current_price
                    send_telegram("✅ Compra ejecutada en Market. Monitoreando para salida con +1.5%...")

                    take_profit_price = round(entry_price * TAKE_PROFIT, 8)
                    stop_loss_price = round(entry_price * STOP_LOSS, 8)

                    while True:
                        price = get_price()
                        if price is None:
                            continue

                        if price >= take_profit_price:
                            create_order('SELL', quantity)
                            send_telegram("🎯 Venta ejecutada en ganancia +1.5%. ¡Ganancia asegurada!")
                            break

                        if price <= stop_loss_price:
                            create_order('SELL', quantity)
                            send_telegram("⚠️ Stop Loss ejecutado. Pérdida controlada.")
                            break

                        time.sleep(CHECK_INTERVAL)

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print(f"Error general: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
