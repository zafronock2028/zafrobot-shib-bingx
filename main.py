import os
import logging
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram import F
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

bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

async def get_spot_balance():
    url = "https://open-api.bingx.com/openApi/user/assets"

    timestamp = str(int(time.time() * 1000))
    params = f"timestamp={timestamp}"
    signature = hmac.new(SECRET_KEY.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()

    headers = {
        "X-BX-APIKEY": API_KEY,
    }
    full_url = f"{url}?{params}&signature={signature}"

    async with aiohttp.ClientSession() as session:
        async with session.get(full_url, headers=headers) as response:
            result = await response.json()
            if result["code"] == 0:
                assets = result["data"]["assets"]
                for asset in assets:
                    if asset["asset"] == "USDT":
                        return float(asset["availableBalance"])
            return None

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "<b>[ ZafroBot Dinámico Pro ]</b>\n\n"
        "🤖 ¡Estoy listo para ayudarte a consultar tu saldo real de USDT en tu cuenta SPOT de BingX!\n\n"
        "Usa el comando /saldo para verlo en tiempo real."
    )

@dp.message(Command("saldo"))
async def saldo(message: types.Message):
    balance = await get_spot_balance()
    if balance is not None:
        await message.answer(
            f"<b>[ ZafroBot Dinámico Pro ]</b>\n\n"
            f"💰 Tu saldo actual disponible en SPOT es: <b>${balance:.2f} USDT</b>"
        )
    else:
        await message.answer(
            "<b>[ ZafroBot Dinámico Pro ]</b>\n\n"
            "⚠️ No fue posible obtener tu saldo.\n\n"
            "<i>Por favor intenta nuevamente en unos minutos.</i>"
        )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())