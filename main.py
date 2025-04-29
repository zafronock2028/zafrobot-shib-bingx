# === ZafroBot Scalper Pro V1 - BLOQUE 1 ===
import os
import asyncio
import logging
import datetime
from decimal import Decimal, ROUND_DOWN

from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import numpy as np

# Configuración inicial
logging.basicConfig(level=logging.INFO)

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", "0"))

# Clientes
kucoin = Client(API_KEY, API_SECRET, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Estado y parámetros globales
bot_encendido = False
pares = ["PEPE/USDT", "FLOKI/USDT", "SHIB/USDT", "DOGE/USDT"]
operacion_activa = None
operaciones_hoy = 0
ganancia_total_hoy = 0.0
historico_en_memoria = []
modelo_predictor = None
trailing_stop_activado = True

# Config mínimos
minimos_por_par = {
    "PEPE/USDT": {"min_cantidad": 100000, "decimales": 0},
    "FLOKI/USDT": {"min_cantidad": 100000, "decimales": 0},
    "SHIB/USDT": {"min_cantidad": 10000, "decimales": 0},
    "DOGE/USDT": {"min_cantidad": 1, "decimales": 2},
}# === ZafroBot Scalper Pro V1 - BLOQUE 2 ===

# Teclado de opciones para Telegram
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="📈 Estado de Orden Actual")],
    ],
    resize_keyboard=True,
)

# Función para obtener el saldo disponible en USDT
def obtener_saldo_disponible():
    try:
        cuentas = kucoin.get_accounts()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                return float(cuenta['available'])
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
    return 0.0

# Calcular tamaño de posición con Kelly Criterion (fijo 20% si falla)
def calcular_tamano_con_kelly(probabilidad_ganancia, ganancia_riesgo):
    try:
        kelly = (probabilidad_ganancia * (ganancia_riesgo + 1) - 1) / ganancia_riesgo
        return max(min(kelly, 1), 0.05)  # mínimo 5%
    except:
        return 0.20

# Redondear cantidad según decimales del par
def redondear_cantidad(par, cantidad):
    decimales = minimos_por_par.get(par, {}).get("decimales", 2)
    return float(Decimal(cantidad).quantize(Decimal(f'1e-{decimales}'), rounding=ROUND_DOWN))# === ZafroBot Scalper Pro V1 - BLOQUE 3 ===

# Ejecutar orden de compra con trailing stop virtual
async def ejecutar_compra(par, saldo_usdt):
    try:
        minimo = minimos_por_par.get(par, {}).get("min_cantidad", 1)
        precio = float(kucoin.get_ticker(par)['price'])
        cantidad = redondear_cantidad(par, saldo_usdt / precio)

        if cantidad < minimo:
            logging.warning(f"No se puede operar {par}: cantidad {cantidad} menor al mínimo {minimo}")
            return False

        orden = kucoin.create_market_order(par, 'buy', size=str(cantidad))
        logging.info(f"Orden de COMPRA ejecutada: {par}, cantidad: {cantidad}")
        return {
            "par": par,
            "precio_entrada": precio,
            "cantidad": cantidad,
            "precio_maximo": precio
        }
    except Exception as e:
        logging.error(f"Error ejecutando compra de {par}: {e}")
        return False

# Monitorear operación para aplicar trailing stop y cerrar
async def monitorear_operacion(orden):
    try:
        global ganancia_total_hoy, operaciones_hoy, operacion_activa
        par = orden["par"]
        cantidad = orden["cantidad"]
        entrada = orden["precio_entrada"]
        precio_max = orden["precio_maximo"]
        trailing = 0.015  # 1.5%

        while True:
            precio_actual = float(kucoin.get_ticker(par)['price'])
            if precio_actual > precio_max:
                precio_max = precio_actual

            if precio_actual <= precio_max * (1 - trailing):
                venta = kucoin.create_market_order(par, 'sell', size=str(cantidad))
                ganancia = (precio_actual - entrada) * cantidad
                ganancia_total_hoy += ganancia
                operaciones_hoy += 1
                logging.info(f"VENTA ejecutada: {par} | Ganancia: {ganancia:.4f}")
                operacion_activa = None
                break

            await asyncio.sleep(10)
    except Exception as e:
        logging.error(f"Error en monitoreo: {e}")# === ZafroBot Scalper Pro V1 - BLOQUE 4 ===

# Entrenar modelo de machine learning
def entrenar_modelo():
    global modelo_predictor
    if len(historico_en_memoria) < 30:
        return
    datos = np.array(historico_en_memoria)
    X = datos[:, :-1]
    y = (datos[:, -1] > 0).astype(int)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    modelo = RandomForestClassifier(n_estimators=50)
    modelo.fit(X_train, y_train)
    acc = accuracy_score(y_test, modelo.predict(X_test))
    logging.info(f"Modelo entrenado con precisión: {acc:.2f}")
    modelo_predictor = modelo

# Detectar oportunidad de entrada
def detectar_oportunidad(par):
    try:
        velas = kucoin.get_kline(par.replace("/", "-"), "1min", limit=10)
        if not velas or len(velas) < 5:
            return False
        precios = [float(v[2]) for v in velas]
        volumenes = [float(v[5]) for v in velas]
        subida = precios[-1] > precios[0]
        volumen_actual = volumenes[-1]
        promedio_volumen = sum(volumenes[:-1]) / len(volumenes[:-1])
        aumento_volumen = volumen_actual > promedio_volumen * 1.5

        if modelo_predictor:
            entrada = modelo_predictor.predict([[promedio_volumen, volumen_actual]])
            return entrada[0] == 1
        return subida and aumento_volumen
    except Exception as e:
        logging.error(f"Error detectando oportunidad en {par}: {e}")
        return False

# Ciclo operativo principal
async def ciclo_principal():
    global operacion_activa
    while bot_encendido:
        if operacion_activa is None:
            saldo = obtener_saldo_disponible()
            if saldo >= 5:
                for par in pares:
                    if detectar_oportunidad(par):
                        orden = await ejecutar_compra(par, saldo)
                        if orden:
                            operacion_activa = orden
                            await monitorear_operacion(orden)
                            break
        await asyncio.sleep(15)# === ZafroBot Scalper Pro V1 - BLOQUE 5 ===

# ─── Comandos de Telegram ────────────────────────────────────────────────

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "✅ *ZafroBot PRO Scalper Inteligente* iniciado.\n\nSelecciona una opción:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def encender_bot(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await message.answer("🟢 Bot encendido y analizando mercado...")
        asyncio.create_task(ciclo_principal())
    else:
        await message.answer("⚠️ El bot ya estaba encendido.")

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def apagar_bot(message: types.Message):
    global bot_encendido
    bot_encendido = False
    await message.answer("🔴 Bot apagado manualmente.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def estado_bot(message: types.Message):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"📊 Estado actual del bot: {estado}\n\nOperaciones hoy: {operaciones_hoy}\nGanancia hoy: {ganancia_total_hoy:.4f} USDT")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = obtener_saldo_disponible()
    await message.answer(f"💰 Saldo disponible actual: {saldo:.2f} USDT")

@dp.message(lambda m: m.text == "📈 Estado de Orden Actual")
async def estado_orden(message: types.Message):
    if operacion_activa:
        await message.answer(f"📈 Operación activa:\nPar: {operacion_activa['par']}\nPrecio Entrada: {operacion_activa['precio_entrada']:.6f}")
    else:
        await message.answer("📈 No hay operaciones abiertas actualmente.")

# ─── Lanzamiento del Bot ─────────────────────────────────────────────────

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())