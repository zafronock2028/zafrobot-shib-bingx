import os
import time
import requests
from binance.client import Client
from binance.exceptions import BinanceAPIException

# === Configuración de entorno ===
api_key = os.getenv('API_KEY')
api_secret = os.getenv('SECRET_KEY')
telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
telegram_chat_id = os.getenv('CHAT_ID')

client = Client(api_key, api_secret)
symbol = 'SHIBUSDT'
profit_target = 0.015  # 1.5%
stop_loss_threshold = 0.02  # 2% pérdida
percent_to_use = 0.80  # Usa el 80% del USDT disponible

# === Enviar mensaje por Telegram ===
def notify(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    data = {'chat_id': telegram_chat_id, 'text': message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Error al enviar notificación: {e}")

# === Obtener saldo disponible ===
def get_usdt_balance():
    try:
        balance = client.get_asset_balance(asset='USDT')
        return float(balance['free']) if balance else 0
    except:
        notify("Error al obtener saldo.")
        return 0

# === Obtener datos de análisis ===
def get_market_data():
    try:
        candles = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE, limit=10)
        closes = [float(x[4]) for x in candles]
        return closes
    except Exception as e:
        print(f"Error al obtener datos: {e}")
        return []

# === Detectar entrada ideal usando análisis básico ===
def should_enter_trade(closes):
    if len(closes) < 3:
        return False
    return closes[-1] > closes[-2] > closes[-3]  # Tendencia de 3 velas verdes

# === Ejecutar operación ===
def execute_trade():
    usdt_balance = get_usdt_balance()
    if usdt_balance < 1:
        notify("Saldo insuficiente.")
        return

    closes = get_market_data()
    if not should_enter_trade(closes):
        print("No hay oportunidad clara.")
        return

    price = float(client.get_symbol_ticker(symbol=symbol)['price'])
    quantity = (usdt_balance * percent_to_use) / price
    quantity = round(quantity, 0)  # SHIB permite enteros

    try:
        buy_order = client.order_market_buy(symbol=symbol, quantity=quantity)
        buy_price = float(buy_order['fills'][0]['price'])
        notify(f"Compra ejecutada de {quantity} SHIB a {buy_price} USDT")
        print("Esperando ganancia...")

        while True:
            current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
            change = (current_price - buy_price) / buy_price

            if change >= profit_target:
                sell_order = client.order_market_sell(symbol=symbol, quantity=quantity)
                sell_price = float(sell_order['fills'][0]['price'])
                notify(f"Venta ejecutada con ganancia a {sell_price} USDT")
                break
            elif change <= -stop_loss_threshold:
                client.order_market_sell(symbol=symbol, quantity=quantity)
                notify("Venta ejecutada por stop loss.")
                break

            time.sleep(5)
    except BinanceAPIException as e:
        notify(f"Error en la operación: {e.message}")

# === Bucle infinito de scalping ===
notify("ZafroBot Pro con análisis experto iniciado.")
while True:
    execute_trade()
    time.sleep(60)
