import os
import time
import hmac
import hashlib
import base64
import json
import aiohttp
import asyncio
from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand
from aiogram.enums import ParseMode

# Variables de entorno
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Parámetros de Trading
PAIRS = ["SEI-USDT", "ACH-USDT", "CVC-USDT"]
TRADE_PERCENTAGE = 0.95  # Usa el 95% del balance disponible
TAKE_PROFIT_PERCENT = 1.8  # 1.8% de ganancia
STOP_LOSS_PERCENT = 1.2    # 1.2% de pérdida máxima

# Inicializar bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=BotCommand)
dp = Dispatcher(bot=bot)

# Cliente de KuCoin
client = Client(API_KEY, API_SECRET, API_PASSPHRASE)

async def enviar_mensaje(mensaje):
    await bot.send_message(chat_id=CHAT_ID, text=mensaje, parse_mode=ParseMode.HTML)

async def obtener_balance_usdt():
    accounts = await client.get_accounts()
    for account in accounts:
        if account['currency'] == 'USDT' and account['type'] == 'trade':
            return float(account['available'])
    return 0.0

async def analizar_par(par):
    ticker = await client.get_ticker(par)
    last_price = float(ticker['price'])
    return last_price

async def abrir_operacion(par):
    balance = await obtener_balance_usdt()
    if balance < 5:
        await enviar_mensaje("❌ Saldo insuficiente para operar.")
        return

    precio_compra = await analizar_par(par)
    cantidad = (balance * TRADE_PERCENTAGE) / precio_compra

    try:
        order = await client.create_market_order(par, 'buy', size=round(cantidad, 4))
        await enviar_mensaje(f"✅ Compra realizada en {par} a precio de mercado: {precio_compra:.4f} USDT")

        await monitorear_operacion(par, precio_compra)

    except Exception as e:
        await enviar_mensaje(f"⚠️ Error al abrir operación: {str(e)}")

async def monitorear_operacion(par, precio_entrada):
    take_profit = precio_entrada * (1 + TAKE_PROFIT_PERCENT / 100)
    stop_loss = precio_entrada * (1 - STOP_LOSS_PERCENT / 100)

    while True:
        precio_actual = await analizar_par(par)
        
        if precio_actual >= take_profit:
            balance = await obtener_balance_par(par)
            if balance > 0:
                await client.create_market_order(par, 'sell', size=balance)
                await enviar_mensaje(f"✅ ¡Take Profit alcanzado! Vendido {par} a {precio_actual:.4f} USDT")
            break

        if precio_actual <= stop_loss:
            balance = await obtener_balance_par(par)
            if balance > 0:
                await client.create_market_order(par, 'sell', size=balance)
                await enviar_mensaje(f"⚠️ Stop Loss activado. Vendido {par} a {precio_actual:.4f} USDT")
            break

        await asyncio.sleep(10)

async def obtener_balance_par(par):
    symbol = par.split("-")[0]
    accounts = await client.get_accounts()
    for account in accounts:
        if account['currency'] == symbol and account['type'] == 'trade':
            return float(account['available'])
    return 0.0

async def main():
    await enviar_mensaje("🚀 ZafroBot Scalper PRO v1 ha iniciado correctamente.")

    while True:
        for par in PAIRS:
            await abrir_operacion(par)
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())