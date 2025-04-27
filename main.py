import asyncio
import time
import hmac
import hashlib
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# Credenciales
API_KEY = "LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA"
SECRET_KEY = "Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg"
TELEGRAM_BOT_TOKEN = "7768905391:AAGn5T2LiPe4BUpmEwJb2b5ZTrG6EyoGUSU"

# Inicialización del bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Función para obtener saldo Spot
async def get_spot_balance():
    timestamp = int(time.time() * 1000)
    params = {
        "apiKey": API_KEY,
        "timestamp": timestamp
    }
    # Firma HMAC-SHA256
    query_string = "&".join(f"{key}={params[key]}" for key in sorted(params))
    signature = hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    params["sign"] = signature

    url = "https://api.bingx.com/openapi/spot/v1/account/assets"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    print(f"Error HTTP {resp.status}")
                    return None
                return await resp.json()
        except Exception as e:
            print(f"Error al conectar con BingX: {e}")
            return None

# Manejador del comando /saldo
@dp.message(Command(commands=["saldo"]))
async def saldo_spot(message: Message):
    response = await get_spot_balance()
    
    if not response:
        await message.answer("❌ No se pudo conectar con BingX. Inténtalo más tarde.")
        return

    balance = 0.0
    if "data" in response and isinstance(response["data"], list):
        for asset_info in response["data"]:
            if asset_info.get("asset") == "USDT":
                balance = float(asset_info.get("available", 0))
                break

    if balance > 0:
        await message.answer(f"✅ *Saldo disponible en Spot:* `{balance:.2f} USDT`", parse_mode="Markdown")
    else:
        await message.answer("⚠️ No se encontró saldo disponible en USDT.")

# Función principal
async def main():
    try:
        print("Bot iniciado y corriendo...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())