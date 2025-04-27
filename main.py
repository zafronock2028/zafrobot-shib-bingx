import os
import asyncio
import logging
import aiohttp
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from flask import Flask

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Obtener variables de entorno
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Web Server para mantener vivo en Render
app = Flask(__name__)

@app.route('/')
def home():
    return 'ZafroBot está corriendo!'

# Función para consultar saldo en tiempo real
async def get_spot_balance():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/balance"
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    params = {
        "timestamp": int(asyncio.get_event_loop().time() * 1000)
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            data = await response.json()
            if data.get("code") == 0:
                balances = data["data"]["balances"]
                for balance in balances:
                    if balance["asset"] == "USDT":
                        return float(balance["free"])
    return None

# Comando /start
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ Bot activo y listo.\n👉 Usa /saldo para ver tu saldo Spot actualizado.")

# Comando /saldo
@dp.message(Command("saldo"))
async def saldo(message: types.Message):
    await message.answer("⏳ Consultando saldo en tiempo real...")
    balance = await get_spot_balance()
    if balance is not None:
        await message.answer(
            f"📒 *ZafroBot Wallet*\n\n"
            f"💰 *Saldo USDT disponible en Spot:*\n`{balance:.2f}` USDT\n\n"
            f"🕰️ *Actualizado en tiempo real*",
            parse_mode="Markdown"
        )
    else:
        await message.answer("⚠️ No se pudo obtener el saldo. Intenta nuevamente en unos segundos.")

# Función principal
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    app.run(host="0.0.0.0", port=10000)