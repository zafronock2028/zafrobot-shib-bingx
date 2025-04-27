import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiohttp import web
import requests

# Configura el logging
logging.basicConfig(level=logging.INFO)

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Inicializar bot y dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Función para obtener saldo en tiempo real
async def get_spot_balance():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/balance"
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data["code"] == 0:
                balances = data["data"]["balances"]
                usdt_balance = next((float(asset["free"]) for asset in balances if asset["asset"] == "USDT"), 0)
                return usdt_balance
    except Exception as e:
        logging.error(f"Error obteniendo el balance: {e}")
    return None

# Comando /start
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "✅ Bot activo y listo.\n👉 Usa /saldo para ver tu saldo Spot actualizado."
    )

# Comando /saldo
@dp.message(Command(commands=["saldo"]))
async def saldo(message: types.Message):
    await message.answer("⏳ Consultando saldo en tiempo real...")
    balance = await get_spot_balance()
    if balance is not None:
        await message.answer(
            f"🏦 *ZafroBot Wallet*\n\n"
            f"💰 *Saldo USDT disponible en Spot:* `{balance:.2f}` *USDT*\n\n"
            f"🕓 _Actualizado en tiempo real_",
            parse_mode="Markdown"
        )
    else:
        await message.answer("⚠️ No se pudo obtener el saldo. Intenta nuevamente en unos segundos.")

# Web server para que Render no cierre el bot
async def handle(request):
    return web.Response(text="Bot running!")

async def main():
    # Web server
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

    # Iniciar bot
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())