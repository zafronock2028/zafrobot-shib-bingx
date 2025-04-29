# main.py

import os
import asyncio
import logging
import datetime
import random
import numpy as np
from decimal import Decimal, ROUND_DOWN
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from kucoin.client import Client

# ─── Configuración de Logging ─────────────────────────────────────
logging.basicConfig(level=logging.INFO)

# ─── Credenciales desde Entorno ───────────────────────────────────
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

# ─── Inicialización de Clientes ───────────────────────────────────
kucoin = Client(API_KEY, API_SECRET, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ─── Variables Globales ────────────────────────────────────────────
bot_encendido = False
operacion_activa = None
operaciones_hoy = 0
ganancia_total_hoy = 0.0
pares = ["PEPE/USDT", "FLOKI/USDT", "SHIB/USDT", "DOGE/USDT"]
historico_en_memoria = []
modelo_predictor = None
volumen_anterior = {}

# ─── Teclado para el Bot de Telegram ───────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="📈 Estado de Orden Actual")],
    ],
    resize_keyboard=True,
)# ─── Funciones Base ─────────────────────────────────────────────────

async def obtener_saldo_disponible():
    """Lee correctamente el saldo en la wallet de Trading de KuCoin (tipo 'trade')."""
    try:
        cuentas = kucoin.get_accounts()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                return float(cuenta['available'])
        return 0.0
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return 0.0

def calcular_kelly(saldo_total, win_rate=0.7, reward_risk=1.5):
    """Calcula el tamaño de la operación basado en Kelly Criterion."""
    kelly_fraction = (win_rate * (reward_risk + 1) - 1) / reward_risk
    kelly_fraction = max(0.01, min(kelly_fraction, 0.5))  # Limitamos entre 1% y 50%
    monto_kelly = saldo_total * kelly_fraction
    return monto_kelly

async def limitar_por_volumen(par, monto_sugerido):
    """Limita el monto máximo basado en el 4% del volumen de 24 horas del par."""
    try:
        ticker = kucoin.get_ticker(symbol=par.replace("/", "-"))
        volumen_usdt_24h = float(ticker.get("volValue", 0))
        limite_maximo = volumen_usdt_24h * 0.04  # 4% del volumen
        return min(monto_sugerido, limite_maximo)
    except Exception as e:
        logging.error(f"Error obteniendo volumen de {par}: {e}")
        return monto_sugerido# ─── Funciones de Compra, Venta y Trailing Stop ─────────────────────────────

async def comprar(par, usdt_monto):
    """Realiza una compra de mercado en el par usando fondos en USDT."""
    try:
        orden = kucoin.create_market_order(
            symbol=par.replace("/", "-"),
            side="buy",
            funds=str(usdt_monto)
        )
        logging.info(f"Compra ejecutada en {par} por {usdt_monto} USDT")
        return orden
    except Exception as e:
        logging.error(f"Error en compra: {e}")
        return None

async def vender(par, cantidad):
    """Vende en mercado una cantidad específica del par."""
    try:
        orden = kucoin.create_market_order(
            symbol=par.replace("/", "-"),
            side="sell",
            size=str(cantidad)
        )
        logging.info(f"Venta ejecutada en {par} con {cantidad} unidades.")
        return orden
    except Exception as e:
        logging.error(f"Error en venta: {e}")
        return None

async def estrategia_operacion(par):
    """Analiza, entra en operación, y maneja Trailing Stop dinámico."""
    global operacion_activa, operaciones_hoy, ganancia_total_hoy

    saldo_disponible = await obtener_saldo_disponible()
    if saldo_disponible < 5:
        logging.warning("Saldo insuficiente para operar.")
        return

    monto_kelly = calcular_kelly(saldo_disponible)
    monto_ajustado = await limitar_por_volumen(par, monto_kelly)

    orden_compra = await comprar(par, monto_ajustado)
    if not orden_compra:
        return

    deal_funds = float(orden_compra['dealFunds'])
    deal_size = float(orden_compra['dealSize'])
    precio_entrada = deal_funds / deal_size

    logging.info(f"Compra realizada en {par} a {precio_entrada:.8f} USD")

    operacion_activa = par
    precio_maximo = precio_entrada

    while bot_encendido:
        try:
            ticker = kucoin.get_ticker(symbol=par.replace("/", "-"))
            precio_actual = float(ticker['price'])

            if precio_actual > precio_maximo:
                precio_maximo = precio_actual

            stop_price = precio_maximo * 0.92  # Trailing Stop del -8%

            if precio_actual <= stop_price:
                await vender(par, deal_size)
                ganancia = (precio_actual - precio_entrada) * deal_size
                operaciones_hoy += 1
                ganancia_total_hoy += ganancia

                logging.info(f"Venta por Trailing Stop activado. Ganancia: {ganancia:.4f} USDT")
                operacion_activa = None
                break

            await asyncio.sleep(2)

        except Exception as e:
            logging.error(f"Error durante monitoreo de operación en {par}: {e}")
            break# ─── Funciones de Escaneo de Mercado y Flujo ───────────────────────────────

async def escanear_mercado():
    """Escanea el mercado constantemente para detectar oportunidades."""
    global operacion_activa

    while bot_encendido:
        if operacion_activa:
            await asyncio.sleep(5)
            continue  # Espera a que termine la operación activa

        for par in pares:
            try:
                ticker = kucoin.get_ticker(symbol=par.replace("/", "-"))
                volumen_24h = float(ticker.get("volValue", 0))
                spread = (float(ticker.get("sell"), 0) - float(ticker.get("buy"), 0)) / float(ticker.get("sell"), 1)

                if volumen_24h > 50000 and spread < 0.004:
                    await estrategia_operacion(par)
                    await asyncio.sleep(2)
            except Exception as e:
                logging.error(f"Error escaneando {par}: {e}")
                continue

        await asyncio.sleep(2)

# ─── Modelo Predictor Simulado ─────────────────────────────────────────────

def entrenar_modelo():
    """Entrena un modelo de predicción básico."""
    X = np.random.rand(1000, 4)
    y = np.random.choice([0, 1], size=1000)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    modelo = RandomForestClassifier()
    modelo.fit(X_train, y_train)
    acc = accuracy_score(y_test, modelo.predict(X_test))
    logging.info(f"Precisión del modelo de predicción: {acc:.2f}")
    return modelo

modelo_predictor = entrenar_modelo()# ─── Comandos de Telegram ────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ *ZafroBot Scalper Pro* iniciado.\n\nSelecciona una opción:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def encender(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await message.answer("🟢 Bot encendido. Analizando mercado…", reply_markup=keyboard)
        asyncio.create_task(escanear_mercado())
    else:
        await message.answer("⚠️ El bot ya estaba encendido.", reply_markup=keyboard)

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def apagar(message: types.Message):
    global bot_encendido
    bot_encendido = False
    await message.answer("🔴 Bot apagado.", reply_markup=keyboard)

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def estado_bot(message: types.Message):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(
        f"📊 Estado del Bot: {estado}\n"
        f"🔹 Operaciones hoy: {operaciones_hoy}\n"
        f"🔹 Ganancia hoy: {ganancia_total_hoy:.4f} USDT",
        reply_markup=keyboard
    )

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = await obtener_saldo_disponible()
    await message.answer(f"💰 Saldo disponible: {saldo:.2f} USDT", reply_markup=keyboard)

@dp.message(lambda m: m.text == "📈 Estado de Orden Actual")
async def estado_operacion(message: types.Message):
    if operacion_activa:
        await message.answer(f"🚀 Operación activa: {operacion_activa}", reply_markup=keyboard)
    else:
        await message.answer("❌ No hay operación activa actualmente.", reply_markup=keyboard)

# ─── Lanzamiento Principal ───────────────────────────────────────────────

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())