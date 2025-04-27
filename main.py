import asyncio
import base64
import hmac
import time
import hashlib
import json
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import os

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

# Inicializar bot de Telegram
bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(bot=bot)

# Pares a escanear
PAIRS = ["SEI-USDT", "ACH-USDT", "CVC-USDT"]

# Parámetros de operación
STOP_LOSS_PERCENT = 2
TAKE_PROFIT_PERCENT = 1.5
OPERATING = False

# Función para enviar notificaciones
async def notify(message):
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

# Función para firmar solicitud
def sign_request(endpoint, method="GET", body=""):
    now = int(time.time() * 1000)
    str_to_sign = str(now) + method + endpoint + body
    signature = base64.b64encode(
        hmac.new(SECRET_KEY.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest()
    ).decode()
    passphrase = base64.b64encode(
        hmac.new(SECRET_KEY.encode('utf-8'), API_PASSPHRASE.encode('utf-8'), hashlib.sha256).digest()
    ).decode()
    headers = {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": str(now),
        "KC-API-PASSPHRASE": passphrase,
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }
    return headers

# Obtener balance en USDT
async def get_balance():
    url = "https://api.kucoin.com/api/v1/accounts"
    headers = sign_request("/api/v1/accounts")
    response = requests.get(url, headers=headers)
    data = response.json()
    for account in data["data"]:
        if account["currency"] == "USDT" and account["type"] == "trade":
            return float(account["available"])
    return 0.0

# Abrir operación
async def open_trade(pair):
    global OPERATING
    balance = await get_balance()
    if balance < 5:
        await notify("⚠️ No tienes saldo suficiente para operar.")
        return

    url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={pair}"
    response = requests.get(url)
    data = response.json()
    price = float(data["data"]["price"])
    quantity = round((balance * 0.98) / price, 6)

    endpoint = "/api/v1/orders"
    url = "https://api.kucoin.com" + endpoint
    order = {
        "clientOid": str(int(time.time() * 1000)),
        "side": "buy",
        "symbol": pair,
        "type": "market",
        "funds": str(balance * 0.98)
    }
    headers = sign_request(endpoint, method="POST", body=json.dumps(order))
    response = requests.post(url, headers=headers, json=order)
    if response.status_code == 200:
        OPERATING = True
        await notify(f"✅ Compra realizada en {pair} a {price} USDT.\nCantidad: {quantity}")
        await monitor_trade(pair, price, quantity)
    else:
        await notify("❌ Error al realizar compra.")
        OPERATING = False

# Monitorear y cerrar operación
async def monitor_trade(pair, buy_price, quantity):
    global OPERATING
    while OPERATING:
        url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={pair}"
        response = requests.get(url)
        data = response.json()
        current_price = float(data["data"]["price"])

        profit_percent = ((current_price - buy_price) / buy_price) * 100

        if profit_percent >= TAKE_PROFIT_PERCENT or profit_percent <= -STOP_LOSS_PERCENT:
            endpoint = "/api/v1/orders"
            url = "https://api.kucoin.com" + endpoint
            order = {
                "clientOid": str(int(time.time() * 1000)),
                "side": "sell",
                "symbol": pair,
                "type": "market",
                "size": str(quantity)
            }
            headers = sign_request(endpoint, method="POST", body=json.dumps(order))
            response = requests.post(url, headers=headers, json=order)
            if response.status_code == 200:
                await notify(f"✅ Venta realizada en {pair} a {current_price} USDT.")
            else:
                await notify("❌ Error al realizar venta.")
            OPERATING = False
        await asyncio.sleep(5)

# Escaneo de mercado
async def scan_market():
    global OPERATING
    while True:
        if not OPERATING:
            for pair in PAIRS:
                await open_trade(pair)
                await asyncio.sleep(2)
        await asyncio.sleep(3)

# Función principal
async def main():
    asyncio.create_task(scan_market())
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())