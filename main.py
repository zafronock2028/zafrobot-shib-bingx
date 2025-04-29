# main.py
import os
import asyncio
import logging
import datetime
import random
from kucoin.client import Market, Trade, User
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

# ─── Configuración de Entorno ─────────────────────────────────────────────
API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID        = int(os.getenv("CHAT_ID", 0))

# ─── Inicializar clientes de KuCoin ───────────────────────────────────────
market = Market(API_KEY, API_SECRET, API_PASSPHRASE)
trade = Trade(API_KEY, API_SECRET, API_PASSPHRASE)
user = User(API_KEY, API_SECRET, API_PASSPHRASE)

# ─── Inicializar Bot de Telegram ──────────────────────────────────────────
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ─── Variables Globales ────────────────────────────────────────────────────
bot_encendido = False
_last_balance = 0.0
pares = ["PEPE/USDT", "FLOKI/USDT", "SHIB/USDT", "DOGE/USDT"]

operacion_activa = None
operaciones_hoy = 0
ganancia_total_hoy = 0.0
historial_operaciones = []
volumen_anterior = {}
historico_en_memoria = []
modelo_predictor = None# ─── Reglas de Tamaño Mínimo por Par ───────────────────────────────────────
minimos_por_par = {
    "PEPE/USDT": {"min_cantidad": 100000, "decimales": 0},
    "FLOKI/USDT": {"min_cantidad": 100000, "decimales": 0},
    "SHIB/USDT": {"min_cantidad": 10000, "decimales": 0},
    "DOGE/USDT": {"min_cantidad": 1, "decimales": 2},
}

# ─── Teclado Personalizado de Telegram ──────────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🚀 Encender Bot"),
            KeyboardButton(text="🛑 Apagar Bot")
        ],
        [
            KeyboardButton(text="📊 Estado del Bot"),
            KeyboardButton(text="💰 Actualizar Saldo")
        ],
        [
            KeyboardButton(text="📈 Estado de Orden Actual")
        ],
    ],
    resize_keyboard=True,
)# ─── Funciones para Consultar el Saldo Disponible en Wallet de Trading ──────
async def obtener_saldo_disponible():
    try:
        cuentas = kucoin.get_accounts()
        saldo_total = 0.0
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                saldo_total += float(cuenta['available'])
        return saldo_total
    except Exception as e:
        logging.error(f"Error al obtener saldo: {e}")
        return 0.0

async def actualizar_saldo(mensaje: types.Message):
    saldo = await obtener_saldo_disponible()
    await mensaje.answer(f"💰 Saldo disponible: {saldo:.2f} USDT")

# ─── Función para Calcular la Operación Segura con Kelly Criterion ─────────
def calcular_monto_con_kelly(saldo_disponible, probabilidad_exito, riesgo_recompensa, volumen_24h):
    try:
        kelly = (probabilidad_exito * (riesgo_recompensa + 1) - 1) / riesgo_recompensa
        monto_kelly = saldo_disponible * kelly
        max_operacion = volumen_24h * 0.04  # no operar más del 4% del volumen 24h
        monto_final = min(monto_kelly, max_operacion)

        if monto_final < 5:  # para evitar compras muy bajas, ajuste mínimo
            monto_final = 5
        return max(monto_final, 1)  # aseguramos mínimo 1 USDT
    except Exception as e:
        logging.error(f"Error en cálculo de Kelly: {e}")
        return 1.0# ─── Análisis de Oportunidades de Entrada ───────────────────────────────────
async def analizar_oportunidades():
    global operacion_activa
    while bot_encendido:
        try:
            saldo = await obtener_saldo_disponible()
            if saldo <= 0:
                logging.warning("Saldo insuficiente para operar.")
                await asyncio.sleep(2)
                continue

            mejor_par = None
            mejor_probabilidad = 0
            volumen_actual = 0

            for par in pares:
                data = kucoin.get_ticker(par)
                volumen = float(data['volValue'])  # volumen en USD
                precio = float(data['price'])

                historico_en_memoria.append(precio)
                if len(historico_en_memoria) > 100:
                    historico_en_memoria.pop(0)

                if len(historico_en_memoria) >= 30:
                    X = np.array(historico_en_memoria[:-1]).reshape(-1, 1)
                    y = np.array([1 if historico_en_memoria[i+1] > historico_en_memoria[i] else 0 for i in range(len(historico_en_memoria)-1)])

                    modelo = RandomForestClassifier(n_estimators=100)
                    modelo.fit(X, y)

                    prediccion = modelo.predict(np.array([[precio]]))
                    probabilidad = modelo.predict_proba(np.array([[precio]]))[0][1]  # probabilidad de subida

                    if probabilidad > mejor_probabilidad:
                        mejor_probabilidad = probabilidad
                        mejor_par = par
                        volumen_actual = volumen

            if mejor_par and mejor_probabilidad > 0.60:
                monto_invertir = calcular_monto_con_kelly(saldo, mejor_probabilidad, 2, volumen_actual)
                await ejecutar_compra(mejor_par, monto_invertir)

            await asyncio.sleep(2)

        except Exception as e:
            logging.error(f"Error en análisis de oportunidades: {e}")
            await asyncio.sleep(5)

# ─── Ejecución de Compra ───────────────────────────────────────────────────
async def ejecutar_compra(par, cantidad_usdt):
    global operacion_activa

    try:
        precio_actual = float(kucoin.get_ticker(par)['price'])
        minimos = minimos_por_par.get(par, {"min_cantidad": 1, "decimales": 2})
        cantidad = cantidad_usdt / precio_actual
        cantidad = Decimal(cantidad).quantize(Decimal('1e-{0}'.format(minimos['decimales'])), rounding=ROUND_DOWN)

        if cantidad < minimos['min_cantidad']:
            cantidad = Decimal(minimos['min_cantidad'])

        orden = kucoin.create_market_order(
            symbol=par.replace("/", "-"),
            side='buy',
            size=str(cantidad)
        )
        logging.info(f"Compra ejecutada en {par} por {cantidad_usdt:.2f} USDT")
        operacion_activa = {
            "par": par,
            "cantidad": cantidad,
            "precio_entrada": precio_actual,
            "stop_loss": precio_actual * (1 - 0.08),  # trailing stop -8%
            "objetivo_minimo": precio_actual * 1.02,  # target mínimo 2%
            "objetivo_maximo": precio_actual * 1.10,  # target máximo 10%
        }
    except Exception as e:
        logging.error(f"Error al ejecutar compra: {e}")# ─── Monitoreo de Operaciones Abiertas ─────────────────────────────────────
async def monitorear_operacion():
    global operacion_activa, operaciones_hoy, ganancia_total_hoy

    while bot_encendido:
        if not operacion_activa:
            await asyncio.sleep(2)
            continue

        try:
            par = operacion_activa["par"]
            cantidad = operacion_activa["cantidad"]
            precio_entrada = operacion_activa["precio_entrada"]
            stop_loss = operacion_activa["stop_loss"]
            objetivo_minimo = operacion_activa["objetivo_minimo"]

            precio_actual = float(kucoin.get_ticker(par)['price'])

            if precio_actual >= objetivo_minimo:
                kucoin.create_market_order(
                    symbol=par.replace("/", "-"),
                    side='sell',
                    size=str(cantidad)
                )
                ganancia = (precio_actual - precio_entrada) * float(cantidad)
                operaciones_hoy += 1
                ganancia_total_hoy += ganancia
                await bot.send_message(CHAT_ID, f"🎯 Venta exitosa en {par}\nGanancia: {ganancia:.4f} USDT")
                logging.info(f"Venta ejecutada exitosamente en {par} con ganancia {ganancia:.4f}")
                operacion_activa = None

            elif precio_actual <= stop_loss:
                kucoin.create_market_order(
                    symbol=par.replace("/", "-"),
                    side='sell',
                    size=str(cantidad)
                )
                ganancia = (precio_actual - precio_entrada) * float(cantidad)
                operaciones_hoy += 1
                ganancia_total_hoy += ganancia
                await bot.send_message(CHAT_ID, f"⚡ Venta por STOP LOSS en {par}\nGanancia/Pérdida: {ganancia:.4f} USDT")
                logging.warning(f"Stop Loss ejecutado en {par}")
                operacion_activa = None

            await asyncio.sleep(2)

        except Exception as e:
            logging.error(f"Error monitoreando operación: {e}")
            await asyncio.sleep(5)

# ─── Comandos de Telegram ──────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ *ZafroBot Scalper PRO* iniciado.\n\nSelecciona una opción:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def encender(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await message.answer("🟢 Bot encendido. Escaneando mercado...")
        asyncio.create_task(analizar_oportunidades())
        asyncio.create_task(monitorear_operacion())
    else:
        await message.answer("⚠️ El bot ya está encendido.")

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def apagar(message: types.Message):
    global bot_encendido
    bot_encendido = False
    await message.answer("🔴 Bot apagado.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def estado(message: types.Message):
    estado_actual = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(
        f"📊 Estado del bot: {estado_actual}\n"
        f"🔹 Operaciones hoy: {operaciones_hoy}\n"
        f"🔹 Ganancia hoy: {ganancia_total_hoy:.4f} USDT",
        reply_markup=keyboard
    )

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def saldo(message: types.Message):
    await actualizar_saldo(message)

@dp.message(lambda m: m.text == "📈 Estado de Orden Actual")
async def orden_actual(message: types.Message):
    if operacion_activa:
        await message.answer(f"🚀 Operación activa en {operacion_activa['par']}", reply_markup=keyboard)
    else:
        await message.answer("❌ No hay operación activa en este momento.", reply_markup=keyboard)

# ─── Arranque Principal ───────────────────────────────────────────────────

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())