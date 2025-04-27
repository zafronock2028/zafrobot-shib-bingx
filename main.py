import os
import hmac
import base64
import time
import json
import aiohttp
from hashlib import sha256
from aiogram import Bot, Dispatcher, types
from aiogram.enums.parse_mode import ParseMode
import asyncio

# Variables de entorno
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('SECRET_KEY')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

BASE_URL = "https://api.kucoin.com"

# Inicializar el bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Función para enviar mensaje a Telegram
async def send_telegram_message(message):
    await bot.send_message(chat_id=CHAT_ID, text=message)

# Función para hacer peticiones a KuCoin
async def kucoin_request(method, endpoint, payload=None):
    now = int(time.time() * 1000)
    payload_json = json.dumps(payload) if payload else ''
    str_to_sign = f"{now}{method}{endpoint}{payload_json}"
    
    signature = base64.b64encode(
        hmac.new(API_SECRET.encode('utf-8'), str_to_sign.encode('utf-8'), sha256).digest()
    ).decode()
    
    passphrase = base64.b64encode(
        hmac.new(API_SECRET.encode('utf-8'), API_PASSPHRASE.encode('utf-8'), sha256).digest()
    ).decode()

    headers = {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": str(now),
        "KC-API-PASSPHRASE": passphrase,
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        url = BASE_URL + endpoint
        if method == "GET":
            async with session.get(url, headers=headers) as response:
                return await response.json()
        elif method == "POST":
            async with session.post(url, headers=headers, data=payload_json) as response:
                return await response.json()

# Función para consultar el saldo disponible en USDT
async def get_balance():
    try:
        response = await kucoin_request("GET", "/api/v1/accounts")
        for account in response.get('data', []):
            if account['currency'] == 'USDT' and account['type'] == 'trade':
                return float(account['available'])
    except Exception as e:
        await send_telegram_message(f"Error obteniendo balance: {e}")
    return 0.0

# Función para abrir una operación de compra
async def open_trade(symbol):
    balance = await get_balance()
    if balance <= 0:
        await send_telegram_message("No hay saldo disponible para operar.")
        return
    
    # Usamos 95% del saldo para cada operación
    usdt_to_spend = balance * 0.95

    order = {
        "clientOid": str(int(time.time() * 1000)),
        "side": "buy",
        "symbol": symbol,
        "type": "market",
        "funds": str(usdt_to_spend)
    }
    try:
        response = await kucoin_request("POST", "/api/v1/orders", order)
        if response.get('code') == "200000":
            await send_telegram_message(f"¡Compra realizada en {symbol}!")
        else:
            await send_telegram_message(f"Error al comprar {symbol}: {response}")
    except Exception as e:
        await send_telegram_message(f"Error abriendo operación: {e}")

# Función principal para escanear y operar
async def main_loop():
    symbols = ["SEI-USDT", "ACH-USDT", "CVC-USDT"]

    while True:
        for symbol in symbols:
            try:
                ticker = await kucoin_request("GET", f"/api/v1/market/orderbook/level1?symbol={symbol}")
                price = float(ticker['data']['price'])
                
                # Aquí puedes agregar tus condiciones de scalping para comprar/vender
                if price > 0:  # De momento solo validamos precio válido
                    await open_trade(symbol)
                    
                    # Luego de abrir una operación, esperamos 30 segundos antes de volver a escanear
                    await asyncio.sleep(30)
            except Exception as e:
                await send_telegram_message(f"Error analizando {symbol}: {e}")

        await asyncio.sleep(10)  # Tiempo entre cada ciclo de escaneo

# Ejecución
async def start_bot():
    await send_telegram_message("✅ ZafroBot Scalper PRO v1 iniciado correctamente.")
    await main_loop()

if __name__ == "__main__":
    asyncio.run(start_bot())