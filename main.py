# main.py

import os
import asyncio
import logging
import random
import numpy as np
import datetime
from decimal import Decimal, ROUND_DOWN
from kucoin.client import Market, Trade
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Configuración de logging
logging.basicConfig(level=logging.INFO)

# ─── Variables de Entorno ─────────────────────────────────────
API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID        = int(os.getenv("CHAT_ID", 0))

# ─── Inicializar clientes ─────────────────────────────────────
market = Market(api_key=API_KEY, api_secret=API_SECRET, passphrase=API_PASSPHRASE)
trade  = Trade(api_key=API_KEY, api_secret=API_SECRET, passphrase=API_PASSPHRASE)

# ─── Inicializar Telegram ──────────────────────────────────────
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ─── Variables Globales ────────────────────────────────────────
bot_encendido = False
pares = ["PEPE/USDT", "FLOKI/USDT", "SHIB/USDT", "DOGE/USDT"]

operacion_activa = None
saldo_inicial = 0
ganancia_total_hoy = 0
historial_operaciones = []
modelo_predictor = None
volumen_anterior = {}

# ─── Configuraciones mínimas ───────────────────────────────────
minimos_por_par = {
    "PEPE/USDT": {"min_cantidad": 100000, "decimales": 0},
    "FLOKI/USDT": {"min_cantidad": 100000, "decimales": 0},
    "SHIB/USDT": {"min_cantidad": 10000, "decimales": 0},
    "DOGE/USDT": {"min_cantidad": 1, "decimales": 2},
}

# ─── Teclado en Telegram ───────────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="📈 Estado de Orden Actual")],
    ],
    resize_keyboard=True,
)# ─── Funciones ─────────────────────────────────────────────────

async def obtener_saldo_disponible():
    try:
        cuentas = trade.get_accounts()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                saldo = float(cuenta['available'])
                return saldo
        return 0.0
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return 0.0

async def analizar_mercado():
    mejor_par = None
    mejor_volumen = 0

    for par in pares:
        try:
            par_kucoin = par.replace("/", "-")
            order_book = market.get_part_order_book_large(par_kucoin, limit=20)
            bids = order_book['bids']
            asks = order_book['asks']

            volumen_total = sum(float(bid[1]) for bid in bids) + sum(float(ask[1]) for ask in asks)

            if volumen_total > mejor_volumen:
                mejor_volumen = volumen_total
                mejor_par = par

        except Exception as e:
            logging.error(f"Error analizando {par}: {e}")

    return mejor_par

def calcular_kelly(win_rate=0.6, reward_risk=1.5):
    kelly_fraction = (win_rate - (1 - win_rate) / reward_risk)
    return max(0.01, min(kelly_fraction, 1.0))

async def enviar_telegram(mensaje):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=mensaje)
    except Exception as e:
        logging.error(f"Error enviando mensaje: {e}")

async def comprar(par, usdt_amount):
    try:
        par_kucoin = par.replace("/", "-")
        price_info = market.get_ticker(par_kucoin)
        precio_actual = float(price_info['price'])

        decimals = minimos_por_par[par]['decimales']
        cantidad = Decimal(usdt_amount / precio_actual).quantize(Decimal(10) ** -decimals, rounding=ROUND_DOWN)

        if float(cantidad) < minimos_por_par[par]["min_cantidad"]:
            cantidad = Decimal(minimos_por_par[par]["min_cantidad"])

        orden = trade.create_market_order(
            symbol=par_kucoin,
            side="buy",
            size=str(cantidad)
        )
        return orden

    except Exception as e:
        logging.error(f"Error en compra: {e}")
        return Noneasync def vender(par, cantidad):
    try:
        par_kucoin = par.replace("/", "-")

        orden = trade.create_market_order(
            symbol=par_kucoin,
            side="sell",
            size=str(cantidad)
        )
        return orden

    except Exception as e:
        logging.error(f"Error en venta: {e}")
        return None

async def estrategia_trading():
    global bot_encendido, operacion_activa, operaciones_hoy, ganancia_total_hoy, _last_balance

    while bot_encendido:
        try:
            saldo_disponible = await obtener_saldo_disponible()
            _last_balance = saldo_disponible

            mejor_par = await analizar_mercado()

            if mejor_par:
                kelly = calcular_kelly()
                usdt_para_invertir = saldo_disponible * kelly

                # Garantizamos monto mínimo para el par
                if usdt_para_invertir < 1:
                    usdt_para_invertir = 1

                logging.info(f"Invirtiendo {usdt_para_invertir:.2f} USDT en {mejor_par}")

                orden_compra = await comprar(mejor_par, usdt_para_invertir)

                if orden_compra:
                    operacion_activa = mejor_par
                    await enviar_telegram(f"✅ Compra ejecutada en {mejor_par}")

                    # Esperamos unos segundos para permitir subida de precio
                    await asyncio.sleep(random.randint(5, 10))

                    # Ahora buscamos vender con ganancia
                    precio_compra = float(orden_compra['dealFunds']) / float(orden_compra['dealSize'])
                    target_ganancia = precio_compra * random.uniform(1.02, 1.06)

                    while True:
                        ticker = market.get_ticker(mejor_par.replace("/", "-"))
                        precio_actual = float(ticker['price'])

                        if precio_actual >= target_ganancia:
                            cantidad = orden_compra['dealSize']
                            orden_venta = await vender(mejor_par, cantidad)

                            if orden_venta:
                                ganancia = (precio_actual - precio_compra) * float(cantidad)
                                operaciones_hoy += 1
                                ganancia_total_hoy += ganancia

                                await enviar_telegram(f"✅ Venta realizada en {mejor_par} con ganancia de {ganancia:.4f} USDT")
                            break

                        await asyncio.sleep(2)

                operacion_activa = None
                await asyncio.sleep(2)

            else:
                logging.info("No se encontró oportunidad, esperando...")
                await asyncio.sleep(2)

        except Exception as e:
            logging.error(f"Error en estrategia_trading: {e}")
            await asyncio.sleep(5)# ─── Cálculo de Kelly ───────────────────────────────────────────────────────

def calcular_kelly():
    win_rate = 0.7    # Probabilidad de éxito estimada
    reward_risk = 1.5 # Relación recompensa / riesgo
    kelly = (win_rate * (reward_risk + 1) - 1) / reward_risk
    return max(0.01, min(kelly, 0.5))  # Lo limitamos entre 1% y 50%

# ─── Inicializar Entrenamiento del Modelo ────────────────────────────────────

def entrenar_modelo():
    global modelo_predictor, historico_en_memoria

    X = []
    y = []

    for entrada in historico_en_memoria:
        X.append([entrada['precio'], entrada['volumen']])
        y.append(entrada['sube'])

    if len(X) < 10:
        return None

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    modelo = RandomForestClassifier(n_estimators=100)
    modelo.fit(X_train, y_train)

    predicciones = modelo.predict(X_test)
    acc = accuracy_score(y_test, predicciones)
    logging.info(f"Entrenamiento modelo: Accuracy {acc:.2f}")

    return modelo

# ─── Comandos de Telegram ────────────────────────────────────────────────────

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("¡Hola! Soy el ZafroBot Scalper Pro V1.")

@dp.message()
async def command_handler(message: types.Message):
    global bot_encendido

    if message.text == "🚀 Encender Bot":
        bot_encendido = True
        await message.answer("✅ Bot encendido.", reply_markup=keyboard)
        asyncio.create_task(estrategia_trading())

    elif message.text == "🛑 Apagar Bot":
        bot_encendido = False
        await message.answer("🛑 Bot apagado.", reply_markup=keyboard)

    elif message.text == "📊 Estado del Bot":
        estado = "Encendido" if bot_encendido else "Apagado"
        await message.answer(f"Estado del bot: {estado}\nOperaciones hoy: {operaciones_hoy}\nGanancia hoy: {ganancia_total_hoy:.2f} USDT", reply_markup=keyboard)

    elif message.text == "💰 Actualizar Saldo":
        saldo = await obtener_saldo_disponible()
        await message.answer(f"💰 Saldo disponible: {saldo:.2f} USDT", reply_markup=keyboard)

    elif message.text == "📈 Estado de Orden Actual":
        if operacion_activa:
            await message.answer(f"Operación activa en {operacion_activa}", reply_markup=keyboard)
        else:
            await message.answer("No hay operación activa.", reply_markup=keyboard)# ─── Función Principal ──────────────────────────────────────────────────────

async def main():
    await dp.start_polling(bot)

# ─── Arranque del Bot ────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(main())