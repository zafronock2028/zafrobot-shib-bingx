import requests
import os

# Cargar variables de entorno
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Mensaje de prueba
mensaje = "✅ Prueba de notificación enviada correctamente."

# URL para enviar el mensaje
url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
params = {
    "chat_id": CHAT_ID,
    "text": mensaje
}

# Enviar la solicitud
response = requests.get(url, params=params)

print(response.json())