import asyncio
import hmac
import hashlib
import time
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Tus APIs integradas
API_KEY = "RA2cfzSaJKWxDrVEXitoiLZK1dpfEQLaCe8TIdG77Nl2GJEiImL7eXRRWIJDdjwYpakLIa37EQIpI6jpQ"
SECRET_KEY = "VlwOFCk2hsJxth98TQLZoHf7HLDxDCNHuGmIKyhHgh9UoturNTon3rkiLwtbsr1zxqZcOvVyWNCILFDzVVLg"
TELEGRAM_TOKEN = "8100886306:AAFRDnn32wMKXhZGfkThifFFGPhL0p6KFjw"
CHAT_ID = "1130366010"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Función para consultar saldo de USDT en SPOT
async def consultar_saldo_spot():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/assets"

    timestamp = int(time.time() * 1000)
    params = {
        "apiKey": API_KEY,
        "timestamp": timestamp
    }
    # Crear firma HMAC-SHA256
    query_string = "&".join([f"{key}={params[key]}" for key in sorted(params)])
    signature = hmac.new(SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    params["sign"] = signature

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if "data" in data:
                    for asset in data["data"]:
                        if asset.get("asset") == "USDT":
                            balance = float(asset.get("available", 0))
                            return round(balance, 2)
                return None
        except Exception as e:
            print(f"Error consultando saldo: {e}")
            return None

# Comando /start
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "**[[ ZafroBot Dinámico Pro ]]**\n\n"
        "🤖 Estoy listo para ayudarte a consultar tu saldo real de USDT en tu cuenta SPOT.\n\n"
        "Usa el comando /saldo para verlo en tiempo real."
    )

# Comando /saldo
@dp.message(Command("saldo"))
async def saldo(message: types.Message):
    saldo_usdt = await consultar_saldo_spot()
    if saldo_usdt is not None:
        await message.answer(
            f"**[[ ZafroBot Dinámico Pro ]]**\n\n"
            f"*Saldo actual disponible en SPOT:*\n\n"
            f"**{saldo_usdt} USDT**"
        )
    else:
        await message.answer(
            "**[[ ZafroBot Dinámico Pro ]]**\n\n"
            "⚠️ No fue posible obtener tu saldo actual.\n\n"
            "_Por favor intenta nuevamente en unos minutos._"
        )

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())