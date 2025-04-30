import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from kucoin.client import Market, Trade, User
import os

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASS = os.getenv("API_PASS")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

market_client = Market()
trade_client = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASS)
user_client = User(API_KEY, SECRET_KEY, API_PASS)

bot_encendido = False
operaciones_activas = []
max_operaciones = 3
pares = [
    "SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT",
    "TURBO-USDT", "BONK-USDT", "KAS-USDT", "WIF-USDT",
    "OM-USDT", "HYPE-USDT", "TRUMP-USDT", "ENA-USDT",
    "SUI-USDT"
]
trailing_stop_pct = -0.08
ganancia_objetivo = 0.008
historial_operaciones = {"ganadas": 1, "perdidas": 1}
min_orden_usdt = 3.0
max_orden_usdt = 6.0

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="💲 Saldo")],
        [KeyboardButton(text="📊 Estado Bot")],
        [KeyboardButton(text="📈 Estado de Orden Activa")]
    ],
    resize_keyboard=True
)@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ ¡Bienvenido al Zafrobot Scalper V1 Pro!", reply_markup=keyboard)

@dp.message()
async def comandos(message: types.Message):
    global bot_encendido

    if message.text == "💲 Saldo":
        saldo = obtener_saldo_disponible()
        await message.answer(f"💰 Tu saldo disponible es: *{saldo:.2f} USDT*")

    elif message.text == "🚀 Encender Bot":
        if not bot_encendido:
            bot_encendido = True
            await message.answer("✅ Bot encendido. Escaneando pares en tiempo real...")
            asyncio.create_task(loop_operaciones())
        else:
            await message.answer("⚠️ El bot ya está encendido.")

    elif message.text == "🛑 Apagar Bot":
        bot_encendido = False
        await message.answer("🛑 Bot apagado manualmente.")

    elif message.text == "📊 Estado Bot":
        estado = "✅ ENCENDIDO" if bot_encendido else "🛑 APAGADO"
        await message.answer(f"📊 Estado actual del bot: {estado}")

    elif message.text == "📈 Estado de Orden Activa":
        if operaciones_activas:
            for op in operaciones_activas:
                estado = "GANANCIA ✅" if op["ganancia"] >= 0 else "PÉRDIDA ❌"
                await message.answer(
                    f"📈 *Par:* {op['par']}\n"
                    f"*Entrada:* {op['entrada']:.6f} USDT\n"
                    f"*Actual:* {op['actual']:.6f} USDT\n"
                    f"*Ganancia:* {op['ganancia']:.6f} USDT ({estado})"
                )
        else:
                await message.answer("⚠️ No hay operaciones activas actualmente.")

def obtener_saldo_disponible():
    try:
        cuentas = user_client.get_account_list()
        saldo = next((float(x["available"]) for x in cuentas if x["currency"] == "USDT"), 0.0)
        return saldo
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return 0.0

def calcular_kelly(win_rate, avg_win=1, avg_loss=1):
    try:
        kelly = (win_rate * avg_win - (1 - win_rate)) / avg_loss
        return max(min(kelly, 1), 0.05)
    except:
        return 0.05

def analizar_par(par):
    try:
        velas = market_client.get_kline(symbol=par, kline_type="1min", limit=5)
        precios = [float(x[2]) for x in velas]
        promedio = sum(precios) / len(precios)
        actual = precios[-1]
        volumen_24h = float(market_client.get_24h_stats(par)["volValue"])
        volumen_reciente = float(velas[-1][5])
        puntaje = 0

        if actual > promedio:
            puntaje += 1
        if volumen_reciente > volumen_24h * 0.001:
            puntaje += 1
        if abs(actual - promedio) / promedio >= 0.005:
            puntaje += 1

        logging.info(f"🔍 {par} | Puntaje: {puntaje} | Precio: {actual:.6f} | Vol24h: {volumen_24h:.2f}")
        return {"par": par, "precio": actual, "puntaje": puntaje}
    except Exception as e:
        logging.warning(f"Error analizando {par}: {e}")
        return {"par": par, "precio": 0, "puntaje": 0}

def ejecutar_compra(par, cantidad):
    try:
        return trade_client.create_market_order(symbol=par, side="buy", size=round(cantidad, 6))
    except Exception as e:
        logging.error(f"Error ejecutando compra en {par}: {e}")
        return Noneasync def loop_operaciones():
    global bot_encendido, operaciones_activas

    while bot_encendido:
        if len(operaciones_activas) >= max_operaciones:
            await asyncio.sleep(3)
            continue

        saldo = obtener_saldo_disponible()
        if saldo < min_orden_usdt:
            await asyncio.sleep(5)
            continue

        win_rate = historial_operaciones["ganadas"] / max((historial_operaciones["ganadas"] + historial_operaciones["perdidas"]), 1)
        porcentaje_kelly = calcular_kelly(win_rate)

        for par in pares:
            if len(operaciones_activas) >= max_operaciones:
                break

            info = analizar_par(par)
            if info["puntaje"] >= 2:
                monto_inversion = min(saldo * porcentaje_kelly, max_orden_usdt)
                if monto_inversion < min_orden_usdt:
                    continue

                cantidad = monto_inversion / info["precio"]
                resultado = ejecutar_compra(par, cantidad)

                if resultado:
                    operacion = {
                        "par": par,
                        "entrada": info["precio"],
                        "cantidad": cantidad,
                        "ganancia": 0.0,
                        "id": resultado["orderOid"],
                        "actual": info["precio"]
                    }
                    operaciones_activas.append(operacion)

                    logging.info(f"🟢 COMPRA: {par} | Entrada: {info['precio']} | Cantidad: {cantidad}")
                    await bot.send_message(
                        CHAT_ID,
                        f"🟢 *COMPRA EJECUTADA*\nPar: `{par}`\nEntrada: `{info['precio']:.6f}`\nCantidad: `{cantidad:.2f}`"
                    )
                    asyncio.create_task(monitorear_salida(operacion))

        await asyncio.sleep(3)

async def monitorear_salida(operacion):
    global historial_operaciones, operaciones_activas
    try:
        entrada = operacion["entrada"]
        cantidad = operacion["cantidad"]
        par = operacion["par"]
        max_precio = entrada

        while True:
            actual = float(market_client.get_ticker(par)["price"])
            max_precio = max(max_precio, actual)
            cambio_pct = (actual - entrada) / entrada
            trailing_trigger = (max_precio - actual) / max_precio

            operacion["actual"] = actual
            operacion["ganancia"] = (actual - entrada) * cantidad

            if cambio_pct >= ganancia_objetivo or trailing_trigger >= abs(trailing_stop_pct):
                trade_client.create_market_order(symbol=par, side="sell", size=round(cantidad, 6))
                operaciones_activas.remove(operacion)
                historial_operaciones["ganadas" if cambio_pct > 0 else "perdidas"] += 1

                logging.info(f"🔴 VENTA: {par} | Salida: {actual} | Ganancia: {operacion['ganancia']:.4f}")
                await bot.send_message(
                    CHAT_ID,
                    f"🔴 *VENTA EJECUTADA*\nPar: `{par}`\nSalida: `{actual:.6f}`\nGanancia: `{operacion['ganancia']:.4f} USDT`"
                )
                break
            await asyncio.sleep(5)
    except Exception as e:
        logging.error(f"Error en monitoreo de salida: {e}")
        if operacion in operaciones_activas:
            operaciones_activas.remove(operacion)async def main():
    logging.basicConfig(level=logging.INFO)
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Error en polling: {e}")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())