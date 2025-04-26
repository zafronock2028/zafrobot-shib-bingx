import os
import requests
from flask import Flask
from telegram import Bot
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Datos de acceso
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Inicializar Flask
app = Flask(__name__)

# Inicializar bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Función para obtener saldo
def obtener_saldo():
    try:
        url = "https://open-api.bingx.com/openApi/user/getBalance"
        headers = {
            "X-BX-APIKEY": API_KEY
        }
        response = requests.get(url, headers=headers)
        data = response.json()
        balances = data.get('data', {}).get('balanceList', [])
        usdt_balance = next((b['balance'] for b in balances if b['asset'] == 'USDT'), None)
        return float(usdt_balance) if usdt_balance else None
    except Exception as e:
        print(f"Error obteniendo saldo: {e}")
        return None

# Función para enviar mensajes de forma segura
def enviar_mensaje(texto):
    try:
        bot.send_message(chat_id=CHAT_ID, text=texto)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

# Ruta principal
@app.route('/')
def inicio():
    return "Bot funcionando correctamente."

# Función de arranque
def arranque_bot():
    # Enviar mensaje de arranque
    enviar_mensaje("✅ Bot iniciado correctamente.")

    # Obtener y mostrar saldo
    saldo = obtener_saldo()
    if saldo is not None:
        enviar_mensaje(f"💰 Saldo actual detectado: {saldo:.2f} USDT.")
    else:
        enviar_mensaje("⚠️ No se pudo obtener el saldo.")

    # Mensaje de inicio de análisis
    enviar_mensaje("🔍 Iniciando análisis... Buscando mejor oportunidad.")

# Ejecutar funciones después de iniciar Flask
with app.app_context():
    arranque_bot()

# Ejecutar app
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)