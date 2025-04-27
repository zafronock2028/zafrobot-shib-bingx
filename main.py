import os
import time
import hmac
import hashlib
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Función para firmar la consulta
def create_signature(params, secret_key):
    query_string = '&'.join(f"{k}={params[k]}" for k in sorted(params))
    signature = hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

# Función para obtener el saldo disponible de USDT
async def get_balance():
    url = "https://open-api.bingx.com/openApi/user/assets"
    timestamp = int(time.time() * 1000)
    params = {
        "timestamp": timestamp
    }
    signature = create_signature(params, SECRET_KEY)

    headers = {
        "X-BX-APIKEY": API_KEY
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params={**params, "signature": signature}) as response:
            if response.status == 200:
                result = await response.json()
                if result["code"] == 0:
                    for asset in result["data"]["assets"]:
                        if asset["asset"] == "USDT":
                            return float(asset.get("availableBalance", 0))
            return None

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        "<b>[ ZafroBot Dinámico Pro ]</b>\n\n"
        "🤖 ¡Listo para ayudarte a consultar tu saldo real de USDT en tu cuenta SPOT de BingX!\n\n"
        "Escribe /saldo cuando quieras saberlo en tiempo real."
    )

@dp.message(Command("saldo"))
async def saldo_handler(message: types.Message):
    # Mensaje de carga
    loading_msg = await message.answer("⏳ Consultando tu saldo, un momento...")

    balance = await get_balance()
    if balance is not None:
        await loading_msg.edit_text(
            f"<b>[ ZafroBot Dinámico Pro ]</b>\n\n"
            f"💵 <b>Saldo actual disponible en Spot:</b>\n"
            f"➤ <b>${balance:.2f} USDT</b>\n\n"
            "_(Actualizado en tiempo real.)_ ✅"
        )
    else:
        await loading_msg.edit_text(
            "<b>[ ZafroBot Dinámico Pro ]</b>\n\n"
            "⚠️ No fue posible obtener tu saldo.\n"
            "<i>Por favor intenta nuevamente en unos minutos.</i>"
        )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())