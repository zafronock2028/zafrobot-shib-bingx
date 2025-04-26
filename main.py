import os
import time
import requests
from binance.spot import Spot

# Variables de entorno
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Configuración
PAIR = "SHIBUSDT"
TAKE_PROFIT_PERCENT = 1.5  # Porcentaje de ganancia
STOP_LOSS_PERCENT = 2.0    # Porcentaje de pérdida
CHECK_INTERVAL = 10        # Segundos entre análisis

# Conexión con Binance Spot
client = Spot(key=API_KEY, secret=API_SECRET)

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

# Función para obtener el saldo USDT
def get_usdt_balance():
    account_info = client.account()
    for balance in account_info['balances']:
        if balance['asset'] == 'USDT':
            return float(balance['free'])
    return 0.0

# Función para obtener el precio actual de SHIB/USDT
def get_current_price():
    ticker = client.ticker_price(symbol=PAIR)
    return float(ticker['price'])

# Inicio del bot
send_telegram_message("🚀 *ZafroBot Dinámico Pro iniciado con éxito!*")
usdt_balance = get_usdt_balance()
send_telegram_message(f"💰 *Saldo detectado en Spot:* ${usdt_balance:.2f} *USDT*")

# Función principal de trading
def main():
    while True:
        try:
            usdt_balance = get_usdt_balance()
            if usdt_balance < 1:
                send_telegram_message("⚠️ *Saldo insuficiente para operar.*")
                time.sleep(60)
                continue

            current_price = get_current_price()

            # Lógica de entrada profesional simulada
            if analizar_entrada_segura(current_price):
                cantidad_a_comprar = (usdt_balance * 0.80) / current_price

                # Comprar SHIB
                order = client.new_order(
                    symbol=PAIR,
                    side="BUY",
                    type="MARKET",
                    quantity=round(cantidad_a_comprar, 0)
                )
                buy_price = float(order['fills'][0]['price'])
                send_telegram_message(f"🛒 *Compra ejecutada* a ${buy_price:.8f}")

                objetivo_take_profit = buy_price * (1 + TAKE_PROFIT_PERCENT / 100)
                objetivo_stop_loss = buy_price * (1 - STOP_LOSS_PERCENT / 100)

                # Monitorear operación
                while True:
                    current_price = get_current_price()

                    if current_price >= objetivo_take_profit:
                        sell_quantity = sum(float(fill['qty']) for fill in order['fills'])
                        client.new_order(
                            symbol=PAIR,
                            side="SELL",
                            type="MARKET",
                            quantity=round(sell_quantity, 0)
                        )
                        send_telegram_message(f"✅ *Take Profit alcanzado!* Precio: ${current_price:.8f}")
                        break

                    elif current_price <= objetivo_stop_loss:
                        sell_quantity = sum(float(fill['qty']) for fill in order['fills'])
                        client.new_order(
                            symbol=PAIR,
                            side="SELL",
                            type="MARKET",
                            quantity=round(sell_quantity, 0)
                        )
                        send_telegram_message(f"🛑 *Stop Loss activado!* Precio: ${current_price:.8f}")
                        break

                    time.sleep(5)

            else:
                print("Esperando oportunidad...")

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            send_telegram_message(f"⚠️ *Error en ejecución:* {e}")
            time.sleep(60)

# Función simulada de análisis de entrada segura
def analizar_entrada_segura(current_price):
    # Aquí normalmente iría el análisis profesional.
    # De momento simulamos 80% de probabilidad de entrada segura.
    import random
    return random.random() < 0.8  # 80% chance de entrada (para pruebas)

# Ejecutar bot
if __name__ == "__main__":
    main()
