import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from kucoin.client import Market, Trade, User

API_KEY = "TU_API_KEY"
SECRET_KEY = "TU_SECRET_KEY"
API_PASS = "TU_API_PASS"
CHAT_ID = "TU_CHAT_ID"
TOKEN = "TU_BOT_TOKEN"

bot = Bot(token=TOKEN)
dp = Dispatcher()

market_client = Market()
trade_client = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASS)
user_client = User(API_KEY, SECRET_KEY, API_PASS)

bot_encendido = False
operaciones_activas = []
max_operaciones = 3
pares = [
    "SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT", "TRUMP-USDT",
    "TURBO-USDT", "BONK-USDT", "KAS-USDT", "WIF-USDT", "SUI-USDT",
    "HYPE-USDT", "HYPER-USDT", "OM-USDT", "ENA-USDT"
]
trailing_stop_pct = -0.08
ganancia_objetivo = 0.008
historial_operaciones = {"ganadas": 1, "perdidas": 1}
min_orden_usdt = 3.0
max_orden_usdt = 6.0keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="⛔ Apagar Bot")],
        [KeyboardButton(text="💰 Saldo")],
        [KeyboardButton(text="📊 Estado Bot")],
        [KeyboardButton(text="📈 Estado de Orden Activa")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ ¡Bienvenido al Zafrobot Scalper V1!", reply_markup=keyboard)

@dp.message()
async def comandos(message: types.Message):
    global bot_encendido

    if message.text == "💰 Saldo":
        saldo = await obtener_saldo_disponible()
        await message.answer(f"💰 Tu saldo disponible es: {saldo:.2f} USDT")

    elif message.text == "🚀 Encender Bot":
        if not bot_encendido:
            bot_encendido = True
            await message.answer("✅ Bot encendido correctamente.")
            asyncio.create_task(loop_operaciones())
        else:
            await message.answer("⚠️ El bot ya está encendido.")

    elif message.text == "⛔ Apagar Bot":
        bot_encendido = False
        await message.answer("⛔ Bot apagado manualmente.")

    elif message.text == "📊 Estado Bot":
        estado = "✅ ENCENDIDO" if bot_encendido else "⛔ APAGADO"
        await message.answer(f"📊 Estado actual del bot: {estado}")

    elif message.text == "📈 Estado de Orden Activa":
        if operaciones_activas:
            mensaje = ""
            for op in operaciones_activas:
                estado = "GANANCIA ✅" if op["ganancia"] > 0 else "PERDIENDO ❌"
                mensaje += (
                    f"📈 Par: {op['par']}\n"
                    f"Entrada: {op['entrada']:.6f} USDT\n"
                    f"Actual: {op['actual']:.6f} USDT\n"
                    f"Ganancia: {op['ganancia']:.6f} USDT ({estado})\n\n"
                )
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ No hay operaciones activas actualmente.")async def obtener_saldo_disponible():
    try:
        cuentas = user_client.get_account_list()
        saldo = next((float(x["available"]) for x in cuentas if x["currency"] == "USDT"), 0.0)
        return saldo
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return 0.0

def calcular_kelly(win_rate, avg_win=1, avg_loss=1):
    kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
    return max(min(kelly, 1), 0.05)

def analizar_par(par):
    try:
        velas = market_client.get_kline(symbol=par, kline_type="1min", limit=5)
        precios = [float(x[2]) for x in velas]
        promedio = sum(precios) / len(precios)
        actual = precios[-1]
        volumen_24h = float(market_client.get_24h_stats(par)["volValue"])
        spread = abs(actual - promedio) / promedio
        puntaje = 0
        if actual > promedio:
            puntaje += 1
        if spread < 0.02:
            puntaje += 1
        if volumen_24h > 500000:
            puntaje += 1
        return {
            "puntaje": puntaje,
            "precio": actual,
            "volumen": volumen_24h
        }
    except Exception as e:
        logging.error(f"Error analizando par {par}: {e}")
        return {"puntaje": 0, "precio": 0.0, "volumen": 0.0}async def loop_operaciones():
    global bot_encendido, operaciones_activas

    while bot_encendido:
        if len(operaciones_activas) >= max_operaciones:
            await asyncio.sleep(4)
            continue

        saldo = await obtener_saldo_disponible()
        if saldo < min_orden_usdt:
            await asyncio.sleep(10)
            continue

        win_rate = historial_operaciones["ganadas"] / (historial_operaciones["ganadas"] + historial_operaciones["perdidas"])
        porcentaje_kelly = calcular_kelly(win_rate)

        for par in pares:
            if len(operaciones_activas) >= max_operaciones:
                break

            analisis = analizar_par(par)
            if analisis["puntaje"] >= 2:
                monto_inversion = max(min(saldo * porcentaje_kelly, max_orden_usdt), min_orden_usdt)
                if monto_inversion > saldo:
                    continue

                cantidad = round(monto_inversion / analisis["precio"], 2)

                try:
                    orden = trade_client.create_market_order(symbol=par, side="buy", size=str(cantidad))
                    operacion = {
                        "par": par,
                        "entrada": analisis["precio"],
                        "cantidad": cantidad,
                        "ganancia": 0.0,
                        "actual": analisis["precio"]
                    }
                    operaciones_activas.append(operacion)

                    logging.info(f"✅ COMPRA EJECUTADA en {par} | Entrada: {analisis['precio']} | Cantidad: {cantidad}")
                    await bot.send_message(
                        CHAT_ID,
                        f"✅ *COMPRA EJECUTADA*\nPar: `{par}`\nEntrada: `{analisis['precio']:.6f}`\nCantidad: `{cantidad}`"
                    )
                    asyncio.create_task(monitorear_salida(operacion))
                except Exception as e:
                    logging.error(f"Error ejecutando orden en {par}: {e}")

        await asyncio.sleep(5)async def monitorear_salida(operacion):
    global operaciones_activas, historial_operaciones

    entrada = operacion["entrada"]
    cantidad = operacion["cantidad"]
    par = operacion["par"]
    max_precio = entrada

    while True:
        try:
            actual = float(market_client.get_ticker(par)["price"])
            max_precio = max(max_precio, actual)
            variacion = (actual - entrada) / entrada
            retroceso = (actual - max_precio) / max_precio

            ganancia = (actual - entrada) * cantidad
            operacion["actual"] = actual
            operacion["ganancia"] = ganancia

            if variacion >= ganancia_objetivo or retroceso <= trailing_stop_pct:
                trade_client.create_market_order(symbol=par, side="sell", size=str(cantidad))
                operaciones_activas.remove(operacion)
                resultado = "✅ GANANCIA" if ganancia >= 0 else "❌ PÉRDIDA"

                if ganancia >= 0:
                    historial_operaciones["ganadas"] += 1
                else:
                    historial_operaciones["perdidas"] += 1

                logging.info(f"🔴 VENTA en {par} | Salida: {actual} | Resultado: {resultado}")
                await bot.send_message(
                    CHAT_ID,
                    f"🔴 *VENTA EJECUTADA*\nPar: `{par}`\nSalida: `{actual:.6f}`\nGanancia: `{ganancia:.4f} USDT`\nResultado: {resultado}"
                )
                break
        except Exception as e:
            logging.error(f"Error monitoreando salida de {par}: {e}")
        await asyncio.sleep(4)

# Iniciar el bot
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())