import os
import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from kucoin.client import Trade, Market, User  # Importación corregida
from dotenv import load_dotenv

# Configuración inicial
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASS = os.getenv("API_PASSPHRASE")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Clientes KuCoin (versión 1.0.12)
market = Market(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASS)
trade = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASS)
user = User(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASS)

bot = Bot(token=TOKEN, parse_mode="Markdown")
dp = Dispatcher()

# Variables de estado
bot_activo = False
operaciones = []
historial = []
ultimos_pares = {}
lock = asyncio.Lock()

# Configuración
PARES = ["SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT", "TRUMP-USDT"]
CONFIG = {
    'uso_saldo': 0.8,
    'max_ops': 3,
    'espera_reentrada': 600,
    'ganancia_obj': 0.004,
    'stop_loss': -0.007,
    'min_orden': 2.5,
    'steps': {
        "SHIB-USDT": 0.1, "PEPE-USDT": 0.1, "TRUMP-USDT": 0.01
    }
}

# Teclado
teclado = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="⛔ Apagar Bot")],
        [KeyboardButton(text="💰 Saldo")],
        [KeyboardButton(text="📊 Estado")]
    ],
    resize_keyboard=True
)

# Handlers
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🤖 Bot listo", reply_markup=teclado)

@dp.message()
async def handle_commands(message: types.Message):
    global bot_activo
    if message.text == "🚀 Encender Bot" and not bot_activo:
        bot_activo = True
        asyncio.create_task(run_bot())
        await message.answer("✅ Bot activado")
    elif message.text == "⛔ Apagar Bot":
        bot_activo = False
        await message.answer("🔴 Bot detenido")
    elif message.text == "💰 Saldo":
        saldo = await get_balance()
        await message.answer(f"💰 Saldo: {saldo:.2f} USDT")
    elif message.text == "📊 Estado":
        await message.answer("🟢 Activo" if bot_activo else "🔴 Inactivo")

# Lógica del bot
async def run_bot():
    while bot_activo:
        try:
            async with lock:
                if len(operaciones) >= CONFIG['max_ops']:
                    await asyncio.sleep(3)
                    continue

                balance = await get_balance()
                monto = (balance * CONFIG['uso_saldo']) / CONFIG['max_ops']

                for par in PARES:
                    if not bot_activo:
                        break
                        
                    if par in [op['par'] for op in operaciones]:
                        continue
                        
                    if par in ultimos_pares and (datetime.now() - ultimos_pares[par]).seconds < CONFIG['espera_reentrada']:
                        continue

                    signal = await check_pair(par)
                    if signal['valido']:
                        await execute_trade(par, signal['precio'], monto)
                        await asyncio.sleep(2)
                        break
            
            await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error: {e}")
            await asyncio.sleep(5)

async def check_pair(par):
    try:
        candles = market.get_kline(symbol=par, kline_type="1min", limit=5)
        prices = [float(c[2]) for c in candles]
        last = prices[-1]
        change = (last - prices[-2]) / prices[-2]
        
        if change > 0.001:
            return {'par': par, 'precio': last, 'valido': True}
    except Exception as e:
        logging.error(f"Error analizando {par}: {e}")
    return {'par': par, 'valido': False}

async def execute_trade(par, price, amount):
    try:
        step = Decimal(str(CONFIG['steps'].get(par, 0.0001)))
        size = (Decimal(str(amount)) / Decimal(str(price)) // step) * step
        
        trade.create_market_order(symbol=par, side="buy", size=str(size))
        
        operaciones.append({
            'par': par,
            'entrada': float(price),
            'size': float(size),
            'max': float(price)
        })
        
        await bot.send_message(
            CHAT_ID,
            f"🟢 COMPRA {par}\nPrecio: {price:.6f}\nCantidad: {float(size):.2f}"
        )
        
        asyncio.create_task(monitor_trade(operaciones[-1]))
    except Exception as e:
        logging.error(f"Error en trade {par}: {e}")

async def monitor_trade(trade):
    while trade in operaciones and bot_activo:
        try:
            ticker = market.get_ticker(symbol=trade['par'])
            price = float(ticker['price'])
            
            if price > trade['max']:
                trade['max'] = price
            
            profit = (price - trade['entrada']) / trade['entrada']
            drawdown = (price - trade['max']) / trade['max']
            
            if profit >= CONFIG['ganancia_obj'] or drawdown <= CONFIG['stop_loss']:
                await close_trade(trade)
                break
                
            await asyncio.sleep(3)
        except Exception as e:
            logging.error(f"Error monitoreando {trade['par']}: {e}")
            await asyncio.sleep(5)

async def close_trade(trade):
    try:
        trade_client.create_market_order(
            symbol=trade['par'],
            side="sell",
            size=str(trade['size'])
        )
        
        profit = (trade['max'] - trade['entrada']) * trade['size']
        operaciones.remove(trade)
        ultimos_pares[trade['par']] = datetime.now()
        
        await bot.send_message(
            CHAT_ID,
            f"🔴 VENTA {trade['par']}\nGanancia: {profit:.4f} USDT"
        )
    except Exception as e:
        logging.error(f"Error cerrando trade {trade['par']}: {e}")

async def get_balance():
    try:
        accounts = user.get_account_list()
        usdt = next((a for a in accounts if a['currency'] == 'USDT'), None)
        return float(usdt['available']) if usdt else 0.0
    except Exception as e:
        logging.error(f"Error obteniendo balance: {e}")
        return 0.0

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())