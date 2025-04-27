import os
import asyncio
import time
import base64
import hmac
import hashlib
import json
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

trading_pairs = ["SEI-USDT", "CVC-USDT", "CUC-USDT"]
TRADE_AMOUNT_PERCENTAGE = 0.80  # 80% del saldo disponible
TAKE_PROFIT_PERCENTAGE = 0.015  # 1.5%
STOP_LOSS_PERCENTAGE = 0.02     # 2%
TRADE_INTERVAL = 5  # segundos entre cada revisión

base_url = "https://api.kucoin.com"

async def kucoin_request(method, endpoint, params=None):
    now = int(time.time() * 1000)
    str_to_sign = str(now) + method + endpoint
    if params and method == 'GET':
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        str_to_sign += '?' + query_string
    elif params:
        str_to_sign += json.dumps(params)

    signature = base64.b64encode(
        hmac.new(API_SECRET.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest()
    ).decode()

    headers = {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": str(now),
        "KC-API-PASSPHRASE": os.getenv('PASSPHRASE'),
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        url = base_url + endpoint
        if method == 'GET':
            async with session.get(url, headers=headers, params=params) as response:
                return await response.json()
        elif method == 'POST':
            async with session.post(url, headers=headers, json=params) as response:
                return await response.json()

async def get_balance():
    data = await kucoin_request('GET', '/api/v1/accounts', params={"type": "trade"})
    for asset in data.get('data', []):
        if asset['currency'] == 'USDT':
            return float(asset['available'])
    return 0.0

async def open_trade(symbol):
    balance = await get_balance()
    if balance <= 1:
        return

    trade_amount = balance * TRADE_AMOUNT_PERCENTAGE
    price_data = await kucoin_request('GET', '/api/v1/market/orderbook/level1', params={"symbol": symbol})
    price = float(price_data['data']['price'])
    quantity = round(trade_amount / price, 4)

    # Crear orden de compra a mercado
    order = {
        "clientOid": str(int(time.time() * 1000)),
        "side": "buy",
        "symbol": symbol,
        "type": "market",
        "size": quantity
    }
    await kucoin_request('POST', '/api/v1/orders', params=order)

    await bot.send_message(CHAT_ID, f"✅ Compra realizada en {symbol}\nMonto: {trade_amount:.2f} USDT")

    await manage_trade(symbol, price, quantity)

async def manage_trade(symbol, buy_price, quantity):
    while True:
        price_data = await kucoin_request('GET', '/api/v1/market/orderbook/level1', params={"symbol": symbol})
        current_price = float(price_data['data']['price'])

        if current_price >= buy_price * (1 + TAKE_PROFIT_PERCENTAGE):
            await sell_trade(symbol, quantity)
            await bot.send_message(CHAT_ID, f"✅ Venta con GANANCIA en {symbol}\nPrecio: {current_price:.4f}")
            break
        elif current_price <= buy_price * (1 - STOP_LOSS_PERCENTAGE):
            await sell_trade(symbol, quantity)
            await bot.send_message(CHAT_ID, f"⚠️ Venta con PÉRDIDA controlada en {symbol}\nPrecio: {current_price:.4f}")
            break

        await asyncio.sleep(5)

async def sell_trade(symbol, quantity):
    order = {
        "clientOid": str(int(time.time() * 1000)),
        "side": "sell",
        "symbol": symbol,
        "type": "market",
        "size": quantity
    }
    await kucoin_request('POST', '/api/v1/orders', params=order)

async def bot_main():
    await bot.send_message(CHAT_ID, "🚀 ZafroBot Scalper PRO v1 iniciado y listo para operar en KuCoin.")

    while True:
        await asyncio.sleep(TRADE_INTERVAL)
        await open_trade(select_best_pair())

def select_best_pair():
    return trading_pairs[int(time.time()) % len(trading_pairs)]

if __name__ == "__main__":
    asyncio.run(bot_main())