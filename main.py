import os
import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from flask import Flask

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tokens y claves desde variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Inicializar Bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Endpoint de la API para saldo spot
API_URL = "https://open-api.bingx.com/openApi/swap/v2/user/balance"

async def obtener_saldo_spot_usdt():
    """Obtiene el saldo solo de USDT en Spot"""
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, headers=headers) as response:
            if response.status != 200:
                logger.error(f"Error en la API: {response.status}")
                return None
            data = await response.json()
            balances = data.get("data", [])
            for balance in balances:
                if balance["asset"] == "USDT":
                    return float(balance["balance"])
            return 0.0

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ Bot activo y listo.\n"
        "👉 Usa /saldo para ver tu saldo Spot actualizado."
    )

@dp.message(Command("saldo"))
async def cmd_saldo(message: types.Message):
    await message.answer("⏳ Consultando saldo en tiempo real...")
    saldo = await obtener_saldo_spot_usdt()
    if saldo is None:
        await message.answer("⚠️ No se pudo obtener el saldo. Intenta nuevamente en unos segundos.")
    else:
        await message.answer(
            f"🪙 *Saldo USDT disponible en Spot:*\n"
            f"*{saldo:.2f}* _USDT_\n\n"
            f"🕒 _Actualizado en tiempo real_",
            parse_mode="Markdown"
        )

# Flask app para mantener vivo
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot Notifier PRO está activo."

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    app.run(host="0.0.0.0", port=10000)