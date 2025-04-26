import os
import time
import hmac
import hashlib
import requests
from flask import Flask
from telegram import Bot
from pybit.unified_trading import HTTP

# Configuración
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Cliente de BingX
session = HTTP(
    testnet=False,
    api_key=API_KEY,
    api_secret=API_SECRET,
)

# Cliente de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Variables de control
en_operacion = False
total_ganancia_diaria = 0.0
conteo_operaciones = 0

# Función para obtener saldo disponible
def obtener_saldo():
    try:
        response = session.get_wallet_balance(accountType="SPOT")
        balance = response['result']['balance']
        for coin in balance:
            if coin['coin'] == 'USDT':
                return float(coin['availableBalance'])
    except Exception as e:
        print(f"Error obteniendo saldo: {e}")
        return None

# Función para enviar mensajes
def enviar_mensaje(texto):
    try:
        bot.send_message(chat_id=CHAT_ID, text=texto)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

# Función para simular compra
def comprar(cantidad):
    try:
        # Aquí deberías usar tu lógica real de compra
        precio_compra = obtener_precio_actual()
        enviar_mensaje(f"✅ ¡Compra ejecutada! Precio de compra: ${precio_compra:.6f}")
        return precio_compra
    except Exception as e:
        enviar_mensaje(f"⚠️ Error al comprar: {e}")
        return None

# Función para simular venta
def vender(cantidad, precio_compra):
    try:
        # Aquí deberías usar tu lógica real de venta
        precio_venta = obtener_precio_actual()
        ganancia = (precio_venta - precio_compra) * cantidad
        return ganancia, precio_venta
    except Exception as e:
        enviar_mensaje(f"⚠️ Error al vender: {e}")
        return None, None

# Función para obtener precio actual (simulado)
def obtener_precio_actual():
    # Simulación de precio actual
    response = session.get_ticker(symbol="SHIB/USDT")
    return float(response['result']['lastPrice'])

# Función principal del bot
def bot_principal():
    global en_operacion, total_ganancia_diaria, conteo_operaciones

    saldo = obtener_saldo()
    if saldo is None:
        enviar_mensaje("⚠️ Bot iniciado, pero no se pudo obtener el saldo.")
        return

    enviar_mensaje(f"✅ ZafroBot Iniciado\n-------------------------\n💳 Saldo disponible: ${saldo:.2f} USDT\n-------------------------\n⚡ ¡Listo para analizar oportunidades!")

    time.sleep(2)

    enviar_mensaje("⏳ Analizando oportunidades...\nCuando se detecte una entrada, recibirás la notificación automáticamente.")

    cantidad_compra = saldo * 0.8  # Usamos el 80% del saldo

    while True:
        if not en_operacion:
            precio_actual = obtener_precio_actual()
            # Aquí colocas tu lógica para decidir cuándo comprar
            # Suponiendo que siempre compra para ejemplo
            precio_compra = comprar(cantidad_compra)
            if precio_compra:
                en_operacion = True
                precio_objetivo = precio_compra * 1.015  # 1.5% de ganancia objetivo
                precio_stop = precio_compra * 0.98       # 2% de pérdida stop loss

                while en_operacion:
                    precio_actual = obtener_precio_actual()
                    if precio_actual >= precio_objetivo:
                        ganancia, precio_venta = vender(cantidad_compra, precio_compra)
                        saldo_actual = obtener_saldo()
                        conteo_operaciones += 1
                        total_ganancia_diaria += ganancia
                        enviar_mensaje(f"✅ ¡Operación cerrada! Vendido a ${precio_venta:.6f}\nGanancia asegurada.\n💰 Saldo actual: ${saldo_actual:.2f}\n\nTrade {conteo_operaciones} PROFIT✅")
                        en_operacion = False
                    elif precio_actual <= precio_stop:
                        ganancia, precio_venta = vender(cantidad_compra, precio_compra)
                        saldo_actual = obtener_saldo()
                        conteo_operaciones += 1
                        total_ganancia_diaria += ganancia
                        enviar_mensaje(f"❌ ¡Stop Loss activado! Vendido a ${precio_venta:.6f}\nPérdida limitada.\n💰 Saldo actual: ${saldo_actual:.2f}\n\nTrade {conteo_operaciones} -${abs(ganancia):.2f}❌")
                        en_operacion = False

                    time.sleep(5)  # Espera entre chequeos

        time.sleep(5)

# Servidor web para mantener Render activo
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot está corriendo."

if __name__ == "__main__":
    import threading
    threading.Thread(target=bot_principal).start()
    app.run(host="0.0.0.0", port=10000)
