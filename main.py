import os
import telegram
from flask import Flask

app = Flask(__name__)

# Leer las variables de entorno
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# Crear el bot
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

# Función para enviar mensaje de inicio
def enviar_mensaje_inicio():
    mensaje = "✅ Bot de prueba iniciado correctamente y listo para operar."
    bot.send_message(chat_id=CHAT_ID, text=mensaje)

# Cuando el servidor esté listo
@app.before_first_request
def before_first_request_func():
    enviar_mensaje_inicio()

# Rutas para mantener activo en Render
@app.route('/')
def home():
    return "Bot funcionando correctamente."

# Ejecutar
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)