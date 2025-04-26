import os
import logging
import asyncio
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from flask import Flask

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Obtener variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
CHAT_ID = os.getenv("CHAT_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Inicializar bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Inicializar servidor Flask
app = Flask(__name__)

# Función para obtener el saldo del Spot en USDT
def obtener_saldo_spot():
    try:
        url = "https://open-api.bingx.com/openApi/user/getBalance"
        headers = {
            "X-BX-APIKEY": API_KEY
        }
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            balances = data.get("data", {}).get("balances", [])
            for balance in balances:
                if balance.get("asset") == "USDT":
                    return float(balance.get("balance", 0))
            return 0  # No hay USDT
        else:
            return None
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return None

# Función que envía el mensaje de bienvenida y saldo al iniciar
async def enviar_mensaje_bienvenida():
    saldo = obtener_saldo_spot()

    if saldo is None:
        mensaje = "⚠️ Bot vinculado, pero no se pudo obtener el saldo.\nVerifica tus API Keys."
    else:
        mensaje = f"✅ Bot vinculado exitosamente.\nSaldo disponible en Spot: <b>{saldo:.2f} USDT</b>."

    await bot.send_message(chat_id=CHAT_ID, text=mensaje)

# Comando /start para enviar saldo manualmente si quieres
@dp.message(Command(commands=["start"]))
async def cmd_start(message: Message):
    saldo = obtener_saldo_spot()

    if saldo is None:
        await message.answer("⚠️ No se pudo obtener el saldo.\nVerifica tus API Keys.")
    else:
        await message.answer(f"✅ Saldo actual en Spot: <b>{saldo:.2f} USDT</b>.")

# Endpoint raíz para mantener Render activo
@app.route('/')
def home():
    return 'Bot funcionando!'

# Función principal
async def main():
    await enviar_mensaje_bienvenida()
    await dp.start_polling(bot)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    app.run(host="0.0.0.0", port=5000)