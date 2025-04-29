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
)# ─── Funciones de Trading ──────────────────────────────────────────────────

async def obtener_balance():
    """Obtiene el saldo disponible real de USDT."""
    cuentas = await asyncio.to_thread(kucoin.get_accounts)
    for cuenta in cuentas:
        if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
            return float(cuenta['available'])
    return 0.0

def calcular_kelly(historico):
    """Calcula la fracción de Kelly basado en operaciones anteriores."""
    if len(historico) < 10:
        return 0.5  # Default si hay poco histórico

    ganancias = sum(1 for h in historico if h > 0)
    perdidas = sum(1 for h in historico if h <= 0)

    if perdidas == 0:
        return 0.95  # Siempre ganar, muy agresivo

    r = sum(historico) / abs(sum(1 for h in historico if h < 0))
    b = ganancias / (ganancias + perdidas)
    kelly = b - ((1 - b) / r)
    return max(0.1, min(kelly, 0.95))  # No menor a 10%, ni mayor 95%

def entrenar_modelo(historico):
    """Entrena el modelo de Machine Learning."""
    if len(historico) < 20:
        return None

    X = np.array([[x[0], x[1]] for x in historico])
    y = np.array([1 if x[2] > 0 else 0 for x in historico])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    modelo = RandomForestClassifier(n_estimators=50)
    modelo.fit(X_train, y_train)

    y_pred = modelo.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    logging.info(f"Modelo entrenado con precisión: {acc:.2f}")

    return modeloasync def operar():
    global operacion_activa, operaciones_hoy, ganancia_total_hoy, modelo_predictor

    balance = await obtener_balance()
    if balance < 5:
        await bot.send_message(CHAT_ID, f"⚠️ Saldo insuficiente ({balance:.2f} USDT). Esperando...")
        await asyncio.sleep(60)
        return

    par = random.choice(pares)
    precio_actual = await asyncio.to_thread(obtener_precio, par)

    if modelo_predictor and len(historico_en_memoria) >= 20:
        entrada = modelo_predictor.predict(np.array([[precio_actual, volumen_anterior.get(par, 0)]]))
        if entrada[0] == 0:
            await asyncio.sleep(5)
            return

    porcentaje_kelly = calcular_kelly(historico_en_memoria)
    monto_usdt = balance * porcentaje_kelly

    cantidad = calcular_cantidad(par, monto_usdt, precio_actual)
    if cantidad <= 0:
        await asyncio.sleep(5)
        return

    orden = await asyncio.to_thread(ejecutar_compra, par, cantidad)
    if orden:
        operacion_activa = {
            "par": par,
            "precio_entrada": precio_actual,
            "cantidad": cantidad,
            "stop_loss": precio_actual * 0.985,
            "trailing_stop": precio_actual * 0.99
        }
        operaciones_hoy += 1
        await bot.send_message(CHAT_ID, f"✅ Entrada ejecutada en {par}.\nPrecio: {precio_actual:.8f} USDT\nCantidad: {cantidad}")

async def monitorear_operacion():
    global operacion_activa, ganancia_total_hoy

    if not operacion_activa:
        return

    par = operacion_activa["par"]
    precio_entrada = operacion_activa["precio_entrada"]
    cantidad = operacion_activa["cantidad"]
    stop_loss = operacion_activa["stop_loss"]
    trailing_stop = operacion_activa["trailing_stop"]

    while bot_encendido and operacion_activa:
        precio_actual = await asyncio.to_thread(obtener_precio, par)

        # Actualizar trailing stop si el precio sube
        if precio_actual > trailing_stop * 1.01:
            nuevo_trailing = precio_actual * 0.99
            operacion_activa["trailing_stop"] = nuevo_trailing
            await bot.send_message(CHAT_ID, f"🔄 Trailing Stop actualizado para {par}: {nuevo_trailing:.8f}")

        if precio_actual <= operacion_activa["trailing_stop"]:
            ganancia = (precio_actual - precio_entrada) * cantidad
            ganancia_total_hoy += ganancia
            historial_operaciones.append(ganancia)
            historico_en_memoria.append((precio_entrada, volumen_anterior.get(par, 0), ganancia))

            await bot.send_message(
                CHAT_ID,
                f"🚪 Salida en {par}.\nPrecio final: {precio_actual:.8f}\nGanancia: {ganancia:.6f} USDT"
            )

            operacion_activa = None
            modelo_predictor = entrenar_modelo(historico_en_memoria)
            break

        await asyncio.sleep(5)def calcular_cantidad(par, monto_usdt, precio_actual):
    regla = minimos_por_par.get(par)
    if not regla:
        return 0

    cantidad = monto_usdt / precio_actual
    cantidad = Decimal(cantidad).quantize(Decimal(10) ** -regla["decimales"], rounding=ROUND_DOWN)

    if cantidad < Decimal(regla["min_cantidad"]):
        return 0
    return float(cantidad)

def obtener_precio(par):
    try:
        simbolo = par.replace("/", "-")
        ticker = kucoin.get_ticker(symbol=simbolo)
        return float(ticker["price"])
    except Exception as e:
        logging.error(f"Error obteniendo precio de {par}: {e}")
        return 0.0

def ejecutar_compra(par, cantidad):
    try:
        simbolo = par.replace("/", "-")
        orden = kucoin.create_market_order(symbol=simbolo, side="buy", size=cantidad)
        return orden
    except Exception as e:
        logging.error(f"Error ejecutando compra de {par}: {e}")
        return None# ─── Comandos de Telegram ─────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ *ZafroBot PRO Scalper Inteligente* iniciado.\n\nSelecciona una opción:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def cmd_encender(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await message.answer("🟢 Bot encendido. Buscando oportunidades...")
        asyncio.create_task(ciclo_operativo())
    else:
        await message.answer("⚠️ El bot ya estaba encendido.")

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def cmd_apagar(message: types.Message):
    global bot_encendido, operacion_activa
    bot_encendido = False
    operacion_activa = None
    await message.answer("🔴 Bot apagado manualmente.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def cmd_estado(message: types.Message):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"📊 Estado actual del bot: {estado}")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def cmd_actualizar_saldo(message: types.Message):
    balance = await obtener_balance()
    await message.answer(f"💰 Saldo disponible: {balance:.2f} USDT")

@dp.message(lambda m: m.text == "📈 Estado de Orden Actual")
async def cmd_estado_orden(message: types.Message):
    if operacion_activa:
        await message.answer(f"📈 Operación abierta:\nPar: {operacion_activa['par']}\nEntrada: {operacion_activa['precio_entrada']:.8f}")
    else:
        await message.answer("📈 No hay operaciones abiertas en este momento.")

# ─── Ciclo operativo ───────────────────────────────────────────────────────

async def ciclo_operativo():
    while bot_encendido:
        try:
            if not operacion_activa:
                await operar()
            else:
                await monitorear_operacion()
            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"Error general en el ciclo operativo: {str(e)}")
            await asyncio.sleep(10)

# ─── Lanzamiento del Bot ───────────────────────────────────────────────────

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())