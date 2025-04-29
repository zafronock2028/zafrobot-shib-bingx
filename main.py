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
modelo_predictor = None# ─── Teclado de Comandos ────────────────────────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="📈 Estado de Orden Actual")],
    ],
    resize_keyboard=True,
)

# ─── Funciones de Análisis ──────────────────────────────────────────────────

async def analizar_mercado_real(par):
    try:
        simbolo = par.replace("/", "-")
        order_book = await asyncio.to_thread(kucoin.get_order_book, symbol=simbolo, depth=20)

        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])

        if not bids or not asks:
            return False

        mejor_bid = float(bids[0][0])
        mejor_ask = float(asks[0][0])
        spread = (mejor_ask - mejor_bid) / mejor_bid * 100

        volumen_bids = sum(float(bid[1]) for bid in bids[:5])
        volumen_asks = sum(float(ask[1]) for ask in asks[:5])

        if spread > 0.3:  # Mejorado: permite spread hasta 0.3%
            return False
        if volumen_bids < volumen_asks:
            return False
        if volumen_bids < 50:
            return False

        return True

    except Exception as e:
        logging.error(f"Error en analizar_mercado_real para {par}: {str(e)}")
        return False

# ─── Funciones de Gestión de Operaciones ────────────────────────────────────

async def registrar_operacion(par, precio_entrada, cantidad, saldo_usado):
    global operacion_activa
    operacion_activa = {
        "par": par,
        "precio_entrada": precio_entrada,
        "cantidad": cantidad,
        "saldo_usado": saldo_usado,
        "hora": datetime.datetime.now(),
        "mejor_precio": precio_entrada
    }

async def limpiar_operacion():
    global operacion_activa
    operacion_activa = None

async def actualizar_estadisticas(porcentaje_ganancia):
    global operaciones_hoy, ganancia_total_hoy, historial_operaciones
    operaciones_hoy += 1
    ganancia_total_hoy += porcentaje_ganancia
    historial_operaciones.append(porcentaje_ganancia)
    if len(historial_operaciones) > 50:
        historial_operaciones.pop(0)
    entrenar_modelo()# ─── Funciones Internas ─────────────────────────────────────────────────────

async def obtener_balance():
    cuenta = await asyncio.to_thread(kucoin.get_accounts, currency="USDT", type="trade")
    if cuenta:
        return float(cuenta[0].get('available', 0))
    return 0.0

def obtener_precio(par):
    simbolo = par.replace("/", "-")
    ticker = kucoin.get_ticker(symbol=simbolo)
    return float(ticker["price"])

def ejecutar_compra(par, cantidad):
    simbolo = par.replace("/", "-")
    try:
        orden = kucoin.create_market_order(symbol=simbolo, side="buy", size=cantidad)
        return orden
    except Exception as e:
        logging.error(f"Error comprando {par}: {str(e)}")
        return None

# ─── Recolección de Datos en Memoria ────────────────────────────────────────

def recolectar_datos_en_memoria(par, precio_open, precio_high, precio_low, precio_close, volumen, spread, liquidez_compra, resultado=None):
    global historico_en_memoria
    historico_en_memoria.append({
        "par": par,
        "open": precio_open,
        "high": precio_high,
        "low": precio_low,
        "close": precio_close,
        "volumen": volumen,
        "spread": spread,
        "liquidez": liquidez_compra,
        "resultado": resultado
    })
    if len(historico_en_memoria) > 500:
        historico_en_memoria.pop(0)

# ─── Machine Learning: Entrenamiento y Predicción ───────────────────────────

def entrenar_modelo():
    global modelo_predictor, historico_en_memoria

    if len(historico_en_memoria) < 100:
        return

    try:
        X = []
        y = []

        for registro in historico_en_memoria:
            if registro["resultado"] is None:
                continue

            X.append([
                registro["open"],
                registro["high"],
                registro["low"],
                registro["close"],
                registro["volumen"],
                registro["spread"],
                registro["liquidez"],
            ])
            y.append(1 if registro["resultado"] > 0 else 0)

        if len(X) < 50:
            return

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        modelo = RandomForestClassifier(n_estimators=100, random_state=42)
        modelo.fit(X_train, y_train)

        modelo_predictor = modelo

        preds = modelo.predict(X_test)
        acc = accuracy_score(y_test, preds)
        logging.info(f"Nuevo modelo entrenado con precisión {acc:.2%}")

    except Exception as e:
        logging.error(f"Error entrenando modelo: {str(e)}")

def predecir_entrada(open_price, high_price, low_price, close_price, volumen, spread, liquidez):
    if modelo_predictor is None:
        return True

    try:
        datos = np.array([[open_price, high_price, low_price, close_price, volumen, spread, liquidez]])
        prediccion = modelo_predictor.predict(datos)[0]
        return prediccion == 1
    except Exception as e:
        logging.error(f"Error prediciendo entrada: {str(e)}")
        return True# ─── Lógica de Trading ──────────────────────────────────────────────────────

async def operar():
    global _last_balance
    _last_balance = await obtener_balance()

    while bot_encendido:
        try:
            balance = await obtener_balance()

            if balance < 5:
                await bot.send_message(CHAT_ID, f"⚠️ Saldo insuficiente ({balance:.2f} USDT). Esperando...")
                await asyncio.sleep(10)
                continue

            if operacion_activa is not None:
                await asyncio.sleep(1)
                continue

            par = random.choice(pares)

            precio_open = await asyncio.to_thread(obtener_precio, par)
            precio_high = precio_open * random.uniform(1.001, 1.005)
            precio_low = precio_open * random.uniform(0.995, 0.999)
            precio_close = await asyncio.to_thread(obtener_precio, par)
            spread = abs(precio_high - precio_low)
            liquidez = random.uniform(100, 10000)

            recolectar_datos_en_memoria(par, precio_open, precio_high, precio_low, precio_close, volumen=0, spread=spread, liquidez_compra=liquidez)

            analisis_ok = await analizar_mercado_real(par)

            if not analisis_ok:
                await asyncio.sleep(1)
                continue

            es_buena_entrada = predecir_entrada(precio_open, precio_high, precio_low, precio_close, 0, spread, liquidez)

            if not es_buena_entrada:
                await asyncio.sleep(1)
                continue

            porcentaje_kelly = calcular_kelly_ratio()
            saldo_usar = balance * porcentaje_kelly
            cantidad = saldo_usar / precio_open

            orden = await asyncio.to_thread(ejecutar_compra, par, cantidad)
            if orden:
                await bot.send_message(CHAT_ID, f"✅ *Compra ejecutada*\n\nPar: {par}\nPrecio: {precio_open:.8f}\nSaldo usado: {saldo_usar:.2f} USDT", parse_mode="Markdown")
                await registrar_operacion(par, precio_open, cantidad, saldo_usar)
                asyncio.create_task(monitorear_operacion(par, precio_open, cantidad))

            await asyncio.sleep(1)

        except Exception as e:
            logging.error(f"Error general: {str(e)}")
            await asyncio.sleep(10)

async def monitorear_operacion(par, precio_entrada, cantidad):
    global operacion_activa

    objetivo_inicial = precio_entrada * 1.025
    trailing_stop = 0.98

    while bot_encendido and operacion_activa is not None:
        precio_actual = await asyncio.to_thread(obtener_precio, par)

        porcentaje_cambio = ((precio_actual - precio_entrada) / precio_entrada) * 100

        if precio_actual > operacion_activa["mejor_precio"]:
            operacion_activa["mejor_precio"] = precio_actual

        mejor_precio = operacion_activa["mejor_precio"]
        nuevo_stop = mejor_precio * 0.985

        if precio_actual >= objetivo_inicial:
            if precio_actual <= nuevo_stop:
                await bot.send_message(CHAT_ID, f"🎯 *Take Profit alcanzado*\n\nGanancia asegurada: +{porcentaje_cambio:.2f}%", parse_mode="Markdown")
                await actualizar_estadisticas(porcentaje_cambio)
                await limpiar_operacion()
                break

        elif precio_actual <= precio_entrada * trailing_stop:
            await bot.send_message(CHAT_ID, f"⚡ *Stop Loss activado*\n\nPérdida: {porcentaje_cambio:.2f}%", parse_mode="Markdown")
            await actualizar_estadisticas(porcentaje_cambio)
            await limpiar_operacion()
            break

        await asyncio.sleep(1)

# ─── Kelly Criterion Mejorado ───────────────────────────────────────────────

def calcular_kelly_ratio():
    if len(historial_operaciones) < 10:
        return 0.5

    ganancias = [r for r in historial_operaciones if r > 0]
    perdidas = [r for r in historial_operaciones if r <= 0]

    p = len(ganancias) / len(historial_operaciones)
    q = 1 - p

    if len(perdidas) == 0:
        return 0.9

    ganancia_promedio = sum(ganancias) / len(ganancias)
    perdida_promedio = abs(sum(perdidas)) / len(perdidas)

    b = ganancia_promedio / perdida_promedio if perdida_promedio > 0 else 1

    kelly = (b * p - q) / b

    return max(0.1, min(kelly, 0.9))# ─── Sistema de Alertas de Volumen Anormal ──────────────────────────────────

async def inicializar_volumenes():
    global volumen_anterior
    for par in pares:
        simbolo = par.replace("/", "-")
        try:
            ticker = await asyncio.to_thread(kucoin.get_ticker, symbol=simbolo)
            volumen = float(ticker.get('volValue', 0))
            volumen_anterior[par] = volumen
        except Exception as e:
            logging.error(f"Error inicializando volumen de {par}: {str(e)}")
            volumen_anterior[par] = 0.0

async def escanear_volumenes():
    global volumen_anterior
    await inicializar_volumenes()

    while True:
        try:
            for par in pares:
                simbolo = par.replace("/", "-")
                ticker = await asyncio.to_thread(kucoin.get_ticker, symbol=simbolo)
                volumen_actual = float(ticker.get('volValue', 0))

                volumen_ant = volumen_anterior.get(par, 0.0)
                if volumen_ant == 0.0:
                    volumen_anterior[par] = volumen_actual
                    continue

                incremento = ((volumen_actual - volumen_ant) / volumen_ant) * 100

                if incremento >= 500:
                    await bot.send_message(CHAT_ID,
                        f"🚨 *ALERTA de Volumen Anormal*\n\n"
                        f"Par: {par}\n"
                        f"Incremento: +{incremento:.2f}%\n"
                        f"Acción: Monitorear posible oportunidad.",
                        parse_mode="Markdown"
                    )

                volumen_anterior[par] = volumen_actual

            await asyncio.sleep(60)

        except Exception as e:
            logging.error(f"Error en escaneo de volumen: {str(e)}")
            await asyncio.sleep(60)

# ─── Comandos de Telegram ───────────────────────────────────────────────────

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
        await message.answer("🟢 Bot encendido. Analizando mercado…")
        asyncio.create_task(operar())
    else:
        await message.answer("⚠️ El bot ya está encendido.")

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def cmd_apagar(message: types.Message):
    global bot_encendido
    bot_encendido = False
    await message.answer("🔴 Bot apagado.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def cmd_estado(message: types.Message):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"📊 Estado actual: {estado}")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def cmd_actualizar_saldo(message: types.Message):
    balance = await obtener_balance()
    await message.answer(f"💰 Saldo disponible: {balance:.2f} USDT")

@dp.message(lambda m: m.text == "📈 Estado de Orden Actual")
async def cmd_estado_orden(message: types.Message):
    if operacion_activa is None:
        await message.answer("⚠️ No hay operaciones abiertas en este momento.")
    else:
        par = operacion_activa["par"]
        precio_entrada = operacion_activa["precio_entrada"]
        cantidad = operacion_activa["cantidad"]
        saldo_usado = operacion_activa["saldo_usado"]
        precio_actual = await asyncio.to_thread(obtener_precio, par)

        porcentaje_cambio = ((precio_actual - precio_entrada) / precio_entrada) * 100

        estado = "🟢 En Ganancia" if porcentaje_cambio > 0 else "🔴 En Pérdida"

        await message.answer(
            f"📈 Estado de Orden Actual:\n\n"
            f"Par: {par}\n"
            f"Precio Entrada: {precio_entrada:.8f}\n"
            f"Precio Actual: {precio_actual:.8f}\n"
            f"{estado}: {porcentaje_cambio:.2f}%\n"
            f"Saldo Invertido: {saldo_usado:.2f} USDT"
        )

# ─── Lanzamiento Final ──────────────────────────────────────────────────────

async def main():
    asyncio.create_task(escanear_volumenes())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())