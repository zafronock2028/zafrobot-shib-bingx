import os
import logging
import asyncio
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from kucoin.client import Market, Trade, User

# Configurar logs
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
logging.getLogger('aiogram').setLevel(logging.WARNING)

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASS = os.getenv("API_PASSPHRASE")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN, parse_mode="Markdown")
dp = Dispatcher()
market = Market()
trade = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASS)
user = User(API_KEY, SECRET_KEY, API_PASS)

# Variables de control
bot_activo = False
operaciones = []
historial = []
pares_activos = []
ultimo_update = datetime.now()
ultimos_pares = {}
lock = asyncio.Lock()
symbol_info_cache = {}
pares_descartados = {}

# Configuración
USO_SALDO = 0.80
MAX_OPS = 3
ESPERA_REENTRADA = 600
GANANCIA_OBJ = 0.004
TRAILING_STOP = -0.007
MIN_ORDEN = 2.5
SCORE_MINIMO = 2
ACTUALIZACION_PARES = 300

# Teclado Telegram
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="⛔ Apagar Bot")],
        [KeyboardButton(text="💰 Saldo")],
        [KeyboardButton(text="📊 Estado Bot")],
        [KeyboardButton(text="📈 Ordenes Activas")],
        [KeyboardButton(text="🧾 Historial")]
    ],
    resize_keyboard=True
)

async def obtener_step_size(par):
    try:
        if par not in symbol_info_cache:
            symbol_info = await asyncio.to_thread(market.get_symbol_list, symbol=par)
            symbol_info_cache[par] = symbol_info[0] if symbol_info else None
        
        info = symbol_info_cache[par]
        return Decimal(info['baseIncrement']) if info else Decimal('0.0001')
    except Exception as e:
        logging.error(f"[STEP SIZE] Error en {par}: {e}")
        return Decimal('0.0001')

async def actualizar_pares_volumen():
    try:
        tickers = await asyncio.to_thread(market.get_all_tickers)
        usdt_pares = []
        
        for t in tickers['ticker']:
            if t['symbol'].endswith('USDT'):
                try:
                    usdt_pares.append({
                        'symbol': t['symbol'],
                        'volumen': float(t['volValue'])
                    })
                except:
                    continue

        usdt_pares.sort(key=lambda x: x['volumen'], reverse=True)
        return [p['symbol'] for p in usdt_pares[:10]]
    
    except Exception as e:
        logging.error(f"[ACTUALIZAR PARES] Error: {e}")
        return None

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ Bot operativo. Usa los botones para controlarlo.", reply_markup=keyboard)

@dp.message()
async def comandos(message: types.Message):
    global bot_activo, pares_activos, ultimo_update
    if message.text == "🚀 Encender Bot":
        if not bot_activo:
            pares_activos = await actualizar_pares_volumen()
            if pares_activos:
                symbol_info_cache.clear()
                await message.answer(f"🔄 Top 10 pares actualizados:\n{', '.join(pares_activos)}")
                ultimo_update = datetime.now()
            
            bot_activo = True
            await message.answer("✅ Bot encendido.")
            asyncio.create_task(ciclo_principal())
        else:
            await message.answer("⚠️ El bot ya está encendido.")
    elif message.text == "⛔ Apagar Bot":
        bot_activo = False
        symbol_info_cache.clear()
        await message.answer("⛔ Bot apagado.")
    elif message.text == "💰 Saldo":
        saldo = await saldo_disponible()
        await message.answer(f"💰 Saldo disponible: `{saldo:.2f}` USDT")
    elif message.text == "📊 Estado Bot":
        estado = "✅ ENCENDIDO" if bot_activo else "⛔ APAGADO"
        await message.answer(f"📊 Estado: {estado}")
    elif message.text == "📈 Ordenes Activas":
        if operaciones:
            mensaje = ""
            for op in operaciones:
                mensaje += (
                    f"• *{op['par']}*\n"
                    f"Entrada: `{op['entrada']:.6f}`\n"
                    f"Actual: `{op['actual']:.6f}`\n"
                    f"Ganancia: `{op['ganancia']:.4f}` USDT\n\n"
                )
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ No hay operaciones activas.")
    elif message.text == "🧾 Historial":
        if historial:
            mensaje = "*Últimas 10 operaciones:*\n\n"
            for h in historial[-10:]:
                mensaje += (
                    f"• {h['fecha']} | *{h['par']}* | {h['resultado']}\n"
                    f"Ganancia: `{h['ganancia']:.4f}` | Saldo: `{h['saldo']:.2f}`\n\n"
                )
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ Historial vacío.")

async def saldo_disponible():
    try:
        cuentas = await asyncio.to_thread(user.get_account_list)
        return next((float(x["available"]) for x in cuentas if x["currency"] == "USDT"), 0.0)
    except Exception as e:
        logging.error(f"[SALDO] Error: {e}")
        return 0.0

async def analizar_par(par):
    try:
        # Verificar si el par está temporalmente descartado
        if par in pares_descartados:
            tiempo_descarte = (datetime.now() - pares_descartados[par]).seconds
            if tiempo_descarte < 300:
                return {"par": par, "valido": False}
            del pares_descartados[par]
        
        # Verificación crítica de velas antes del análisis
        try:
            velas = await asyncio.to_thread(market.get_kline, symbol=par, kline_type="1min", limit=3)
            if len(velas) < 3 or any(len(v) < 6 for v in velas):
                raise ValueError("Datos de vela incompletos")
        except Exception as e:
            if par not in pares_descartados:  # Evitar spam de logs
                logging.warning(f"[{par}] Descarte silencioso: {str(e)}")
            pares_descartados[par] = datetime.now()
            return {"par": par, "valido": False}

        cierres = [float(v[2]) for v in velas]
        volumenes = [float(v[5]) for v in velas]

        c1, c2, c3 = cierres
        v1, v2, v3 = volumenes

        # Obtener volumen 24h
        try:
            stats = await asyncio.to_thread(market.get_24h_stats, par)
            v24h = float(stats["volValue"]) if stats else 0
        except:
            v24h = 0

        # Cálculo de métricas
        momentum = (c3 - c1) / c1
        impulso = (c3 - c2) / c2
        spread = abs(c3 - (sum(cierres) / 3)) / (sum(cierres) / 3)
        volumen_creciente = v3 > v2 > v1

        # Sistema de scoring
        score = sum([
            1 if impulso > 0.0005 else 0,
            1 if momentum > 0.0005 else 0,
            1 if spread < 0.03 else 0,
            1 if v24h > 100000 else 0,
            1 if volumen_creciente else 0
        ])

        logging.info(f"[SCORE] {par} | {score}/5 -> Imp: {impulso:.4f}, Mom: {momentum:.4f}, Spr: {spread:.4f}")

        if score >= SCORE_MINIMO:
            logging.info(f"[SEÑAL] {par} ✅")
            return {"par": par, "precio": c3, "valido": True}
        else:
            pares_descartados[par] = datetime.now()
            return {"par": par, "valido": False}

    except Exception as e:
        if par not in pares_descartados:  # Registrar solo la primera ocurrencia
            logging.warning(f"[{par}] Error crítico: {str(e)}")
        pares_descartados[par] = datetime.now()
        return {"par": par, "valido": False}

async def ciclo_principal():
    global pares_activos, ultimo_update
    while bot_activo:
        async with lock:
            try:
                # Actualizar lista de pares cada 5 minutos
                if (datetime.now() - ultimo_update).seconds > ACTUALIZACION_PARES:
                    nuevos_pares = await actualizar_pares_volumen()
                    if nuevos_pares:
                        pares_activos = nuevos_pares
                        ultimo_update = datetime.now()
                        logging.info(f"🔄 Pares actualizados: {', '.join(pares_activos)}")

                if not pares_activos:
                    await asyncio.sleep(30)
                    continue

                if len(operaciones) >= MAX_OPS:
                    await asyncio.sleep(3)
                    continue

                saldo = await saldo_disponible()
                if saldo < MIN_ORDEN:
                    await asyncio.sleep(10)
                    continue

                monto_por_op = (saldo * USO_SALDO) / MAX_OPS

                for par in pares_activos:
                    if not bot_activo or len(operaciones) >= MAX_OPS:
                        break

                    if par in [op['par'] for op in operaciones]:
                        continue

                    if par in ultimos_pares and (datetime.now() - ultimos_pares[par]).total_seconds() < ESPERA_REENTRADA:
                        continue

                    analisis = await analizar_par(par)
                    if not analisis["valido"]:
                        continue

                    try:
                        step = await obtener_step_size(par)
                        cantidad = Decimal(monto_por_op / analisis["precio"]).quantize(step, rounding=ROUND_DOWN)
                        
                        if float(cantidad) * analisis["precio"] < MIN_ORDEN:
                            continue

                        await asyncio.to_thread(trade.create_market_order, 
                                              symbol=par, 
                                              side="buy", 
                                              size=str(cantidad))
                        
                        op = {
                            "par": par,
                            "entrada": analisis["precio"],
                            "cantidad": float(cantidad),
                            "actual": analisis["precio"],
                            "ganancia": 0.0
                        }
                        operaciones.append(op)
                        ultimos_pares[par] = datetime.now()
                        
                        logging.info(f"[COMPRA] {par} @ {analisis['precio']:.6f}")
                        await bot.send_message(
                            CHAT_ID,
                            f"✅ *COMPRA EJECUTADA*\n"
                            f"• Par: `{par}`\n"
                            f"• Entrada: `{analisis['precio']:.6f}`\n"
                            f"• Cantidad: `{cantidad:.4f}`"
                        )
                        asyncio.create_task(monitorear_operacion(op))

                    except Exception as e:
                        logging.error(f"[COMPRA] Error en {par}: {e}")

                await asyncio.sleep(2)
            except Exception as e:
                logging.error(f"[CICLO] Error: {e}")
                await asyncio.sleep(10)

async def monitorear_operacion(op):
    max_precio = op['entrada']
    while op in operaciones and bot_activo:
        try:
            ticker = await asyncio.to_thread(market.get_ticker, op['par'])
            actual = float(ticker['price'])
            max_precio = max(max_precio, actual)
            
            ganancia_bruta = (actual - op['entrada']) * op['cantidad']
            ganancia_neta = ganancia_bruta - (op['entrada'] * op['cantidad'] * 0.002)
            
            op['actual'] = actual
            op['ganancia'] = ganancia_neta
            
            # Lógica de venta profesional
            take_profit = (actual - op['entrada']) / op['entrada'] >= GANANCIA_OBJ
            stop_loss = (actual - max_precio) / max_precio <= TRAILING_STOP
            
            if take_profit or stop_loss:
                await asyncio.to_thread(
                    trade.create_market_order,
                    symbol=op['par'],
                    side="sell",
                    size=str(Decimal(op['cantidad']).quantize(Decimal('0.0001')))
                )
                
                operaciones.remove(op)
                saldo_actual = await saldo_disponible()
                resultado = "✅ GANADA" if ganancia_neta > 0 else "❌ PERDIDA"
                
                historial.append({
                    "fecha": datetime.now().strftime("%m/%d %H:%M"),
                    "par": op['par'],
                    "ganancia": ganancia_neta,
                    "resultado": resultado,
                    "saldo": saldo_actual
                })
                
                logging.info(f"[VENTA] {op['par']} @ {actual:.6f} | {resultado}")
                await bot.send_message(
                    CHAT_ID,
                    f"🔴 *VENTA EJECUTADA*\n"
                    f"• Par: `{op['par']}`\n"
                    f"• Salida: `{actual:.6f}`\n"
                    f"• Resultado: {resultado}\n"
                    f"• Ganancia Neta: `{ganancia_neta:.4f}` USDT"
                )
                break
            
            await asyncio.sleep(3)
        except Exception as e:
            logging.error(f"[MONITOREO] Error en {op['par']}: {e}")
            await asyncio.sleep(5)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())