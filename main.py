import os
import asyncio
import logging
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

# Variables Globales
bot_encendido = False
operacion_activa = None
pares = ["SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT"]
trailing_stop_pct = -0.08

# Teclado para Telegram
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

# Comando /start
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ ¡Bienvenido al Zafrobot Dinámico Pro Scalping!", reply_markup=keyboard)

# Comandos desde teclado
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
                f"📈 Operación activa en {operacion_activa['par']}\n"
                f"Entrada: {operacion_activa['entrada']:.8f} USDT\n"
                f"Actual: {operacion_activa['actual']:.8f} USDT\n"
                f"Ganancia: {operacion_activa['ganancia']:.4f} USDT ({estado})"
            )
        else:
            await message.answer("⚠️ No hay operaciones activas actualmente.")

# Obtener saldo USDT disponible
def obtener_saldo_disponible():
    try:
        cuentas = user_client.get_account_list()
        saldo_usdt = next((float(x['available']) for x in cuentas if x['currency'] == "USDT" and x['type'] == "trade"), 0.0)
        return saldo_usdt
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return 0.0

# Bucle principal de operaciones
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
                    ticker = market_client.get_ticker(par)
                    logging.debug(f"TICKER DEBUG para {par}: {ticker}")

                    precio_actual = float(ticker.get("price", 0))
                    if precio_actual == 0:
                        logging.warning(f"⚠️ Precio no válido para {par}")
                        continue

                    # Obtener volumen del libro de órdenes nivel 1 (liquidez de compra)
                    order_book = market_client.get_order_book(par, level=1)
                    best_bid = float(order_book["bids"][0][1]) if order_book["bids"] else 0

                    if best_bid == 0:
                        logging.warning(f"⚠️ Volumen de compra no válido para {par}")
                        continue

                    logging.info(f"Analizando {par} | Volumen de compra: {best_bid}")
                    porcentaje_inversion = 0.8 if best_bid > 1000 else 0.5
                    monto_usar = saldo * porcentaje_inversion
                    monto_maximo = best_bid * precio_actual
                    monto_final = min(monto_usar, monto_maximo)
                    logging.info(f"➡️ Monto a usar en {par}: {monto_final}")

                    if monto_final < 5:
                        continue

                    velas = market_client.get_kline(par, "1min", 5)
                    precios = [float(v[2]) for v in velas if float(v[2]) > 0]
                    if not precios:
                        logging.warning(f"⚠️ Velas vacías para {par}")
                        continue

                    promedio_precio = sum(precios) / len(precios)

                    if precio_actual < promedio_precio:
                        cantidad = round(monto_final / precio_actual, 0)
                        trade_client.create_market_order(
                            symbol=par,
                            side="buy",
                            size=str(int(cantidad))
                        )
                        logging.info(f"Comprado {cantidad} de {par} a {precio_actual}")
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

# Monitorear salida con trailing stop
async def monitorear_salida():
    global operacion_activa
    precio_max = operacion_activa["entrada"]

    while True:
        try:
            ticker = market_client.get_ticker(operacion_activa["par"])
            precio_actual = float(ticker["price"])
            if precio_actual > precio_max:
                precio_max = precio_actual

            variacion = (precio_actual - operacion_activa["entrada"]) / operacion_activa["entrada"]
            retroceso = (precio_actual - precio_max) / precio_max

            ganancia = (precio_actual - operacion_activa["entrada"]) * operacion_activa["cantidad"]
            operacion_activa["actual"] = precio_actual
            operacion_activa["ganancia"] = ganancia

            if variacion >= 0.025 or retroceso <= trailing_stop_pct:
                trade_client.create_market_order(
                    symbol=operacion_activa["par"],
                    side="sell",
                    size=str(int(operacion_activa["cantidad"]))
                )
                logging.info(f"✅ VENTA realizada de {operacion_activa['par']} a {precio_actual} USDT")
                operacion_activa = None
                break

        except Exception as e:
            logging.error(f"Error monitoreando salida: {e}")

        await asyncio.sleep(2)

# Iniciar el bot
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())