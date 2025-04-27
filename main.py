import os
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv
import time
import hmac
import hashlib

# Cargar variables de entorno
load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

async def obtener_saldo():
    url = "https://open-api.bingx.com/openApi/wallet/supported-coin-list"

    timestamp = str(int(time.time() * 1000))
    params = f"timestamp={timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), params.encode(), hashlib.sha256).hexdigest()

    headers = {
        "X-BX-APIKEY": API_KEY,
        "Content-Type": "application/json",
    }

    full_url = f"{url}?{params}&signature={signature}"

    async with aiohttp.ClientSession() as session:
        async with session.get(full_url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                for coin in data.get("data", []):
                    if coin["asset"] == "USDT":
                        spot_balance = float(coin.get("spotAvailableBalance", 0))
                        return spot_balance
                return 0.0
            else:
                return None

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    texto = (
        "**[[ ZafroBot Dinámico Pro ]]**\n\n"
        "🤖 Estoy listo para ayudarte a consultar tu saldo real de USDT en tu cuenta SPOT de BingX.\n\n"
        "Usa el comando /saldo para verlo en tiempo real."
    )
    await message.answer(texto, parse_mode="Markdown")

@dp.message(Command("saldo"))
async def saldo_handler(message: types.Message):
    saldo = await obtener_saldo()
    if saldo is not None:
        respuesta = (
            "**[[ ZafroBot Dinámico Pro ]]**\n\n"
            f"💰 Saldo actual disponible en SPOT: **${saldo:.2f} USDT**"
        )
    else:
        respuesta = (
            "**[[ ZafroBot Dinámico Pro ]]**\n\n"
            "⚠️ No fue posible obtener tu saldo actual.\n\n"
            "_Por favor intenta nuevamente en unos minutos._"
        )
    await message.answer(respuesta, parse_mode="Markdown")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())