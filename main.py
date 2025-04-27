import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
import aiohttp
import hmac
import hashlib
import time

# Credenciales
API_KEY = "LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA"
SECRET_KEY = "Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg"
TELEGRAM_BOT_TOKEN = "7768905391:AAGn5T2LiPe4BUpmEwJb2b5ZTrG6EyoGUSU"
CHAT_ID = 1130366010  # ID del chat (no utilizado directamente en este ejemplo)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command(commands=["saldo"]))
async def saldo_spot(message: Message):
    """Maneja el comando /saldo: consulta el saldo de USDT en Spot."""
    # Construir parámetros de la solicitud firmada para la API de BingX
    timestamp = int(time.time() * 1000)
    params = {
        "apiKey": API_KEY,
        "timestamp": timestamp
    }
    # Generar la firma HMAC-SHA256
    query_string = "&".join([f"{key}={params[key]}" for key in sorted(params)])
    signature = hmac.new(SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    params["sign"] = signature

    # Endpoint de la API de BingX para obtener saldos de spot
    url = "https://api.bingx.com/openapi/spot/v1/account/assets"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    await message.answer("Error al obtener el saldo de BingX.")
                    return
                data = await resp.json()
        except Exception as e:
            await message.answer(f"Error en la conexión con BingX API: {e}")
            return

    # Obtener el saldo de USDT del resultado
    balance = None
    # Algunos formatos de respuesta posibles:
    # 1. data["data"] es lista de activos con campos "asset" y "available"
    # 2. data["balances"] es lista (similar a Binance)
    if data is not None:
        if "data" in data and isinstance(data["data"], list):
            for asset_info in data["data"]:
                if asset_info.get("asset") == "USDT":
                    balance = asset_info.get("available") or asset_info.get("free") or "0"
                    break
        elif "balances" in data and isinstance(data["balances"], list):
            for asset_info in data["balances"]:
                if asset_info.get("asset") == "USDT":
                    balance = asset_info.get("free") or "0"
                    break

    # Si no se encontró, asignar 0
    if balance is None:
        balance = "0"

    # Formatear el balance como número (float)
    try:
        balance_float = float(balance)
    except:
        balance_float = 0.0

    # Enviar mensaje con el saldo de USDT en Spot
    await message.answer(f"Saldo disponible en Spot: {balance_float} USDT")

async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())