import os
import time
import requests
from pybit import spot
from telegram import Bot

# Configuración de entorno
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Configuración de trading
PAIR = "SHIBUSDT"
TAKE_PROFIT_PERCENT = 1.5
STOP_LOSS_PERCENT = 2
WAIT_TIME = 10  # segundos

# Inicializar clientes
session = spot.HTTP(
    endpoint="https://api.bingx.com",
    api_key=API_KEY,
    api_secret=API_SECRET
)
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def enviar_mensaje(mensaje):
    try:
        bot.send_message(chat_id=CHAT_ID, text=mensaje, parse_mode="Markdown")
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

def obtener_saldo_disponible():
    balance = session.get_wallet_balance(coin="USDT")
    saldo_total = float(balance['data']['balance'])
    saldo_utilizar = saldo_total * 0.80
    return saldo_utilizar

def obtener_precio_actual():
    ticker = session.latest_information_for_symbol(symbol=PAIR)
    return float(ticker['data'][0]['lastPrice'])

def comprar_shib(cantidad_usdt, precio_actual):
    cantidad_shib = cantidad_usdt / precio_actual
    cantidad_shib = round(cantidad_shib, 0)  # SHIB no usa decimales
    session.place_active_order(
        symbol=PAIR,
        side="Buy",
        type="Market",
        quantity=str(cantidad_shib)
    )
    return cantidad_shib

def vender_shib(cantidad_shib):
    session.place_active_order(
        symbol=PAIR,
        side="Sell",
        type="Market",
        quantity=str(cantidad_shib)
    )

# INICIO
saldo = obtener_saldo_disponible()
precio_compra = None
cantidad_shib = None
operacion_abierta = False

enviar_mensaje(f"✅ *Saldo Detectado:* ${saldo:.2f} *USDT*")
time.sleep(2)
enviar_mensaje("⚡ *ZafroBot comenzó el análisis.*\nCuando detecte una oportunidad real, recibirás la notificación de compra ejecutada.")

while True:
    try:
        precio_actual = obtener_precio_actual()
        if not operacion_abierta:
            # Simulando análisis profesional
            if True:  # Aquí puedes luego integrar análisis real
                cantidad_shib = comprar_shib(saldo, precio_actual)
                precio_compra = precio_actual
                operacion_abierta = True
                enviar_mensaje(f"✅ *Compra ejecutada a:* ${precio_actual:.8f}")
        else:
            cambio_porcentaje = ((precio_actual - precio_compra) / precio_compra) * 100
            if cambio_porcentaje >= TAKE_PROFIT_PERCENT:
                vender_shib(cantidad_shib)
                saldo = obtener_saldo_disponible()
                enviar_mensaje(f"✅ *¡Operación cerrada!*\n_Vendido a:_ ${precio_actual:.8f}\n\n💰 *Saldo actual:* ${saldo:.2f}")
                operacion_abierta = False
            elif cambio_porcentaje <= -STOP_LOSS_PERCENT:
                vender_shib(cantidad_shib)
                saldo = obtener_saldo_disponible()
                enviar_mensaje(f"❌ *¡Stop Loss activado!*\n_Vendido a:_ ${precio_actual:.8f}\n\n💰 *Saldo actual:* ${saldo:.2f}")
                operacion_abierta = False

        time.sleep(WAIT_TIME)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(WAIT_TIME)
