import os
import telegram
import time
from flask import Flask

app = Flask(__name__)

# Leer las variables de entorno
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# Crear el bot
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

# Función principal
def enviar_mensaje_prueba():
    mensaje = "✅ Bot de prueba iniciado correctamente."
    bot.send_message(chat_id=CHAT_ID, text=mensaje)

# Ejecutar la función después de que arranque el servidor Flask
@app.before_first_request
def before_first_request_func():
    enviar_mensaje_prueba()

# Rutas básicas para mantener vivo en Render
@app.route('/')
def home():
    return "Bot de prueba activo"

# Iniciar el servidor Flask
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)