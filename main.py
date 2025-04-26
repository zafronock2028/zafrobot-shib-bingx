import os
import requests
import hmac
import hashlib
import time
import asyncio
from telegram import Bot

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
CHAT_ID = os.getenv("CHAT_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Función para firmar los parámetros
def firmar_parametros(params):
    query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params)])
    signature = hmac.new(SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

# Función para obtener saldo
async def obtener_saldo():
    try:
        url = "https://api-swap-rest.bingx.com/openApi/swap/v2/user/balance"
        params = {
            "apiKey": API_KEY,
            "timestamp": str(int(time.time() * 1000)),
        }
        params["signature"] = firmar_parametros(params)

        response = requests.get(url, params=params)
        data = response.json()

        if data["code"] == 0:
            saldo = data["data"]["balance"]
            return saldo
        else:
            print("Error en la respuesta:", data)
            return None
    except Exception as e:
        print("Error obteniendo balance:", str(e))
        return None

# Función para enviar mensaje a Telegram
async def enviar_mensaje(texto):
    await bot.send_message(chat_id=CHAT_ID, text=texto)

# Función principal
async def main():
    saldo = await obtener_saldo()
    if saldo is not None:
        mensaje = f"✅ Bot iniciado correctamente.\nSaldo actual disponible: {saldo} USDT."
    else:
        mensaje = "⚠️ Bot iniciado, pero no se pudo obtener el saldo."
    
    await enviar_mensaje(mensaje)

if __name__ == "__main__":
    asyncio.run(main())
