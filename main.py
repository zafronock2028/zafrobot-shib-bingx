import os
import time
import requests
from pybit.unified_trading import HTTP
from datetime import datetime, timedelta

# Variables de entorno
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")
telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("CHAT_ID")

# Configuraciones
pair = "SHIBUSDT"
profit_target = 1.5  # 1.5% ganancia
stop_loss_threshold = -2.0  # -2% pérdida
capital_usage = 0.8  # Usar el 80% del saldo
report_time_utc = "00:00"  # Hora de reporte diario en UTC (modificable)

# Inicializar cliente de BingX
session = HTTP(
    testnet=False,
    api_key=api_key,
    api_secret=api_secret,
)

# Variables de control
active_trade = False
entry_price = 0.0
trade_counter = 1
daily_profit = 0.0
last_report_date = datetime.utcnow().date()

# Funciones
def send_telegram(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")

def get_balance():
    try:
        balance = session.get_wallet_balance(accountType="UNIFIED")
        usdt_balance = float(balance['result']['list'][0]['totalEquity'])
        return usdt_balance
    except Exception as e:
        print(f"Error obteniendo balance: {e}")
        return 0.0

def get_price(symbol):
    try:
        price = session.get_ticker(symbol=symbol)['result'][0]['lastPrice']
        return float(price)
    except Exception as e:
        print(f"Error obteniendo precio: {e}")
        return 0.0

def buy_shib(usdt_amount):
    price = get_price(pair)
    if price == 0:
        return 0
    quantity = round((usdt_amount / price), 0)
    try:
        order = session.place_order(
            category="spot",
            symbol=pair,
            side="Buy",
            orderType="Market",
            qty=quantity
        )
        return price
    except Exception as e:
        print(f"Error ejecutando compra: {e}")
        return 0

def sell_shib(quantity):
    try:
        order = session.place_order(
            category="spot",
            symbol=pair,
            side="Sell",
            orderType="Market",
            qty=quantity
        )
        return True
    except Exception as e:
        print(f"Error ejecutando venta: {e}")
        return False

# Iniciar bot
send_telegram("🤖 *ZafroBot Dinámico* ha iniciado.\n🔍 Analizando oportunidades en *SHIB/USDT*...")

while True:
    now = datetime.utcnow()

    # Reporte diario
    if now.strftime("%H:%M") == report_time_utc and last_report_date != now.date():
        send_telegram(f"📊 *Reporte Diario*: Ganancia acumulada: `${daily_profit:.2f}` USDT")
        daily_profit = 0.0
        last_report_date = now.date()

    try:
        if not active_trade:
            saldo = get_balance()
            if saldo < 5:
                send_telegram("⚠️ *Saldo insuficiente para operar*.")
                time.sleep(60)
                continue

            usdt_to_use = saldo * capital_usage
            entry_price = buy_shib(usdt_to_use)
            if entry_price > 0:
                quantity_bought = usdt_to_use / entry_price
                active_trade = True
                send_telegram(f"🟢 *Compra realizada* a `{entry_price}` USDT.\n🔄 Monitoreando operación...")
                entry_time = datetime.utcnow()

        if active_trade:
            current_price = get_price(pair)
            price_change = ((current_price - entry_price) / entry_price) * 100

            if price_change >= profit_target:
                if sell_shib(quantity_bought):
                    profit = quantity_bought * (current_price - entry_price)
                    daily_profit += profit
                    send_telegram(f"✅ *Operación cerrada!* Vendido a `{current_price}` USDT.\n📈 *Ganancia:* `${profit:.2f}`\n💰 *Saldo actual:* `${get_balance():.2f}`")
                    active_trade = False
                    trade_counter += 1
                    time.sleep(10)
            elif price_change <= stop_loss_threshold:
                if sell_shib(quantity_bought):
                    loss = quantity_bought * (current_price - entry_price)
                    daily_profit += loss
                    send_telegram(f"❌ *Operación cerrada en pérdida.* Vendido a `{current_price}` USDT.\n📉 *Pérdida:* `${loss:.2f}`\n💰 *Saldo actual:* `${get_balance():.2f}`")
                    active_trade = False
                    trade_counter += 1
                    time.sleep(10)

    except Exception as e:
        print(f"Error general: {e}")
        time.sleep(60)

    time.sleep(10)
