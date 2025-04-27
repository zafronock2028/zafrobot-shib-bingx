import os
import aiohttp
import asyncio
import hmac
import hashlib
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Iniciar bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Función para firmar parámetros
def sign_params(params, secret_key):
    query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params)])
    signature = hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

# Función para obtener saldo de USDT en Spot
async def obtener_saldo_spot():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/assets"
    timestamp = int(time.time() * 1000)

    params = {
        "apiKey": API_KEY,
        "timestamp": timestamp
    }
    signature = sign_params(params, SECRET_KEY)
    params["sign"] = signature

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("code") == 0 and "data" in data:
                    for asset in data["data"]:
                        if asset["asset"] == "USDT":
                            saldo = float(asset.get("available", 0))
                            return saldo
            return None

# Comando /start
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    texto = (
        "**[[ ZafroBot Dinámico Pro ]]**\n\n"
        "🤖 ¡Estoy listo para ayudarte a consultar tu saldo real de **USDT** en tu cuenta **SPOT** de BingX!\n\n"
        "Usa el comando /saldo para verlo en **tiempo real**."
    )
    await message.answer(texto, parse_mode="Markdown")

# Comando /saldo
@dp.message(Command("saldo"))
async def saldo_handler(message: types.Message):
    saldo = await obtener_saldo_spot()
    if saldo is not None:
        respuesta = (
            "**[[ ZafroBot Dinámico Pro ]]**\n\n"
            "✅ **Saldo disponible en SPOT:**\n\n"
            f"💵 **{saldo:.2f} USDT**\n\n"
            "_(Actualizado en tiempo real.)_"
        )
    else:
        respuesta = (
            "**[[ ZafroBot Dinámico Pro ]]**\n\n"
            "⚠️ No fue posible obtener tu saldo.\n\n"
            "_Por favor intenta nuevamente en unos minutos._"
        )
    await message.answer(respuesta, parse_mode="Markdown")

# Lanzar el bot
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())