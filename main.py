import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from flask import Flask
import requests

# Cargar las variables de entorno
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
CHAT_ID = os.getenv("CHAT_ID")

# Crear el bot correctamente para AIOGRAM v3
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Crear la app Flask (para que Render no lo cierre por inactividad)
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot Dinámico Pro está activo."

# Función para obtener el saldo
async def obtener_saldo():
    try:
        url = "https://open-api.bingx.com/openApi/spot/v1/account/assets"
        headers = {
            "X-BX-APIKEY": API_KEY
        }
        response = requests.get(url, headers=headers)
        data = response.json()
        
        # Buscar el saldo en USDT
        if data["code"] == 0:
            balances = data["data"]["balances"]
            for balance in balances:
                if balance["asset"] == "USDT":
                    saldo = float(balance["free"])
                    return saldo
            return 0.0
        else:
            return None
    except Exception as e:
        print(f"Error obteniendo saldo: {e}")
        return None

# Manejador de comando /start
@dp.message(commands=["start"])
async def start_handler(message: types.Message):
    await message.answer("✅ Bot vinculado correctamente. Consultando saldo...")

    saldo = await obtener_saldo()
    if saldo is None:
        await message.answer("⚠️ Bot vinculado, pero no se pudo obtener el saldo.\nVerifica tus API Keys.")
    else:
        await message.answer(f"💰 Tu saldo disponible en Spot es: <b>{saldo:.2f} USDT</b>")

# Función principal
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    app.run(host="0.0.0.0", port=5000)