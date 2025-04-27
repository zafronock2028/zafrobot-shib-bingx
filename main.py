import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
import aiohttp
import asyncio
import os

# Variables directamente integradas
TELEGRAM_BOT_TOKEN = "7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM"
API_KEY = "LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA"
SECRET_KEY = "Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg"
CHAT_ID = "1130366010"  # El tuyo real

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

async def get_usdt_balance():
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    params = {
        "recvWindow": 5000
    }
    url = "https://open-api.bingx.com/openApi/spot/v1/account/balance"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            data = await resp.json()
            if data["code"] == 0:
                for asset in data["data"]:
                    if asset["asset"] == "USDT":
                        return float(asset["balance"])
            return None

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ Bot activo y listo.\n👉 Usa /saldo para consultar tu saldo disponible en USDT.")

@dp.message(Command("saldo"))
async def saldo(message: types.Message):
    await message.answer("⏳ Consultando saldo en tiempo real...")
    balance = await get_usdt_balance()
    if balance is not None:
        await message.answer(
            f"💵 *ZafroBot Wallet*\n\n*💵 Saldo disponible en Spot:*\n{balance:.2f} USDT\n\n🕰 *Actualizado en tiempo real*",
            parse_mode="Markdown"
        )
    else:
        await message.answer("⚠️ No se pudo obtener el saldo. Intenta nuevamente más tarde.")

async def on_startup(app):
    logging.basicConfig(level=logging.INFO)

def create_app():
    app = web.Application()
    app.on_startup.append(on_startup)
    return app

if __name__ == "__main__":
    app = create_app()
    asyncio.get_event_loop().create_task(dp.start_polling(bot))
    web.run_app(app, port=10000)