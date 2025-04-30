import os
import asyncio
import logging
from datetime import datetime
from kucoin.client import Market, Trade, User
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
logging.basicConfig(level=logging.INFO)

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

user_client = User(API_KEY, SECRET_KEY, API_PASSPHRASE)
market_client = Market()
trade_client = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASSPHRASE)

bot_encendido = False
operacion_activa = None
pares = ["SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT"]
trailing_stop_pct = -0.08

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="💰 Saldo")],
        [KeyboardButton(text="📊 Estado Bot")],
        [KeyboardButton(text="📈 Estado de Orden Actual")],
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ ¡Bienvenido al Zafrobot Dinámico Pro Scalping!", reply_markup=keyboard)

@dp.message()
async def comandos_principales(message: types.Message):
    global bot_encendido, operacion_activa

    if message.text == "💰 Saldo":
        saldo = obtener_saldo_disponible()
        await message.answer(f"💰 Tu saldo disponible es: {saldo:.2f} USDT")

    elif message.text == "🚀 Encender Bot":
        if not bot_encendido:
            bot_encendido = True
            await message.answer("✅ Bot encendido. Analizando oportunidades...")
            asyncio.create_task(loop_operaciones())
        else:
            await message.answer("⚠️ El bot ya está encendido.")

    elif message.text == "🛑 Apagar Bot":
        bot_encendido = False
        await message.answer("🛑 Bot apagado manualmente.")

    elif message.text == "📊 Estado Bot":
        estado = "✅ ENCENDIDO" if bot_encendido else "🛑 APAGADO"
        await message.answer(f"📊 Estado actual del bot: {estado}")

    elif message.text == "📈 Estado de Orden Actual":
        if operacion_activa:
            estado = "GANANCIA ✅" if operacion_activa["ganancia"] >= 0 else "PÉRDIDA ❌"
            await message.answer(
                f"📈 Operación activa en {operacion_activa['par']}
"
                f"Entrada: {operacion_activa['entrada']:.6f} USDT
"
                f"Actual: {operacion_activa['actual']:.6f} USDT
"
                f"Ganancia: {operacion_activa['ganancia']:.6f} USDT ({estado})"
            )
        else:
            await message.answer("⚠️ No hay operaciones activas actualmente.")

def obtener_saldo_disponible():
    try:
        cuentas = user_client.get_account_list()
        saldo_usdt = next((float(x['available']) for x in cuentas if x['currency'] == "USDT" and x['type'] == "trade"), 0.0)
        return saldo_usdt
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return 0.0

async def loop_operaciones():
    global bot_encendido, operacion_activa

    while bot_encendido:
        try:
            saldo = obtener_saldo_disponible()
            if saldo < 5:
                logging.warning("Saldo insuficiente para operar.")
                await asyncio.sleep(10)
                continue

            for par in pares:
                if operacion_activa:
                    break

                try:
                    stats = market_client.get_24h_stats(par)
                    precio_actual = float(stats.get("last", 0))
                    volumen_24h = float(stats.get("volValue", 0))

                    logging.info(f"🧠 Analizando {par} | Precio: {precio_actual} | Volumen 24h: {volumen_24h}")

                    if volumen_24h == 0 or precio_actual == 0:
                        logging.warning(f"⚠️ Datos no válidos para {par}")
                        continue

                    porcentaje_inversion = 0.8 if volumen_24h > 100000 else 0.5
                    monto_usar = saldo * porcentaje_inversion
                    monto_max_volumen = volumen_24h * 0.04
                    monto_final = min(monto_usar, monto_max_volumen)

                    if monto_final < 5:
                        continue

                    velas = market_client.get_kline(symbol=par, kline_type="1min", size=5)
                    precios = [float(v[2]) for v in velas]
                    if not precios:
                        continue

                    promedio_precio = sum(precios) / len(precios)
                    if precio_actual < promedio_precio:
                        cantidad = round(monto_final / precio_actual, 2)
                        trade_client.create_market_order(
                            symbol=par,
                            side="buy",
                            size=str(cantidad)
                        )
                        operacion_activa = {
                            "par": par,
                            "entrada": precio_actual,
                            "cantidad": cantidad,
                            "actual": precio_actual,
                            "ganancia": 0.0
                        }
                        await monitorear_salida()
                        break

                except Exception as e:
                    logging.error(f"Error procesando par {par}: {e}")
                    continue

        except Exception as e:
            logging.error(f"Error general en loop_operaciones: {e}")
            await asyncio.sleep(5)
            continue

        await asyncio.sleep(2)

async def monitorear_salida():
    global operacion_activa
    precio_max = operacion_activa["entrada"]

    while True:
        try:
            stats = market_client.get_24h_stats(operacion_activa["par"])
            precio_actual = float(stats["last"])
            if precio_actual > precio_max:
                precio_max = precio_actual

            variacion = (precio_actual - operacion_activa["entrada"]) / operacion_activa["entrada"]
            retroceso = (precio_actual - precio_max) / precio_max

            ganancia_actual = (precio_actual - operacion_activa["entrada"]) * operacion_activa["cantidad"]
            operacion_activa["actual"] = precio_actual
            operacion_activa["ganancia"] = ganancia_actual

            if variacion >= 0.02 or retroceso <= trailing_stop_pct:
                trade_client.create_market_order(
                    symbol=operacion_activa["par"],
                    side="sell",
                    size=str(operacion_activa["cantidad"])
                )
                operacion_activa = None
                break

        except Exception as e:
            logging.error(f"Error monitoreando salida: {e}")

        await asyncio.sleep(2)

async def main():
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            logging.error(f"Error en polling: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())