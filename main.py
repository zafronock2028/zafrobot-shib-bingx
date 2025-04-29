# main.py
import os
import asyncio
import logging
import datetime
import random
from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import numpy as np

# ─── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

# ─── Configuración ─────────────────────────────────────────────────────────
API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID        = int(os.getenv("CHAT_ID", 0))

# ─── Cliente de KuCoin ─────────────────────────────────────────────────────
kucoin = Client(API_KEY, API_SECRET, API_PASSPHRASE)

# ─── Cliente de Telegram ───────────────────────────────────────────────────
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ─── Variables Globales ────────────────────────────────────────────────────
_last_balance: float = 0.0
bot_encendido = False
pares = ["PEPE/USDT", "FLOKI/USDT", "SHIB/USDT", "DOGE/USDT"]

operacion_activa = None
operaciones_hoy = 0
ganancia_total_hoy = 0.0
historial_operaciones = []
volumen_anterior = {}
historico_en_memoria = []
modelo_predictor = None