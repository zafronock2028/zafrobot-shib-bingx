import requests
import time
import hmac
import hashlib
import json
from datetime import datetime, timedelta
import pytz
from telegram import Bot
from flask import Flask

# Configura tus claves y tokens
API_KEY = "TU_API_KEY"
API_SECRET = "TU_API_SECRET"
TELEGRAM_BOT_TOKEN = "TU_TELEGRAM_BOT_TOKEN"
CHAT_ID = "TU_CHAT_ID"
PAIR = "SHIB-USDT"  # Par de trading
WEBHOOK_PORT = 10000

# Inicializa el bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Variables globales
operacion_abierta = False
precio_entrada = 0.0
ganancia_diaria = 0.0
contador_operaciones = 0

# Función para obtener el saldo disponible
def obtener_saldo(api_key, api_secret):
    try:
        url = "https://open-api.bingx.com/openApi/swap/v2/user/balance"
        headers = {
            "X-API-KEY": api_key,
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if 'data' in data and 'balance' in data['data']:
            saldo = float(data['data']['balance'])
            return saldo
        else:
            print("Respuesta inesperada al obtener saldo:", data)
            return None
    except Exception as e:
        print(f"Error al obtener saldo: {e}")
        return None

# Función para obtener el precio actual
def obtener_precio_actual():
    try:
        url = f"https://open-api.bingx.com/openApi/swap/v2/quote/price?symbol={PAIR}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if 'data' in data and 'price' in data['data']:
            return float(data['data']['price'])
        else:
            print("Respuesta inesperada al obtener precio:", data)
            return None
    except Exception as e:
        print(f"Error al obtener precio: {e}")
        return None

# Función para enviar mensaje por Telegram
def enviar_mensaje(texto):
    try:
        bot.send_message(chat_id=CHAT_ID, text=texto)
    except Exception as e:
        print(f"Error enviando mensaje de Telegram: {e}")

# Inicializar el bot y mostrar saldo disponible
def iniciar_bot():
    saldo = obtener_saldo(API_KEY, API_SECRET)
    if saldo is not None:
        mensaje = f"""✅ *ZafroBot Iniciado*  
——————————————  
🧾 *Saldo disponible:* {saldo:.2f} USDT  
——————————————  
⚡️ *¡Listo para operar!*"""
        enviar_mensaje(mensaje)
        time.sleep(2)
        enviar_mensaje("⚡️ *ZafroBot ahora está analizando el mercado en busca de oportunidades.* Cuando se detecte una entrada segura, recibirás una notificación de compra ejecutada.")
    else:
        enviar_mensaje("⚠️ Bot iniciado, pero no se pudo obtener el saldo.")
    return saldo

# Función principal de trading
def ejecutar_trading():
    global operacion_abierta, precio_entrada, ganancia_diaria, contador_operaciones

    saldo = iniciar_bot()
    if saldo is None:
        saldo = 0.0

    while True:
        try:
            precio_actual = obtener_precio_actual()

            if not operacion_abierta and precio_actual:
                # Lógica de apertura de operación
                cantidad_usdt = saldo * 0.8
                cantidad_shib = cantidad_usdt / precio_actual
                precio_entrada = precio_actual
                operacion_abierta = True

                enviar_mensaje(f"✅ *Compra ejecutada:* {cantidad_shib:.0f} SHIB a {precio_entrada:.8f} USDT")

            elif operacion_abierta and precio_actual:
                # Lógica de cierre de operación
                if precio_actual >= precio_entrada * 1.015:
                    # Ganancia
                    ganancia = (precio_actual - precio_entrada) * cantidad_shib
                    saldo += ganancia
                    ganancia_diaria += ganancia
                    contador_operaciones += 1
                    enviar_mensaje(f"✅ ¡Operación cerrada! Vendido a {precio_actual:.8f} USDT. Ganancia asegurada.\n\n💰Saldo actual: {saldo:.2f} USDT")
                    operacion_abierta = False

                elif precio_actual <= precio_entrada * 0.98:
                    # Pérdida (stop loss)
                    perdida = (precio_entrada - precio_actual) * cantidad_shib
                    saldo -= perdida
                    ganancia_diaria -= perdida
                    contador_operaciones += 1
                    enviar_mensaje(f"❌ *Stop Loss ejecutado* Vendido a {precio_actual:.8f} USDT. \n\n💰Saldo actual: {saldo:.2f} USDT")
                    operacion_abierta = False

            # Si son las 23:59 envía resumen diario
            hora_actual = datetime.now(pytz.timezone('America/Lima')).strftime('%H:%M')
            if hora_actual == "23:59":
                enviar_mensaje(f"📊 *Resumen Diario:* \nOperaciones: {contador_operaciones} \nGanancia Neta: {ganancia_diaria:.2f} USDT")
                # Resetea para el siguiente día
                ganancia_diaria = 0
                contador_operaciones = 0

            time.sleep(15)  # Pausa de 15 segundos entre chequeos
        except Exception as e:
            print(f"Error general: {e}")
            time.sleep(15)

# Código para mantener Render activo
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot corriendo."

if __name__ == "__main__":
    from threading import Thread
    t = Thread(target=ejecutar_trading)
    t.start()
    app.run(host='0.0.0.0', port=WEBHOOK_PORT)