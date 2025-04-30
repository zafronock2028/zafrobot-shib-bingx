import os
import asyncio
import logging
from datetime import datetime
from kucoin.client import Market, Trade, User
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode="Markdown")
dp = Dispatcher()
market_client = Market()
trade_client = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASSPHRASE)
user_client = User(API_KEY, SECRET_KEY, API_PASSPHRASE)

bot_encendido = False
operaciones_activas = []
pares = ["SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT", "TRUMP-USDT", "SUI-USDT", "TURBO-USDT",
         "BONK-USDT", "KAS-USDT", "WIF-USDT", "XMR-USDT", "HYPE-USDT", "HYPER-USDT", "OM-USDT", "ENA-USDT"]
trailing_stop_pct = -0.08
ganancia_objetivo = 0.008
max_operaciones = 3
historial_operaciones = {"ganadas": 1, "perdidas": 1}

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="💰 Saldo")],
        [KeyboardButton(text="📊 Estado Bot")],
        [KeyboardButton(text="📈 Estado de Orden Actual")]
    ],
    resize_keyboard=True
)@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ ¡Bienvenido al Zafrobot Scalper V1!", reply_markup=keyboard)

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
        if operaciones_activas:
            mensaje = ""
            for op in operaciones_activas:
                mensaje += (f"📈 Par: {op['par']} | Entrada: {op['entrada']:.6f} | "
                            f"Actual: {op['actual']:.6f} | Ganancia: {op['ganancia']:.4f} USDT\n")
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ No hay operaciones activas actualmente.")

def obtener_saldo_disponible():
    try:
        cuentas = user_client.get_account_list()
        saldo = next((float(x['available']) for x in cuentas if x['currency'] == "USDT" and x['type'] == "trade"), 0.0)
        return saldo
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return 0.0

def calcular_kelly(win_rate, avg_win=1, avg_loss=1):
    kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
    return max(min(kelly, 1), 0.05)

# Aquí continúa el análisis, compras, monitoreo y ventas (puedo enviarte esa parte si deseas)async def loop_operaciones():
    global bot_encendido, operaciones_activas

    while bot_encendido:
        try:
            if len(operaciones_activas) >= max_operaciones:
                await asyncio.sleep(4)
                continue

            saldo = obtener_saldo_disponible()
            if saldo < 5:
                await asyncio.sleep(5)
                continue

            win_rate = historial_operaciones["ganadas"] / max(1, (historial_operaciones["ganadas"] + historial_operaciones["perdidas"]))
            porcentaje_kelly = calcular_kelly(win_rate)

            for par in pares:
                if len(operaciones_activas) >= max_operaciones:
                    break

                try:
                    stats = market_client.get_24h_stats(par)
                    precio_actual = float(stats.get("last", 0))
                    volumen_24h = float(stats.get("volValue", 0))
                    if volumen_24h < 100000 or precio_actual == 0:
                        continue

                    velas = market_client.get_kline(symbol=par, kline_type="1min", size=5)
                    precios = [float(v[2]) for v in velas]
                    volumenes = [float(v[5]) for v in velas]

                    if len(precios) < 5 or len(volumenes) < 5:
                        continue

                    promedio_precio = sum(precios) / len(precios)
                    volumen_reciente = volumenes[-1]
                    promedio_volumen = sum(volumenes[:-1]) / (len(volumenes) - 1)
                    velas_verdes = sum(1 for v in velas if float(v[2]) > float(v[1]))

                    puntaje = 0
                    if precio_actual < promedio_precio:
                        puntaje += 1
                    if volumen_reciente > promedio_volumen * 1.5:
                        puntaje += 1
                    if velas_verdes >= 3:
                        puntaje += 1

                    logging.info(f"🔍 {par} | Puntaje: {puntaje} | Precio: {precio_actual:.6f} | Vol 24h: {volumen_24h:.2f}")

                    if puntaje >= 1:
                        monto_kelly = saldo * porcentaje_kelly
                        monto_max_vol = volumen_24h * 0.04
                        monto_final = min(monto_kelly, monto_max_vol, saldo * 0.8)

                        if monto_final < 5:
                            continue

                        cantidad = round(monto_final / precio_actual, 2)
                        trade_client.create_market_order(symbol=par, side="buy", size=str(cantidad))

                        operacion = {
                            "par": par,
                            "entrada": precio_actual,
                            "cantidad": cantidad,
                            "actual": precio_actual,
                            "ganancia": 0.0
                        }

                        operaciones_activas.append(operacion)

                        logging.info(f"✅ COMPRA en {par} @ {precio_actual:.6f} | Cantidad: {cantidad}")

                        await bot.send_message(CHAT_ID,
                            f"✅ *COMPRA EJECUTADA*\nPar: `{par}`\nEntrada: `{precio_actual}`\nCantidad: `{cantidad}`\n\n_Esperando oportunidad de salida..._"
                        )
                        asyncio.create_task(monitorear_salida(operacion))

                except Exception as e:
                    logging.error(f"Error analizando {par}: {e}")

        except Exception as e:
            logging.error(f"Error general en loop: {e}")

        await asyncio.sleep(3)async def monitorear_salida(operacion):
    global operaciones_activas
    precio_max = operacion["entrada"]

    while True:
        try:
            ticker = market_client.get_ticker(operacion["par"])
            precio_actual = float(ticker["price"])

            if precio_actual > precio_max:
                precio_max = precio_actual

            variacion = (precio_actual - operacion["entrada"]) / operacion["entrada"]
            retroceso = (precio_actual - precio_max) / precio_max
            ganancia = (precio_actual - operacion["entrada"]) * operacion["cantidad"]

            operacion["actual"] = precio_actual
            operacion["ganancia"] = ganancia

            if variacion >= ganancia_objetivo or retroceso <= trailing_stop_pct:
                trade_client.create_market_order(
                    symbol=operacion["par"],
                    side="sell",
                    size=str(operacion["cantidad"])
                )

                resultado = "✅ *GANANCIA*" if ganancia >= 0 else "❌ *PÉRDIDA*"
                if ganancia >= 0:
                    historial_operaciones["ganadas"] += 1
                else:
                    historial_operaciones["perdidas"] += 1

                logging.info(f"📤 VENTA en {operacion['par']} @ {precio_actual:.6f} | Ganancia: {ganancia:.4f} USDT")

                await bot.send_message(
                    CHAT_ID,
                    f"📤 *VENTA COMPLETADA*\nPar: `{operacion['par']}`\nSalida: `{precio_actual}`\nGanancia: `{ganancia:.4f} USDT`\nResultado: {resultado}"
                )
                operaciones_activas.remove(operacion)
                break

        except Exception as e:
            logging.error(f"Error monitoreando salida en {operacion['par']}: {e}")

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