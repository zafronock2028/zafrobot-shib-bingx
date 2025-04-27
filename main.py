import logging
import asyncio
import aiohttp
import hmac
import hashlib
import time
import json
from aiogram import Bot, Dispatcher, types

# Tus variables integradas
API_KEY = "LCRNrSVWUf1crSsLE5+xdPxYtUWdNVte"
SECRET_KEY = "Kckg5g1hCDsE9N83p8wpxDiUWk0fcfTZY"
TELEGRAM_BOT_TOKEN = "7768905391:AAGn5T2LiPe4RUpmEwJb"
CHAT_ID = "1130366010"

# Inicializar bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Formato del mensaje de saldo
def formatear_tarjeta(saldo):
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "📋 Saldo en Spot\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💵 Moneda: USDT\n"
        f"📈 Disponible: {saldo:.2f}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🕓 Consulta en tiempo real\n"
        "━━━━━━━━━━━━━━━━━━"
    )

# Obtener saldo disponible en USDT
async def obtener_saldo_usdt():
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()

    headers = {
        'X-BX-APIKEY': API_KEY
    }

    url = f"https://open-api.bingx.com/openApi/spot/v1/account/balance?{query_string}&signature={signature}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                balances = data.get('data', {}).get('balances', [])
                for balance in balances:
                    if balance['asset'] == 'USDT':
                        return float(balance['free'])
                return 0.0
            else:
                return 0.0

# Comando /start
@dp.message(commands=["start"])
async def start_handler(message: types.Message):
    await message.answer("👋 ¡Bienvenido a ZafroBot!\nEnvía /saldo para consultar tu saldo disponible en USDT.")

# Comando /saldo
@dp.message(commands=["saldo"])
async def saldo_handler(message: types.Message):
    saldo = await obtener_saldo_usdt()
    respuesta = formatear_tarjeta(saldo)
    await message.answer(respuesta)

# Función principal
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())