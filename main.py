import asyncio
import aiohttp
import time
import hmac
import hashlib
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# Credenciales API
API_KEY = "LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA"
SECRET_KEY = "Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg"
TELEGRAM_BOT_TOKEN = "7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM"
CHAT_ID = "1130366010"

# Inicializar bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command(commands=["start"]))
async def start(message: Message):
    await message.answer(
        "👋 ¡Bienvenido a ZafroBot!\n\n"
        "Este bot te ayuda a consultar tu saldo disponible de **USDT** en tu cuenta Spot de **BingX** en tiempo real.\n\n"
        "Envía el comando /saldo para ver tu saldo actualizado."
    )

@dp.message(Command(commands=["saldo"]))
async def saldo_spot(message: Message):
    """Consulta de saldo de USDT en Spot."""
    timestamp = int(time.time() * 1000)
    params = {
        "apiKey": API_KEY,
        "timestamp": timestamp
    }
    query_string = "&".join([f"{key}={params[key]}" for key in sorted(params)])
    signature = hmac.new(SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    params["sign"] = signature

    url = "https://api.bingx.com/openapi/spot/v1/account/assets"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                if resp.status != 200 or not data.get("data"):
                    await message.answer("❌ No se pudo obtener el saldo de USDT.\nIntenta más tarde.")
                    return
        except Exception as e:
            await message.answer(f"❌ Error en la conexión a BingX API: {e}")
            return

    balance = 0.0
    try:
        assets = data.get("data", [])
        for asset in assets:
            if asset.get("asset") == "USDT":
                balance = float(asset.get("available", 0) or asset.get("balance", 0) or asset.get("free", 0))
                break
    except Exception:
        balance = 0.0

    balance_formatted = "{:.2f}".format(balance)

    mensaje = (
        "┌───────────────┐\n"
        "│ 📋 *Saldo en Spot* │\n"
        "├───────────────┤\n"
        f"│ 💵 Moneda: USDT │\n"
        f"│ 📈 Disponible: {balance_formatted} │\n"
        "├───────────────┤\n"
        "│ ⏰ Consulta en tiempo real │\n"
        "└───────────────┘"
    )
    await message.answer(mensaje, parse_mode="Markdown")

async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())