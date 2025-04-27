import asyncio
import time
import hmac
import hashlib
import base64
import json
import requests
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
import os

load_dotenv()

# Configuración
API_KEY = os.getenv("KUCOIN_API_KEY")
API_SECRET = os.getenv("KUCOIN_API_SECRET")
API_PASSPHRASE = os.getenv("KUCOIN_API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

PAIRS = ["SEI-USDT", "ACH-USDT", "CVC-USDT"]
TAKE_PROFIT_PERCENT = 0.015  # 1.5%
STOP_LOSS_PERCENT = 0.01     # 1%

BASE_URL = "https://api.kucoin.com"

bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

async def send_telegram(message):
    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")

def get_headers(endpoint, method="GET", body=""):
    now = int(time.time() * 1000)
    str_to_sign = str(now) + method + endpoint + body
    signature = base64.b64encode(
        hmac.new(API_SECRET.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest()
    ).decode()

    passphrase = base64.b64encode(
        hmac.new(API_SECRET.encode('utf-8'), API_PASSPHRASE.encode('utf-8'), hashlib.sha256).digest()
    ).decode()

    return {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": str(now),
        "KC-API-PASSPHRASE": passphrase,
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }

async def get_balance():
    endpoint = "/api/v1/accounts?type=trade"
    headers = get_headers(endpoint)
    response = requests.get(BASE_URL + endpoint, headers=headers)
    balances = response.json()["data"]
    for asset in balances:
        if asset["currency"] == "USDT":
            return float(asset["available"])
    return 0.0

async def open_trade(pair):
    balance = await get_balance()
    if balance < 5:
        await send_telegram("⚠️ No tienes saldo suficiente para operar.")
        return

    order_size = round(balance * 0.98, 2)  # Usamos 98% del saldo disponible

    # Crear orden de compra a mercado
    endpoint = "/api/v1/orders"
    body = json.dumps({
        "symbol": pair,
        "side": "buy",
        "type": "market",
        "funds": str(order_size)
    })
    headers = get_headers(endpoint, method="POST", body=body)
    response = requests.post(BASE_URL + endpoint, headers=headers, data=body)
    data = response.json()
    
    if data.get("code") == "200000":
        await send_telegram(f"✅ COMPRA realizada en {pair}")
        await monitor_trade(pair)
    else:
        await send_telegram(f"❌ Error al comprar {pair}: {data.get('msg', 'Error desconocido')}")

async def monitor_trade(pair):
    await asyncio.sleep(3)  # Simulación para el monitoreo
    # Luego aquí pondremos una simulación de venta:
    await close_trade(pair)

async def close_trade(pair):
    # Crear orden de venta a mercado
    endpoint = "/api/v1/orders"
    body = json.dumps({
        "symbol": pair,
        "side": "sell",
        "type": "market",
        "size": "100%"  # Puedes ajustar esto si necesitas
    })
    headers = get_headers(endpoint, method="POST", body=body)
    response = requests.post(BASE_URL + endpoint, headers=headers, data=body)
    data = response.json()

    if data.get("code") == "200000":
        await send_telegram(f"✅ VENTA realizada en {pair}")
    else:
        await send_telegram(f"❌ Error al vender {pair}: {data.get('msg', 'Error desconocido')}")

async def main():
    while True:
        for pair in PAIRS:
            await open_trade(pair)
            await asyncio.sleep(60)  # Espera 1 minuto entre operaciones
        await asyncio.sleep(60)  # Cada ciclo total espera 1 minuto antes de repetir

if __name__ == "__main__":
    asyncio.run(main())