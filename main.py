import os
import time
import requests
import pytz
import asyncio
from datetime import datetime
from telegram import Bot
from flask import Flask

# Variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Inicializar bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Variables iniciales
symbol = "SHIB-USDT"
buy_price = None
holding = False
daily_profit = 0
trade_counter = 0

# Función para enviar mensajes correctamente
async def enviar_mensaje(texto):
    await bot.send_message(chat_id=CHAT_ID, text=texto)

# Función para obtener saldo
def obtener_saldo():
    try:
        url = "https://open-api.bingx.com/openApi/user/getBalance"
        headers = {
            "X-BX-APIKEY": API_KEY
        }
        params = {
            "currency": "USDT"
        }
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        if data["code"] == 0:
            balance = float(data["data"]["availableBalance"])
            return balance
        else:
            return None
    except Exception as e:
        print(f"Error obteniendo saldo: {e}")
        return None

# Función para obtener precio actual
def obtener_precio_actual():
    try:
        url = f"https://open-api.bingx.com/openApi/swap/quote?symbol={symbol}"
        response = requests.get(url)
        data = response.json()
        if data["code"] == 0:
            return float(data["data"]["price"])
        else:
            return None
    except Exception as e:
        print(f"Error obteniendo precio: {e}")
        return None

# Función principal
async def main():
    global buy_price, holding, daily_profit, trade_counter

    saldo = obtener_saldo()
    if saldo is not None:
        await enviar_mensaje(f"✅ Bot iniciado correctamente.\n💰 Saldo disponible: {saldo:.2f} USDT\n\n¡Analizando oportunidades de entrada!")
    else:
        await enviar_mensaje("⚠️ Bot iniciado, pero no se pudo obtener el saldo.")

    while True:
        try:
            precio_actual = obtener_precio_actual()
            if precio_actual is None:
                await asyncio.sleep(10)
                continue

            if not holding:
                # Simulación lógica: si precio baja, compramos
                if True:  # Aquí pones tu análisis real
                    buy_price = precio_actual
                    holding = True
                    await enviar_mensaje(f"✅ ¡Compra ejecutada!\nPrecio de entrada: {buy_price}")
            else:
                if precio_actual >= buy_price * 1.015:
                    ganancia = (precio_actual - buy_price)
                    saldo_actual = obtener_saldo()
                    trade_counter += 1
                    daily_profit += ganancia
                    await enviar_mensaje(f"✅ ¡Operación cerrada en ganancia!\nVenta a: {precio_actual}\nGanancia: {ganancia:.6f} USDT\n\n💰 Saldo actual: {saldo_actual:.2f} USDT\n\nTrade {trade_counter}: PROFIT✅")
                    holding = False
                    buy_price = None
                elif precio_actual <= buy_price * 0.98:
                    perdida = (precio_actual - buy_price)
                    saldo_actual = obtener_saldo()
                    trade_counter += 1
                    daily_profit += perdida
                    await enviar_mensaje(f"❌ ¡Operación cerrada en pérdida!\nVenta a: {precio_actual}\nPérdida: {perdida:.6f} USDT\n\n💰 Saldo actual: {saldo_actual:.2f} USDT\n\nTrade {trade_counter}: -${abs(perdida):.6f}❌")
                    holding = False
                    buy_price = None

            # Cada medianoche reiniciar contador y mandar reporte diario
            ahora = datetime.now(pytz.timezone('America/New_York'))
            if ahora.hour == 23 and ahora.minute == 59:
                await enviar_mensaje(f"📊 Resumen del día:\nTotal de trades: {trade_counter}\nGanancia/perdida del día: {daily_profit:.6f} USDT")
                trade_counter = 0
                daily_profit = 0

            await asyncio.sleep(10)

        except Exception as e:
            print(f"Error principal: {e}")
            await asyncio.sleep(10)

# Iniciar Flask para mantener Render vivo
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot dinámico funcionando."

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    app.run(host='0.0.0.0', port=10000)