import os
import asyncio
import logging
from kucoin.client import Client
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram import F

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Credenciales API de KuCoin
API_KEY = os.getenv("KUCOIN_API_KEY")
API_SECRET = os.getenv("KUCOIN_API_SECRET")
API_PASSPHRASE = os.getenv("KUCOIN_API_PASSPHRASE")

# Bot de Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot=bot)

# Inicializar cliente de KuCoin
client = Client(API_KEY, API_SECRET, API_PASSPHRASE)

# Parámetros de trading
PAIR_LIST = ["SEI-USDT", "ACH-USDT", "CVC-USDT"]
TAKE_PROFIT_PERCENTAGE = 0.02  # 2%
STOP_LOSS_PERCENTAGE = 0.01    # 1%

# Estado de operaciones
open_trade_info = None

async def get_balance():
    account_list = client.get_accounts()
    usdt_balance = next((float(acc['available']) for acc in account_list if acc['currency'] == 'USDT' and acc['type'] == 'trade'), 0)
    return usdt_balance

async def open_trade(symbol):
    global open_trade_info

    balance = await get_balance()
    if balance < 5:
        logging.info(f"No hay suficiente saldo USDT para abrir operación. Saldo: {balance}")
        return

    quantity = round((balance * 0.95), 2)
    if quantity <= 0:
        logging.info("Cantidad a comprar no válida.")
        return

    # Ejecutar compra a mercado
    order = client.create_market_order(symbol=symbol, side="buy", size=str(quantity))
    logging.info(f"Compra realizada en {symbol} con {quantity} USDT.")
    await bot.send_message(CHAT_ID, f"✅ Compra realizada en <b>{symbol}</b> con <b>{quantity} USDT</b>.")

    open_trade_info = {
        "symbol": symbol,
        "buy_price": float(order['dealFunds']) / float(order['dealSize']),
        "quantity": float(order['dealSize'])
    }

async def close_trade():
    global open_trade_info

    if not open_trade_info:
        return

    symbol = open_trade_info["symbol"]
    quantity = open_trade_info["quantity"]

    # Ejecutar venta a mercado
    client.create_market_order(symbol=symbol, side="sell", size=str(quantity))
    logging.info(f"Venta realizada en {symbol} de {quantity} unidades.")
    await bot.send_message(CHAT_ID, f"✅ Venta realizada en <b>{symbol}</b> de <b>{quantity}</b> unidades.")

    open_trade_info = None

async def monitor_market():
    while True:
        try:
            if not open_trade_info:
                # No hay operaciones abiertas, buscar oportunidad
                for pair in PAIR_LIST:
                    candles = client.get_kline_data(symbol=pair, kline_type="1min", limit=3)
                    if len(candles) >= 2:
                        last_close = float(candles[-1][2])
                        prev_close = float(candles[-2][2])
                        if last_close > prev_close * 1.003:  # Detecta mini impulso
                            await open_trade(pair)
                            break
            else:
                # Hay operación abierta, gestionar salida
                current_price = float(client.get_ticker(open_trade_info["symbol"])["price"])
                entry_price = open_trade_info["buy_price"]

                if current_price >= entry_price * (1 + TAKE_PROFIT_PERCENTAGE):
                    await close_trade()
                elif current_price <= entry_price * (1 - STOP_LOSS_PERCENTAGE):
                    await close_trade()

            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"Error monitoreando el mercado: {e}")
            await asyncio.sleep(10)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("🤖 ¡ZafroBot Scalper PRO v1 listo para operar en KuCoin!")

async def main():
    asyncio.create_task(monitor_market())
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())