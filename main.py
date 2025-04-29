import os
import asyncio
import logging
from datetime import datetime
from kucoin.client import Market, Trade, User
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

# ─── Cargar Variables de Entorno ───────────────────────
load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

# ─── Configuración de Logs ─────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Inicialización de Clientes ────────────────────────
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

user_client = User(API_KEY, SECRET_KEY, API_PASSPHRASE)
market_client = Market()
trade_client = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASSPHRASE)

# ─── Configuraciones de Trading ────────────────────────
bot_encendido = False
pares = ["PEPE-USDT", "FLOKI-USDT", "SHIB-USDT", "DOGE-USDT"]
trailing_stop_pct = -0.08  # -8%
operacion_activa = None

# ─── Teclado de Telegram ───────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="💰 Saldo")],
        [KeyboardButton(text="📊 Estado Bot")],
        [KeyboardButton(text="📈 Estado de Orden Actual")],
    ],
    resize_keyboard=True
)@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("¡Bienvenido al Zafrobot Dinámico Pro Scalping!", reply_markup=keyboard)

@dp.message()
async def manejar_comandos(message: types.Message):
    global bot_encendido

    if message.text == "🚀 Encender Bot":
        if not bot_encendido:
            bot_encendido = True
            await message.answer("✅ Bot encendido. Analizando mercado...")
            asyncio.create_task(operar_en_ciclo())
        else:
            await message.answer("⚠️ El bot ya está encendido.")

    elif message.text == "🛑 Apagar Bot":
        bot_encendido = False
        await message.answer("🛑 Bot apagado manualmente.")

    elif message.text == "💰 Saldo":
        saldo = obtener_saldo_disponible()
        await message.answer(f"💰 Tu saldo disponible en Trading Wallet es: {saldo:.2f} USDT")

    elif message.text == "📊 Estado Bot":
        estado = "🟢 ENCENDIDO" if bot_encendido else "🔴 APAGADO"
        await message.answer(f"📊 Estado actual del bot: {estado}")

    elif message.text == "📈 Estado de Orden Actual":
        if operacion_activa:
            estado = "✅ GANANCIA" if operacion_activa["ganancia"] >= 0 else "❌ PÉRDIDA"
            await message.answer(
                f"📈 Orden activa en {operacion_activa['par']}\n"
                f"Entrada: {operacion_activa['entrada']:.6f} USDT\n"
                f"Actual: {operacion_activa['actual']:.6f} USDT\n"
                f"Ganancia: {operacion_activa['ganancia']:.6f} USDT ({estado})"
            )
        else:
            await message.answer("⚠️ No hay operaciones activas.")async def operar_en_ciclo():
    global bot_encendido, operacion_activa

    while bot_encendido:
        try:
            saldo = obtener_saldo_disponible()
            if saldo < 5:
                logging.info("Saldo insuficiente para operar.")
                await asyncio.sleep(30)
                continue

            for par in pares:
                if not bot_encendido:
                    break

                try:
                    ticker = market_client.get_ticker(par)
                    volumen_24h = float(ticker['volValue'])  # Volumen en USDT

                    # Aplicar Kelly y limitar al 4% del volumen
                    maximo_por_volumen = volumen_24h * 0.04
                    porcentaje = 0.8 if volumen_24h > 1_000_000 else 0.3
                    inversion_base = saldo * porcentaje
                    monto_invertir = min(inversion_base, maximo_por_volumen)

                    # Validar monto contra mínimos de compra
                    precio = float(ticker['price'])
                    if monto_invertir < 5:
                        continue
                    cantidad = round(monto_invertir / precio, 4)

                    # Obtener últimas 5 velas y analizar patrón
                    velas = market_client.get_kline(par, '1min', 5)
                    precios_cierre = [float(k[2]) for k in velas]
                    promedio = sum(precios_cierre) / len(precios_cierre)

                    if precio < promedio * 0.99:  # Entrada potencial
                        logging.info(f"COMPRA en {par}: {cantidad} a {precio}")
                        trade_client.create_market_order(par, 'buy', size=str(cantidad))

                        operacion_activa = {
                            "par": par,
                            "entrada": precio,
                            "cantidad": cantidad,
                            "ganancia": 0.0
                        }

                        await monitorear_salida(par, cantidad, precio)
                        break  # Solo una operación a la vez

                except Exception as e:
                    logging.error(f"Error analizando {par}: {e}")

            await asyncio.sleep(2)

        except Exception as e:
            logging.error(f"Error general del ciclo: {e}")
            await asyncio.sleep(10)async def monitorear_salida(par, cantidad, precio_entrada):
    global operacion_activa

    precio_max = precio_entrada
    trailing_stop = trailing_stop_pct

    while True:
        try:
            ticker = market_client.get_ticker(par)
            precio_actual = float(ticker['price'])

            if precio_actual > precio_max:
                precio_max = precio_actual

            variacion = (precio_actual - precio_entrada) / precio_entrada
            retroceso = (precio_actual - precio_max) / precio_max

            ganancia_actual = (precio_actual - precio_entrada) * cantidad
            operacion_activa["actual"] = precio_actual
            operacion_activa["ganancia"] = ganancia_actual

            if variacion >= 0.025 or retroceso <= trailing_stop:
                logging.info(f"VENTA en {par} a {precio_actual}, ganancia: {ganancia_actual:.2f} USDT")
                trade_client.create_market_order(par, 'sell', size=str(cantidad))
                operacion_activa = None
                break

        except Exception as e:
            logging.error(f"Error monitoreando salida en {par}: {e}")

        await asyncio.sleep(2)# ─── Iniciar el bot ─────────────────────────────
async def main():
    try:
        logging.info("Iniciando Zafrobot Dinámico Pro Scalping...")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Error al iniciar el bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())