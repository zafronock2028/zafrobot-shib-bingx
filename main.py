import os
import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from kucoin.client import Client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logs
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASS = os.getenv("API_PASSPHRASE")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Inicialización del cliente KuCoin (versión 1.0.26)
kucoin_client = Client(
    API_KEY,
    SECRET_KEY,
    API_PASS
)

bot = Bot(token=TOKEN, parse_mode="Markdown")
dp = Dispatcher()

# [Resto del código IDÉNTICO al que tenías originalmente]
# Solo cambia las llamadas a:
# market.get_kline() → kucoin_client.get_kline()
# trade.create_market_order() → kucoin_client.create_market_order()
# user.get_account_list() → kucoin_client.get_accounts()