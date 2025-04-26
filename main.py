import os
import requests
import time
import pytz
from datetime import datetime
from flask import Flask
from telegram import Bot

# Configurar variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Inicializar bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Crear app Flask
app = Flask(__name__)

# Parámetros de operación
symbol = "SHIB-USDT"
profit_target = 0.015  # 1.5% de ganancia
stop_loss = 0.02      # 2% de pérdida
operacion_abierta = False
precio_compra = 0.0
saldo_actual = 0.0
historial_trades = []
zona_horaria = pytz.timezone('America/Lima')

# Función para enviar mensajes por Telegram
def enviar_mensaje(mensaje):
    try:
        bot.send_message(chat_id=CHAT_ID, text=mensaje)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

# Función para obtener saldo disponible
def obtener_saldo():
    try:
        url = "https://open-api.bingx.com/openApi/spot/v1/account/balance"
        headers = {"X-BX-APIKEY": API_KEY}
        response = requests.get(url, headers=headers)
        data = response.json()
        if 'data' in data and 'balance' in data['data']:
            return float(data['data']['balance'])
        else:
            return None
    except Exception as e:
        print(f"Error obteniendo saldo: {e}")
        return None

# Función para obtener precio actual
def obtener_precio_actual():
    try:
        url = f"https://open-api.bingx.com/openApi/spot/v1/ticker/24hr?symbol={symbol}"
        response = requests.get(url)
        data = response.json()
        return float(data['data']['lastPrice'])
    except Exception as e:
        print(f"Error obteniendo precio: {e}")
        return None

# Inicio
@app.route('/')
def home():
    return "ZafroBot corriendo!"

if __name__ == '__main__':
    # Obtener saldo inicial
    saldo_actual = obtener_saldo()

    if saldo_actual is None:
        enviar_mensaje("⚠️ Bot iniciado, pero no se pudo obtener el saldo.")
    else:
        enviar_mensaje(f"✅ ZafroBot iniciado.\n\n💰Saldo disponible: ${saldo_actual:.2f} USDT\n\n⚡ ¡Listo para operar!")
        enviar_mensaje("⌛ Analizando el mercado... recibirás una notificación cuando se detecte una oportunidad.")

    # Bucle principal
    while True:
        try:
            precio_actual = obtener_precio_actual()
            if precio_actual is None:
                print("No se pudo obtener precio actual.")
                time.sleep(10)
                continue

            # Lógica de trading
            if not operacion_abierta:
                # Abrir compra
                precio_compra = precio_actual
                operacion_abierta = True
                enviar_mensaje(f"✅ ¡Compra ejecutada!\n\nPrecio de compra: ${precio_compra:.8f}")
            else:
                # Monitorear operación
                ganancia = (precio_actual - precio_compra) / precio_compra

                if ganancia >= profit_target:
                    saldo_actual = obtener_saldo() or saldo_actual  # Actualizar saldo
                    operacion_abierta = False
                    historial_trades.append("PROFIT✅")
                    enviar_mensaje(f"✅ ¡Operación cerrada con GANANCIA!\n\nPrecio de venta: ${precio_actual:.8f}\n💰Saldo actual: ${saldo_actual:.2f}")
                elif ganancia <= -stop_loss:
                    saldo_actual = obtener_saldo() or saldo_actual
                    operacion_abierta = False
                    historial_trades.append("❌ PÉRDIDA")
                    enviar_mensaje(f"❌ ¡Operación cerrada con PÉRDIDA!\n\nPrecio de venta: ${precio_actual:.8f}\n💰Saldo actual: ${saldo_actual:.2f}")

            # Cada 24 horas (puedes ajustar) enviar resumen
            ahora = datetime.now(zona_horaria)
            if ahora.hour == 23 and ahora.minute == 59:
                resumen = "📈 Resumen del día:\n"
                for idx, resultado in enumerate(historial_trades, start=1):
                    resumen += f"Trade {idx}: {resultado}\n"
                enviar_mensaje(resumen)
                historial_trades.clear()

            time.sleep(15)  # Esperar 15 segundos entre análisis
        except Exception as e:
            print(f"Error en el bucle principal: {e}")
            time.sleep(10)