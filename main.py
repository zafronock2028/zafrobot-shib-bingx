import os
import asyncio
import logging
from kucoin.client import Market, Trade, User
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

# ─── Configuración inicial ───
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

# ─── Variables ───
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

# ─── Funciones ───
async def notificar_telegram(mensaje):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=mensaje)
    except Exception as e:
        logging.error(f"Error enviando mensaje a Telegram: {e}")

def obtener_saldo_disponible():
    try:
        cuentas = user_client.get_account_list()
        saldo = next((float(c["available"]) for c in cuentas if c["currency"] == "USDT" and c["type"] == "trade"), 0.0)
        return saldo
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return 0.0

# ─── Comandos ───
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ ¡Bienvenido al Zafrobot Dinámico Pro Scalping!", reply_markup=keyboard)

@dp.message()
async def comandos(message: types.Message):
    global bot_encendido

    if message.text == "💰 Saldo":
        saldo = obtener_saldo_disponible()
        await message.answer(f"💰 Tu saldo disponible es: {saldo:.2f} USDT")

    elif message.text == "🚀 Encender Bot":
        if not bot_encendido:
            bot_encendido = True
            await message.answer("✅ Bot encendido. Analizando oportunidades...")
            await notificar_telegram("✅ Bot encendido.")
            asyncio.create_task(loop_operaciones())
        else:
            await message.answer("⚠️ El bot ya está encendido.")

    elif message.text == "🛑 Apagar Bot":
        bot_encendido = False
        await message.answer("🛑 Bot apagado.")
        await notificar_telegram("🛑 Bot apagado.")

    elif message.text == "📊 Estado Bot":
        estado = "✅ ENCENDIDO" if bot_encendido else "🛑 APAGADO"
        await message.answer(f"📊 Estado del bot: {estado}")

    elif message.text == "📈 Estado de Orden Actual":
        if operacion_activa:
            await message.answer(
                f"📈 Operación activa en {operacion_activa['par']}\n"
                f"Entrada: {operacion_activa['entrada']:.8f} USDT\n"
                f"Actual: {operacion_activa['actual']:.8f} USDT\n"
                f"Ganancia: {operacion_activa['ganancia']:.4f} USDT"
            )
        else:
            await message.answer("⚠️ No hay operaciones activas.")

# ─── Lógica Principal ───
async def loop_operaciones():
    global operacion_activa

    while bot_encendido:
        try:
            saldo = obtener_saldo_disponible()
            if saldo < 5:
                await asyncio.sleep(10)
                continue

            for par in pares:
                if operacion_activa:
                    break

                try:
                    ticker = market_client.get_ticker(par)
                    precio = float(ticker["price"])
                    orden = market_client.get_order_book_level1(par)
                    volumen = float(orden["size"])

                    if precio == 0 or volumen == 0:
                        continue

                    porcentaje = 0.8 if volumen > 100000 else 0.5
                    monto = min(saldo * porcentaje, volumen * 0.04)

                    if monto < 5:
                        continue

                    velas = market_client.get_kline(par, "1min", 5)
                    precios = [float(v[2]) for v in velas]
                    promedio = sum(precios) / len(precios)

                    if precio < promedio:
                        cantidad = round(monto / precio, 0)
                        trade_client.create_market_order(par, "buy", str(int(cantidad)))

                        operacion_activa = {
                            "par": par,
                            "entrada": precio,
                            "cantidad": cantidad,
                            "actual": precio,
                            "ganancia": 0.0
                        }

                        await notificar_telegram(f"🟢 COMPRA: {par} | Cantidad: {cantidad} | Precio: {precio:.8f}")
                        await monitorear_salida()
                        break

                except Exception as e:
                    logging.error(f"Error en par {par}: {e}")

        except Exception as e:
            logging.error(f"Error general: {e}")

        await asyncio.sleep(3)

# ─── Monitorear salida ───
async def monitorear_salida():
    global operacion_activa
    maximo = operacion_activa["entrada"]

    while True:
        try:
            ticker = market_client.get_ticker(operacion_activa["par"])
            precio = float(ticker["price"])

            if precio > maximo:
                maximo = precio

            variacion = (precio - operacion_activa["entrada"]) / operacion_activa["entrada"]
            retroceso = (precio - maximo) / maximo
            ganancia = (precio - operacion_activa["entrada"]) * operacion_activa["cantidad"]

            operacion_activa["actual"] = precio
            operacion_activa["ganancia"] = ganancia

            if variacion >= 0.025 or retroceso <= trailing_stop_pct:
                trade_client.create_market_order(
                    symbol=operacion_activa["par"],
                    side="sell",
                    size=str(int(operacion_activa["cantidad"]))
                )
                await notificar_telegram(
                    f"🔴 VENTA: {operacion_activa['par']} | Precio: {precio:.8f} | Ganancia: {ganancia:.4f} USDT"
                )
                operacion_activa = None
                break

        except Exception as e:
            logging.error(f"Error monitoreando salida: {e}")

        await asyncio.sleep(2)

# ─── Ejecutar ───
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())