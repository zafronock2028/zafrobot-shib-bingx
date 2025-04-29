# main.py
import os
import asyncio
import logging
import datetime
import random
import numpy as np
from decimal import Decimal, ROUND_DOWN
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

# ─── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

# ─── Cargar configuración ─────────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

# ─── Clientes ─────────────────────────────────────────────────────────────
kucoin = Client(API_KEY, API_SECRET, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ─── Variables Globales ───────────────────────────────────────────────────
bot_encendido = False
operacion_activa = None
pares = ["PEPE/USDT", "FLOKI/USDT", "SHIB/USDT", "DOGE/USDT"]
operaciones_hoy = 0
ganancia_total_hoy = 0.0
historial_operaciones = []
volumen_anterior = {}
historico_en_memoria = []
modelo_predictor = None

# ─── Reglas de tamaño mínimo KuCoin ───────────────────────────────────────
minimos_por_par = {
    "PEPE/USDT": {"min_cantidad": 100000, "decimales": 0},
    "FLOKI/USDT": {"min_cantidad": 100000, "decimales": 0},
    "SHIB/USDT": {"min_cantidad": 10000, "decimales": 0},
    "DOGE/USDT": {"min_cantidad": 1, "decimales": 2},
}

# ─── Teclado Telegram ─────────────────────────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="📈 Estado de Orden Actual")],
    ],
    resize_keyboard=True,
)