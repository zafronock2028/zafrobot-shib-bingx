import os
import time
import asyncio
import base64
import hmac
import hashlib
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.utils import executor

# Cargar las variables de entorno
load_dotenv()

KUCOIN_API_KEY = os.getenv('KUCOIN_API_KEY')
KUCOIN_API_SECRET = os.getenv('KUCOIN_API_SECRET')
KUCOIN_API_PASSPHRASE = os.getenv('KUCOIN_API_PASSPHRASE')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

client = Client(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE)
bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot)

# Configuración
pairs_to_trade = ["SEI-USDT", "ACH-USDT", "CVC-USDT"]
profit_target = 1.5 / 100  # 1.5% Take Profit
stop_loss_threshold = 2 / 100  # 2% Stop Loss
investment_percentage = 0.95  # 95% del saldo disponible

is_in_trade = False  # Variable para controlar operaciones activas

async def send_telegram_message(message):
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

async def get_balance():
    usdt_balance = client.get_currency_balance('USDT')
    return float(usdt_balance['available'])

async def get_price(pair):
    ticker = client.get_ticker(pair)
    return float(ticker['price'])

async def open_trade(pair):
    global is_in_trade
    balance = await get_balance()
    amount_to_spend = balance * investment_percentage

    if amount_to_spend < 5:  # KuCoin mínimo de $5
        await send_telegram_message("⚠️ No hay suficiente saldo para abrir operación.")
        return

    price = await get_price(pair)
    size = round(amount_to_spend / price, 6)

    try:
        order = client.create_market_order(pair, 'buy', size=size)
        await send_telegram_message(f"✅ Compra ejecutada: {pair} - Cantidad: {size}")
        is_in_trade = True
        await monitor_trade(pair, size)
    except Exception as e:
        await send_telegram_message(f"⚠️ Error abriendo operación: {e}")

async def monitor_trade(pair, size):
    global is_in_trade
    entry_price = await get_price(pair)
    await send_telegram_message(f"⏳ Monitoreando operación en {pair}...")

    while True:
        await asyncio.sleep(10)
        current_price = await get_price(pair)
        change = (current_price - entry_price) / entry_price

        if change >= profit_target:
            # Tomar ganancia
            try:
                client.create_market_order(pair, 'sell', size=size)
                await send_telegram_message(f"✅ Venta con GANANCIA en {pair} - {round(change*100, 2)}%")
                is_in_trade = False
                break
            except Exception as e:
                await send_telegram_message(f"⚠️ Error vendiendo: {e}")
                break
        elif change <= -stop_loss_threshold:
            # Stop Loss
            try:
                client.create_market_order(pair, 'sell', size=size)
                await send_telegram_message(f"❌ Venta con PÉRDIDA en {pair} - {round(change*100, 2)}%")
                is_in_trade = False
                break
            except Exception as e:
                await send_telegram_message(f"⚠️ Error vendiendo (Stop Loss): {e}")
                break

async def scan_market():
    while True:
        if not is_in_trade:
            best_pair = None
            best_volatility = 0

            for pair in pairs_to_trade:
                try:
                    price_now = await get_price(pair)
                    await asyncio.sleep(1)
                    price_later = await get_price(pair)
                    change = abs(price_later - price_now) / price_now

                    if change > best_volatility:
                        best_volatility = change
                        best_pair = pair
                except Exception as e:
                    await send_telegram_message(f"⚠️ Error analizando {pair}: {e}")

            if best_pair:
                await open_trade(best_pair)
        
        await asyncio.sleep(10)

async def start_bot():
    await send_telegram_message("🚀 ZafroBot Scalper PRO v1 Iniciado.")
    await scan_market()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    executor.start_polling(dp, skip_updates=True)