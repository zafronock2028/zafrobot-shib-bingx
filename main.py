import os
import asyncio
import logging
import requests
from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('SECRET_KEY')
API_PASS = os.getenv('API_PASS')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Configurar el cliente de KuCoin
client = Client(API_KEY, API_SECRET, API_PASS)

# Inicializar bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Parámetros de trading
TRADING_PAIRS = ["SEI-USDT", "ACH-USDT", "SNT-USDT"]  # Pares seleccionados
TRADE_AMOUNT = 15  # Monto en USDT por operación
TAKE_PROFIT_PERCENT = 1.5
STOP_LOSS_PERCENT = 1.0

async def send_telegram_message(message):
    """Enviar mensaje al Telegram"""
    await bot.send_message(chat_id=CHAT_ID, text=message)

async def get_balance():
    """Obtener saldo disponible en USDT"""
    balances = client.get_accounts()
    for balance in balances:
        if balance['currency'] == 'USDT' and balance['type'] == 'trade':
            return float(balance['available'])
    return 0.0

async def open_trade(pair):
    """Abrir una operación de compra"""
    balance = await get_balance()
    if balance < TRADE_AMOUNT:
        await send_telegram_message("⚠️ Saldo insuficiente para operar.")
        return None

    # Precio actual
    ticker = client.get_ticker(pair)
    price = float(ticker['price'])

    quantity = round(TRADE_AMOUNT / price, 4)

    try:
        order = client.create_market_order(
            symbol=pair,
            side="buy",
            size=quantity
        )
        await send_telegram_message(f"✅ Compra ejecutada: {quantity} {pair} a {price} USDT.")
        return {"order_id": order['orderId'], "price": price, "quantity": quantity}
    except Exception as e:
        await send_telegram_message(f"❌ Error al comprar: {e}")
        return None

async def close_trade(pair, quantity):
    """Cerrar una operación de venta"""
    try:
        order = client.create_market_order(
            symbol=pair,
            side="sell",
            size=quantity
        )
        await send_telegram_message(f"✅ Venta ejecutada de {quantity} {pair}.")
    except Exception as e:
        await send_telegram_message(f"❌ Error al vender: {e}")

async def monitor_trade(pair, entry_price, quantity):
    """Monitorear operación abierta"""
    while True:
        ticker = client.get_ticker(pair)
        current_price = float(ticker['price'])

        if current_price >= entry_price * (1 + TAKE_PROFIT_PERCENT / 100):
            await close_trade(pair, quantity)
            break
        elif current_price <= entry_price * (1 - STOP_LOSS_PERCENT / 100):
            await close_trade(pair, quantity)
            break

        await asyncio.sleep(5)  # Esperar 5 segundos antes de volver a revisar

async def trading_cycle():
    """Ciclo de trading principal"""
    while True:
        for pair in TRADING_PAIRS:
            trade = await open_trade(pair)
            if trade:
                await monitor_trade(pair, trade['price'], trade['quantity'])
        await asyncio.sleep(5)

async def main():
    """Inicializar el bot"""
    logging.basicConfig(level=logging.INFO)
    await send_telegram_message("🤖 ZafroBot Scalper PRO v1 iniciado.")
    await trading_cycle()

if __name__ == "__main__":
    asyncio.run(main())