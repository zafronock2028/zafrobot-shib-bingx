import os
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram import F
from aiogram.types import Message
from aiogram import Router
import asyncio
import hmac
import hashlib
import time

# Obtener variables de entorno correctas
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
CHAT_ID = os.getenv("CHAT_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Iniciar bot y dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

router = Router()
dp.include_router(router)

# Función para firmar la solicitud a BingX
def generate_signature(secret_key, timestamp):
    message = f"timestamp={timestamp}"
    signature = hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

# Función para obtener saldo en SPOT (USDT)
async def obtener_saldo_spot():
    url = "https://open-api.bingx.com/openApi/user/assets"
    timestamp = str(int(time.time() * 1000))
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    params = {
        "timestamp": timestamp,
        "signature": generate_signature(SECRET_KEY, timestamp)
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data["code"] == 0:
                    for asset in data["data"]:
                        if asset["asset"] == "USDT":
                            return float(asset["balance"])
                else:
                    print("Error en respuesta de API:", data)
            else:
                print("Error de conexión:", response.status)
    return None

# Comando /start
@router.message(Command("start"))
async def start(message: Message):
    bienvenida = (
        "**[[ ZafroBot Dinámico Pro ]]**\n\n"
        "🤖 Estoy listo para ayudarte a consultar tu saldo real de USDT en tu cuenta SPOT de BingX.\n\n"
        "Usa el comando /saldo para verlo en **tiempo real**."
    )
    await message.answer(bienvenida, parse_mode="Markdown")

# Comando /saldo
@router.message(Command("saldo"))
async def saldo(message: Message):
    saldo = await obtener_saldo_spot()
    if saldo is not None:
        respuesta = (
            "**[[ ZafroBot Dinámico Pro ]]**\n\n"
            f"💰 Tu saldo actual en SPOT es: **{saldo} USDT**\n\n"
            "_(Datos en tiempo real)._"
        )
    else:
        respuesta = (
            "**[[ ZafroBot Dinámico Pro ]]**\n\n"
            "⚠️ No fue posible obtener tu saldo actual.\n\n"
            "_Por favor intenta nuevamente en unos minutos._"
        )
    await message.answer(respuesta, parse_mode="Markdown")

# Iniciar el bot
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())