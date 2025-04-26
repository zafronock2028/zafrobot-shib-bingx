import requests
import os
from flask import Flask

app = Flask(__name__)

# Variables de entorno
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

@app.route('/')
def send_test_message():
    mensaje = "✅ Prueba de notificación enviada correctamente."

    # URL para enviar mensaje
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": CHAT_ID,
        "text": mensaje
    }

    # Enviar mensaje
    response = requests.get(url, params=params)

    return f"Mensaje enviado. Respuesta: {response.text}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))