import asyncio
import aiohttp
import hmac
import hashlib
import time
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
CHAT_ID = os.getenv('CHAT_ID')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Pares que se van a escanear
PAIRS = ["SEIUSDT", "OPUSDT", "SUIUSDT"]

# Configuraciones de trading
TAKE_PROFIT_PERCENT = 2.5
STOP_LOSS_PERCENT = 2.5
TRADE_PERCENTAGE = 0.8  # 80% del saldo disponible

# Crear bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Estado del bot
operation_open = False

async def get_balance():
    url = "https://api.kucoin.com/api/v1/accounts"
    timestamp = str(int(time.time() * 1000))
    method = 'GET'
    endpoint = "/api/v1/accounts"
    payload = ''
    str_to_sign = str(timestamp) + method + endpoint + payload
    signature = hmac.new(SECRET_KEY.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest()
    signature_b64 = base64.b64encode(signature).decode()

    headers = {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature_b64,
        "KC-API-TIMESTAMP": timestamp,
        "KC-API-PASSPHRASE": "",  # No usamos passphrase en esta versión
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json()
            if data.get("code") == "200000":
                for balance in data["data"]:
                    if balance["currency"] == "USDT" and balance["type"] == "trade":
                        return float(balance["available"])
    return 0.0

async def send_telegram_message(text):
    await bot.send_message(chat_id=CHAT_ID, text=text)

async def scan_market():
    global operation_open
    while True:
        if not operation_open:
            for pair in PAIRS:
                if await check_entry(pair):
                    await open_trade(pair)
                    break
        await asyncio.sleep(60)

async def check_entry(pair):
    # Aquí pondrías tu análisis real
    return True  # Temporal, para prueba

async def open_trade(pair):
    global operation_open
    balance = await get_balance()
    if balance <= 0:
        await send_telegram_message("❌ No hay saldo suficiente para operar.")
        return

    usdt_amount = balance * TRADE_PERCENTAGE
    await send_telegram_message(f"🟢 Abriendo operación en {pair} con {usdt_amount:.2f} USDT.")

    # Simular compra
    operation_open = True

    # Simular ganancia o pérdida después de un tiempo
    await asyncio.sleep(60)  # 1 minuto simulado de operación

    # Simular cierre
    await close_trade(pair, usdt_amount)

async def close_trade(pair, usdt_amount):
    global operation_open
    # Simulación: suponemos ganancia
    gain = usdt_amount * (TAKE_PROFIT_PERCENT / 100)
    await send_telegram_message(f"✅ Cerrada operación en {pair} con ganancia de {gain:.2f} USDT.")
    operation_open = False

@dp.message(Command(commands=["start"]))
async def start_bot(message: types.Message):
    await message.answer("🤖 ZafroBot Scalper PRO v2 iniciado correctamente. ¡Listo para trabajar!")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(scan_market())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())