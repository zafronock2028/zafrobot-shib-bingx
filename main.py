# main.py
import os
import asyncio
import logging
import datetime
import random
from kucoin.client import Trade
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import numpy as np
from decimal import Decimal, ROUND_DOWN

# ─── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

# ─── Configuración ─────────────────────────────────────────────────────────
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

# ─── Cliente de KuCoin ─────────────────────────────────────────────────────
kucoin = Trade(key=API_KEY, secret=API_SECRET, passphrase=API_PASSPHRASE)

# ─── Cliente de Telegram ───────────────────────────────────────────────────
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ─── Variables Globales ────────────────────────────────────────────────────
bot_encendido = False
operacion_activa = None
saldo_total = 0.0
historial_operaciones = []
pares = ["PEPE/USDT", "FLOKI/USDT", "SHIB/USDT", "DOGE/USDT"]
volumen_anterior = {}
modelo_predictor = None# ─── Reglas de tamaño mínimo ───────────────────────────────────────────────
minimos_por_par = {
    "PEPE/USDT": {"min_cantidad": 100000, "decimales": 0},
    "FLOKI/USDT": {"min_cantidad": 100000, "decimales": 0},
    "SHIB/USDT": {"min_cantidad": 10000, "decimales": 0},
    "DOGE/USDT": {"min_cantidad": 1, "decimales": 2},
}

# ─── Teclado de Telegram ────────────────────────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="📈 Estado de Orden Actual")],
    ],
    resize_keyboard=True,
)

# ─── Funciones de Trading ───────────────────────────────────────────────────
async def obtener_saldo():
    try:
        cuentas = kucoin.get_accounts()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                return float(cuenta['available'])
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
    return 0.0

async def analizar_pares():
    oportunidades = []
    for par in pares:
        try:
            book = kucoin.get_order_book(symbol=par.replace("/", "-"))
            bid = float(book['bids'][0][0])
            ask = float(book['asks'][0][0])
            spread = (ask - bid) / bid

            if spread < 0.003:  # Ejemplo: spread menor a 0.3%
                volumen = float(book['bids'][0][1])
                if volumen > 500:  # Volumen mínimo aceptable
                    oportunidades.append((par, spread, volumen))
        except Exception as e:
            logging.error(f"Error analizando {par}: {e}")
    return oportunidades# ─── Modelo Predictor Simple ───────────────────────────────────────────────
def entrenar_modelo():
    X = np.random.rand(1000, 4)
    y = np.random.choice([0, 1], size=1000)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    modelo = RandomForestClassifier()
    modelo.fit(X_train, y_train)
    y_pred = modelo.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    logging.info(f"Precisión del modelo de predicción: {acc:.2f}")
    return modelo

modelo_predictor = entrenar_modelo()

# ─── Funciones para Comprar y Vender ────────────────────────────────────────
async def comprar(par, cantidad):
    try:
        orden = kucoin.create_market_order(
            symbol=par.replace("/", "-"),
            side="buy",
            size=None,
            funds=str(cantidad)
        )
        logging.info(f"Compra ejecutada en {par} por {cantidad} USDT")
        return orden
    except Exception as e:
        logging.error(f"Error ejecutando compra: {e}")
        return None

async def vender(par, cantidad):
    try:
        orden = kucoin.create_market_order(
            symbol=par.replace("/", "-"),
            side="sell",
            size=str(cantidad)
        )
        logging.info(f"Venta ejecutada en {par} con cantidad {cantidad}")
        return orden
    except Exception as e:
        logging.error(f"Error ejecutando venta: {e}")
        return None# ─── Funciones de Trading Inteligente ───────────────────────────────────────
async def analizar_par(par):
    try:
        libro_ordenes = kucoin.get_order_book(symbol=par.replace("/", "-"))
        bids = libro_ordenes['bids']
        asks = libro_ordenes['asks']
        mejor_bid = float(bids[0][0]) if bids else 0
        mejor_ask = float(asks[0][0]) if asks else 0
        spread = (mejor_ask - mejor_bid) / mejor_ask * 100 if mejor_ask else 0

        volumen_24h = kucoin.get_ticker(par.replace("/", "-"))['volValue']
        volumen = float(volumen_24h) if volumen_24h else 0

        if volumen > 10000 and spread < 0.5:
            return True, mejor_bid, mejor_ask
        else:
            return False, mejor_bid, mejor_ask
    except Exception as e:
        logging.error(f"Error analizando {par}: {e}")
        return False, 0, 0

async def ejecutar_operacion(par):
    global operacion_activa, operaciones_hoy, ganancia_total_hoy, _last_balance

    # Análisis y validación
    oportunidad, mejor_bid, mejor_ask = await analizar_par(par)
    if not oportunidad:
        return

    saldo_actual = obtener_saldo_disponible()
    if saldo_actual is None or saldo_actual <= 0:
        return

    monto_inversion = calcular_kelly(saldo_actual)
    if monto_inversion < 1:
        monto_inversion = 1

    orden_compra = await comprar(par, monto_inversion)
    if not orden_compra:
        return

    cantidad_adquirida = float(orden_compra['dealFunds']) / mejor_ask
    precio_objetivo = mejor_ask * 1.025

    logging.info(f"Esperando venta en {par} al precio objetivo: {precio_objetivo:.6f}")

    while True:
        _, bid_actual, ask_actual = await analizar_par(par)
        if bid_actual >= precio_objetivo:
            orden_venta = await vender(par, cantidad_adquirida)
            if orden_venta:
                operaciones_hoy += 1
                ganancia = (bid_actual - mejor_ask) * cantidad_adquirida
                ganancia_total_hoy += ganancia
                _last_balance += ganancia
                historial_operaciones.append({
                    "par": par,
                    "entrada": mejor_ask,
                    "salida": bid_actual,
                    "ganancia": ganancia
                })
            break
        await asyncio.sleep(2)

async def escanear_mercado():
    while bot_encendido:
        for par in pares:
            try:
                await ejecutar_operacion(par)
            except Exception as e:
                logging.error(f"Error en la operación con {par}: {e}")
            await asyncio.sleep(2)# ─── Comandos de Telegram ───────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ *ZafroBot Scalper Pro V1* iniciado.\n\nSelecciona una opción:",
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
        await message.answer("⚠️ El bot ya está encendido.")

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def apagar(message: types.Message):
    global bot_encendido
    bot_encendido = False
    await message.answer("🔴 Bot apagado.", reply_markup=keyboard)

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def estado_bot(message: types.Message):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"Estado actual: {estado}", reply_markup=keyboard)

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = await obtener_saldo()
    await message.answer(f"💰 Saldo disponible: {saldo:.2f} USDT", reply_markup=keyboard)

@dp.message(lambda m: m.text == "📈 Estado de Orden Actual")
async def estado_orden(message: types.Message):
    if operacion_activa:
        await message.answer(f"✅ Operación activa en {operacion_activa}")
    else:
        await message.answer("❌ No hay operación activa en este momento.", reply_markup=keyboard)

# ─── Función Principal ─────────────────────────────────────────────────────

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())