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
from decimal import Decimal, ROUND_DOWN

logging.basicConfig(level=logging.INFO)

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

kucoin = Client(API_KEY, API_SECRET, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

bot_encendido = False
operacion_activa = None
operaciones_hoy = 0
ganancia_total_hoy = 0.0
_last_balance = 0.0
modelo_predictor = None
pares = ["PEPE/USDT", "FLOKI/USDT", "SHIB/USDT", "DOGE/USDT"]
volumen_anterior = {}
historico_en_memoria = []
historial_operaciones = []

minimos_por_par = {
    "PEPE/USDT": {"min_cantidad": 100000, "decimales": 0},
    "FLOKI/USDT": {"min_cantidad": 100000, "decimales": 0},
    "SHIB/USDT": {"min_cantidad": 10000, "decimales": 0},
    "DOGE/USDT": {"min_cantidad": 1, "decimales": 2},
}

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="📈 Estado de Orden Actual")],
    ],
    resize_keyboard=True,
)def obtener_saldo_disponible():
    try:
        cuentas = kucoin.get_accounts()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                return float(cuenta['available'])
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
    return 0.0

def aplicar_kelly(win_rate, profit_ratio):
    try:
        kelly = (win_rate - (1 - win_rate) / profit_ratio)
        return max(0.01, min(kelly, 1.0))  # entre 1% y 100%
    except:
        return 0.05  # valor por defecto conservador

def entrenar_modelo():
    global modelo_predictor
    if len(historico_en_memoria) < 10:
        return None
    datos = np.array(historico_en_memoria)
    X = datos[:, :-1]
    y = datos[:, -1]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    modelo = RandomForestClassifier(n_estimators=50)
    modelo.fit(X_train, y_train)
    acc = accuracy_score(y_test, modelo.predict(X_test))
    logging.info(f"Modelo entrenado con precisión: {acc}")
    modelo_predictor = modelodef detectar_oportunidad(par):
    try:
        velas = kucoin.get_kline(par.replace("/", "-"), "1min", limit=10)
        if not velas or len(velas) < 5:
            return False, None
        volumenes = [float(v[5]) for v in velas]
        precios = [float(v[2]) for v in velas]
        volumen_actual = volumenes[-1]
        promedio_vol = sum(volumenes[:-1]) / len(volumenes[:-1])
        aumento_vol = volumen_actual > promedio_vol * 1.8
        tendencia = precios[-1] > precios[0]
        historico_en_memoria.append([promedio_vol, volumen_actual, tendencia])
        if modelo_predictor:
            pred = modelo_predictor.predict([[promedio_vol, volumen_actual, tendencia]])
            if pred[0] == 1:
                return True, precios[-1]
        return aumento_vol and tendencia, precios[-1] if tendencia else None
    except Exception as e:
        logging.error(f"Error en escaneo de {par}: {e}")
        return False, None

async def ejecutar_operacion(par, precio_entrada, cantidad):
    try:
        simbolo = par.replace("/", "-")
        orden = kucoin.create_market_order(simbolo, "buy", size=None, funds=str(cantidad))
        logging.info(f"Compra ejecutada de {cantidad} USDT en {par}")
        await bot.send_message(CHAT_ID, f"✅ Compra de {par} ejecutada a precio {precio_entrada}")
        return True
    except Exception as e:
        logging.error(f"Error ejecutando compra de {par}: {e}")
        return Falsedef calcular_kelly(p_win=0.6, reward_risk=1.5):
    numerador = (p_win * (reward_risk + 1)) - 1
    denominador = reward_risk
    kelly = numerador / denominador
    return max(0.01, min(kelly, 1))

async def monitorear_operacion(par, precio_entrada, cantidad):
    global operacion_activa, operaciones_hoy, ganancia_total_hoy
    try:
        simbolo = par.replace("/", "-")
        trailing = 0.01
        take_profit = precio_entrada * 1.015
        stop_loss = precio_entrada * 0.98
        while True:
            ticker = kucoin.get_ticker(symbol=simbolo)
            actual = float(ticker["price"])
            if actual >= take_profit:
                logging.info(f"Venta por ganancia en {par}")
                await bot.send_message(CHAT_ID, f"✅ Venta por ganancia en {par}: {actual}")
                ganancia_total_hoy += (actual - precio_entrada) * cantidad / precio_entrada
                operaciones_hoy += 1
                operacion_activa = None
                break
            elif actual <= stop_loss:
                logging.info(f"Venta por stop loss en {par}")
                await bot.send_message(CHAT_ID, f"⚠️ Venta por stop loss en {par}: {actual}")
                operaciones_hoy += 1
                operacion_activa = None
                break
            else:
                nuevo_trailing = actual * 0.985
                if nuevo_trailing > stop_loss:
                    stop_loss = nuevo_trailing
            await asyncio.sleep(10)
    except Exception as e:
        logging.error(f"Error en monitoreo de operación: {e}")@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✅ ZafroBot PRO Scalper Inteligente iniciado.", reply_markup=keyboard)

@dp.message(Command("encender"))
@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def encender_bot(message: types.Message):
    global bot_encendido
    bot_encendido = True
    await message.answer("🟢 Bot encendido. Analizando mercado...")

@dp.message(Command("apagar"))
@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def apagar_bot(message: types.Message):
    global bot_encendido
    bot_encendido = False
    await message.answer("🔴 Bot apagado.")

@dp.message(Command("estado"))
@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def estado_bot(message: types.Message):
    status = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"Estado actual del bot: {status}\nOperaciones hoy: {operaciones_hoy}\nGanancia: {ganancia_total_hoy:.2f} USDT")

@dp.message(lambda m: m.text == "📈 Estado de Orden Actual")
async def estado_orden_actual(message: types.Message):
    if operacion_activa:
        await message.answer(f"⏳ Orden activa: {operacion_activa}")
    else:
        await message.answer("No hay órdenes activas en este momento.")

async def ciclo_principal():
    global bot_encendido, operacion_activa
    while True:
        if bot_encendido and operacion_activa is None:
            for par in pares:
                oportunidad, precio = detectar_oportunidad(par)
                if oportunidad:
                    saldo = obtener_saldo_disponible()
                    fraccion = calcular_kelly()
                    cantidad = saldo * fraccion
                    if cantidad < 1:
                        continue
                    exito = await ejecutar_operacion(par, precio, cantidad)
                    if exito:
                        operacion_activa = par
                        await monitorear_operacion(par, precio, cantidad)
        await asyncio.sleep(15)

async def main():
    asyncio.create_task(ciclo_principal())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())