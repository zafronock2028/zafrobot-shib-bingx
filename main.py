import os
import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from kucoin.client import Trade, Market, User
from dotenv import load_dotenv

# ------------------------- CONFIGURACIÓN INICIAL -------------------------
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)

# ------------------------- VARIABLES DE ENTORNO -------------------------
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

# ------------------------- INICIALIZACIÓN DE CLIENTES -------------------------
try:
    market = Market(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASSPHRASE)
    trade = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASSPHRASE)
    user = User(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASSPHRASE)
    bot = Bot(token=TELEGRAM_TOKEN, parse_mode="Markdown")
    dp = Dispatcher()
    logging.info("Clientes inicializados correctamente")
except Exception as e:
    logging.error(f"Error inicializando clientes: {e}")
    raise

# ------------------------- VARIABLES DE ESTADO -------------------------
bot_activo = False
operaciones = []
historial = []
ultimos_pares = {}
lock = asyncio.Lock()

# ------------------------- CONFIGURACIÓN DEL TRADING -------------------------
PARES_ACTIVOS = [
    "SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT", "TRUMP-USDT",
    "SUI-USDT", "TURBO-USDT", "BONK-USDT", "KAS-USDT", "WIF-USDT"
]

CONFIG = {
    'uso_saldo': 0.80,
    'max_operaciones': 3,
    'espera_reentrada': 600,
    'ganancia_objetivo': 0.004,
    'stop_loss': -0.007,
    'orden_minima': 2.5,
    'step_sizes': {
        "SUI-USDT": 0.1, "TRUMP-USDT": 0.01, "BONK-USDT": 0.01,
        "TURBO-USDT": 0.01, "WIF-USDT": 0.01
    }
}

# ------------------------- TECLADO DE TELEGRAM -------------------------
def crear_teclado():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Encender Bot")],
            [KeyboardButton(text="⛔ Apagar Bot")],
            [KeyboardButton(text="💰 Saldo")],
            [KeyboardButton(text="📊 Estado")],
            [KeyboardButton(text="📈 Operaciones")],
            [KeyboardButton(text="🧾 Historial")]
        ],
        resize_keyboard=True
    )

# ------------------------- HANDLERS DE TELEGRAM -------------------------
@dp.message(Command("start"))
async def comando_inicio(message: types.Message):
    await message.answer("🤖 Bot de Trading Activo", reply_markup=crear_teclado())

@dp.message()
async def manejar_comandos(message: types.Message):
    global bot_activo
    
    texto = message.text
    if texto == "🚀 Encender Bot" and not bot_activo:
        bot_activo = True
        asyncio.create_task(ejecutar_ciclo())
        await message.answer("✅ Bot activado")
    elif texto == "⛔ Apagar Bot":
        bot_activo = False
        await message.answer("🔴 Bot detenido")
    elif texto == "💰 Saldo":
        saldo = await obtener_saldo_disponible()
        await message.answer(f"💵 Saldo disponible: {saldo:.2f} USDT")
    elif texto == "📊 Estado":
        estado = "🟢 ACTIVO" if bot_activo else "🔴 INACTIVO"
        await message.answer(f"Estado del bot: {estado}")
    elif texto == "📈 Operaciones":
        await mostrar_operaciones_activas(message)
    elif texto == "🧾 Historial":
        await mostrar_historial(message)

# ------------------------- LÓGICA PRINCIPAL DEL TRADING -------------------------
async def ejecutar_ciclo():
    while bot_activo:
        try:
            async with lock:
                if len(operaciones) >= CONFIG['max_operaciones']:
                    await asyncio.sleep(3)
                    continue

                saldo = await obtener_saldo_disponible()
                if saldo < CONFIG['orden_minima']:
                    await asyncio.sleep(10)
                    continue

                monto = (saldo * CONFIG['uso_saldo']) / CONFIG['max_operaciones']
                
                for par in PARES_ACTIVOS:
                    if not bot_activo:
                        break
                        
                    if any(op['par'] == par for op in operaciones):
                        continue
                        
                    if par in ultimos_pares and (datetime.now() - ultimos_pares[par]).seconds < CONFIG['espera_reentrada']:
                        continue

                    señal = await analizar_par(par)
                    if señal['valido']:
                        await ejecutar_compra(par, señal['precio'], monto)
                        await asyncio.sleep(2)
                        break
            
            await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error en ciclo principal: {e}")
            await asyncio.sleep(5)

async def analizar_par(par):
    try:
        velas = market.get_kline(symbol=par, kline_type="1min", limit=5)
        precios = [float(v[2]) for v in velas]
        ultimo = precios[-1]
        media = sum(precios) / len(precios)
        desviacion = abs(ultimo - media) / media
        
        stats = market.get_24h_stats(symbol=par)
        volumen = float(stats['volValue'])
        cambio = (precios[-1] - precios[-2]) / precios[-2]
        
        if (cambio > 0.001 and desviacion < 0.02 and volumen > 500000):
            logging.info(f"Señal válida en {par} | Precio: {ultimo:.6f}")
            return {'par': par, 'precio': ultimo, 'valido': True}
            
    except Exception as e:
        logging.error(f"Error analizando {par}: {e}")
    
    return {'par': par, 'valido': False}

async def ejecutar_compra(par, precio, monto):
    try:
        step = Decimal(str(CONFIG['step_sizes'].get(par, 0.0001)))
        cantidad = (Decimal(str(monto)) / Decimal(str(precio)))
        cantidad = (cantidad // step) * step
        
        orden = trade.create_market_order(
            symbol=par,
            side='buy',
            size=str(cantidad)
        )
        
        nueva_operacion = {
            'par': par,
            'entrada': float(precio),
            'cantidad': float(cantidad),
            'maximo': float(precio),
            'ganancia': 0.0
        }
        
        operaciones.append(nueva_operacion)
        logging.info(f"Compra ejecutada: {par} {cantidad} @ {precio}")
        await bot.send_message(
            TELEGRAM_CHAT_ID,
            f"🟢 COMPRA: {par}\n"
            f"Precio: {precio:.6f}\n"
            f"Cantidad: {float(cantidad):.2f}"
        )
        
        asyncio.create_task(monitorear_operacion(nueva_operacion))
        
    except Exception as e:
        logging.error(f"Error en compra {par}: {e}")
        await bot.send_message(TELEGRAM_CHAT_ID, f"❌ Error en compra {par}: {str(e)}")

async def monitorear_operacion(op):
    while op in operaciones and bot_activo:
        try:
            ticker = market.get_ticker(symbol=op['par'])
            precio_actual = float(ticker['price'])
            
            if precio_actual > op['maximo']:
                op['maximo'] = precio_actual
            
            ganancia = (precio_actual - op['entrada']) * op['cantidad']
            op['ganancia'] = ganancia
            
            ganancia_porcentaje = (precio_actual - op['entrada']) / op['entrada']
            drawdown = (precio_actual - op['maximo']) / op['maximo']
            
            if (ganancia_porcentaje >= CONFIG['ganancia_objetivo'] or 
                drawdown <= CONFIG['stop_loss']):
                
                await ejecutar_venta(op)
                break
                
            await asyncio.sleep(3)
        except Exception as e:
            logging.error(f"Error monitoreando {op['par']}: {e}")
            await asyncio.sleep(5)

async def ejecutar_venta(op):
    try:
        orden = trade.create_market_order(
            symbol=op['par'],
            side='sell',
            size=str(op['cantidad'])
        )
        
        ganancia = op['ganancia']
        resultado = "GANANCIA" if ganancia > 0 else "PERDIDA"
        
        historial.append({
            'fecha': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'par': op['par'],
            'resultado': resultado,
            'ganancia': ganancia
        })
        
        operaciones.remove(op)
        ultimos_pares[op['par']] = datetime.now()
        
        logging.info(f"Venta ejecutada: {op['par']} Ganancia: {ganancia:.4f}")
        await bot.send_message(
            TELEGRAM_CHAT_ID,
            f"🔴 VENTA: {op['par']}\n"
            f"Precio: {op['maximo']:.6f}\n"
            f"Ganancia: {ganancia:.4f} {resultado}"
        )
        
    except Exception as e:
        logging.error(f"Error en venta {op['par']}: {e}")
        await bot.send_message(TELEGRAM_CHAT_ID, f"❌ Error en venta {op['par']}: {str(e)}")

# ------------------------- FUNCIONES AUXILIARES -------------------------
async def obtener_saldo_disponible():
    try:
        cuentas = user.get_account_list()
        cuenta_usdt = next(
            (c for c in cuentas if c['currency'] == 'USDT' and c['type'] == 'trade'),
            None
        )
        return float(cuenta_usdt['balance']) if cuenta_usdt else 0.0
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return 0.0

async def mostrar_operaciones_activas(message: types.Message):
    if not operaciones:
        await message.answer("No hay operaciones activas")
        return
    
    mensaje = "📊 Operaciones Activas:\n\n"
    for op in operaciones:
        mensaje += (
            f"Par: {op['par']}\n"
            f"Entrada: {op['entrada']:.6f}\n"
            f"Actual: {op['maximo']:.6f}\n"
            f"Ganancia: {op['ganancia']:.4f} USDT\n\n"
        )
    await message.answer(mensaje)

async def mostrar_historial(message: types.Message):
    if not historial:
        await message.answer("Historial vacío")
        return
    
    mensaje = "📜 Últimas 10 operaciones:\n\n"
    for op in historial[-10:]:
        mensaje += (
            f"{op['fecha']} - {op['par']} - "
            f"{op['resultado']} - {op['ganancia']:.4f} USDT\n"
        )
    await message.answer(mensaje)

# ------------------------- INICIO DE LA APLICACIÓN -------------------------
async def iniciar_bot():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(iniciar_bot())