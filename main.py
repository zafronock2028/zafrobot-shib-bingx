import os
import requests
import time
from flask import Flask
from telegram import Bot

# Cargar variables de entorno
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Configurar bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Configurar Flask
app = Flask(__name__)

# Función para enviar mensajes a Telegram
def enviar_mensaje(texto):
    try:
        bot.send_message(chat_id=CHAT_ID, text=texto)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

# Función para obtener el saldo disponible
def obtener_saldo():
    try:
        url = "https://open-api.bingx.com/openApi/swap/v2/user/balance"
        params = {"currency": "USDT"}
        headers = {"X-BX-APIKEY": API_KEY}
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        if "data" in data and "availableBalance" in data["data"]:
            saldo = float(data["data"]["availableBalance"])
            return saldo
        else:
            return None
    except Exception as e:
        print(f"Error al obtener saldo: {e}")
        return None

# Al iniciar el servidor, enviar los tres mensajes
@app.before_first_request
def cuando_inicie():
    # 1. Mensaje de bienvenida
    enviar_mensaje("✅ Bot iniciado correctamente. Bienvenido Zafronock.")

    # 2. Obtener saldo
    saldo = obtener_saldo()
    if saldo is not None:
        enviar_mensaje(f"💰 Tu saldo disponible es: {saldo:.2f} USDT.")
    else:
        enviar_mensaje("⚠️ No se pudo obtener el saldo disponible.")

    # 3. Mensaje de inicio de análisis
    time.sleep(2)  # pequeña pausa para mejor orden
    enviar_mensaje("🔍 Bot preparado. Empezando a analizar el mercado...")

# Ruta principal para mostrar que el bot está activo
@app.route('/')
def home():
    return "Bot funcionando correctamente."

# Iniciar servidor Flask
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)