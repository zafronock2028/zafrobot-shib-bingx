import os
import logging
import asyncio
from datetime import datetime
from decimal import Decimal
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
        logging.FileHandler('trading_bot.log')
    ]
)
logger = logging.getLogger(__name__)

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
    logger.info("Clientes inicializados correctamente")
except Exception as e:
    logger.error(f"Error inicializando clientes: {e}")
    raise

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
    'orden_minima': 15,
    'min_order_usd': {
        "TRUMP-USDT": 15,
        "PEPE-USDT": 5,
        "SHIB-USDT": 5,
        "DOGE-USDT": 10,
        "BONK-USDT": 5,
        "WIF-USDT": 10,
        "SUI-USDT": 5,
        "TURBO-USDT": 5,
        "FLOKI-USDT": 5,
        "KAS-USDT": 5
    }
}

# ------------------------- ESTADO GLOBAL -------------------------
bot_activo = False
operaciones = []
historial = []
ultimos_pares = {}
lock = asyncio.Lock()

# ------------------------- FUNCIONES AUXILIARES -------------------------
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

async def obtener_saldo_disponible():
    try:
        cuentas = user.get_account_list()
        cuenta_usdt = next(
            (c for c in cuentas if c['currency'] == 'USDT' and c['type'] == 'trade'),
            None
        )
        return float(cuenta_usdt['balance']) if cuenta_usdt else 0.0
    except Exception as e:
        logger.error(f"Error obteniendo saldo: {e}")
        return 0.0

# ------------------------- FUNCIONES DE TRADING -------------------------
async def analizar_par(par):
    try:
        velas = market.get_kline(symbol=par, kline_type="1min", limit=5)
        precios = [float(v[2]) for v in velas]
        ultimo = precios[-1]
        media = sum(precios) / len(precios)
        desviacion = abs(ultimo - media) / media
        
        stats = market.get_24h_stats(symbol=par)
        volumen = float(stats['volValue'])
        
        if (desviacion < 0.02 and volumen > 500000 and ultimo > precios[-2]):
            logger.info(f"✅ Señal válida en {par} (Precio: {ultimo:.8f})")
            return {'par': par, 'precio': ultimo, 'valido': True}
            
    except Exception as e:
        logger.error(f"Error analizando {par}: {e}")
    
    return {'par': par, 'valido': False}

async def ejecutar_compra(par, precio, monto):
    try:
        symbol_info = market.get_symbol_list()
        current_symbol = next((s for s in symbol_info if s['symbol'] == par), None)
        
        if not current_symbol:
            raise ValueError(f"Par {par} no encontrado")
        
        base_increment = float(current_symbol['baseIncrement'])
        min_order_size = float(current_symbol['baseMinSize'])
        cantidad = Decimal(str(monto)) / Decimal(str(precio))
        cantidad_corr = (cantidad // Decimal(str(base_increment))) * Decimal(str(base_increment))
        
        if cantidad_corr < Decimal(str(min_order_size)):
            raise ValueError(f"Mínimo no alcanzado: {min_order_size} {par.split('-')[0]}")
        
        # CORRECCIÓN: Paréntesis correctamente cerrados
        orden = trade.create_market_order(
            symbol=par,
            side='buy',
            size=str(float(cantidad_corr))
        )  # ← Este paréntesis estaba faltando
        
        nueva_operacion = {
            'par': par,
            'entrada': float(precio),
            'cantidad': float(cantidad_corr),
            'maximo': float(precio),
            'ganancia': 0.0
        }
        operaciones.append(nueva_operacion)
        
        logger.info(f"🟢 COMPRA: {par} {float(cantidad_corr):.8f} @ {precio:.8f}")
        await bot.send_message(
            TELEGRAM_CHAT_ID,
            f"🟢 COMPRA: {par}\n"
            f"Precio: {precio:.8f}\n"
            f"Cantidad: {float(cantidad_corr):.8f}\n"
            f"Inversión: ${monto:.2f} USD"
        )
        
        asyncio.create_task(monitorear_operacion(nueva_operacion))
        
    except Exception as e:
        logger.error(f"❌ Error en compra: {e}")
        await bot.send_message(TELEGRAM_CHAT_ID, f"Error en compra {par}:\n{str(e)}")

async def monitorear_operacion(op):
    while op in operaciones and bot_activo:
        try:
            ticker = market.get_ticker(symbol=op['par'])
            precio_actual = float(ticker['price'])
            
            if precio_actual > op['maximo']:
                op['maximo'] = precio_actual
            
            ganancia_porcentaje = (precio_actual - op['entrada']) / op['entrada']
            
            if (ganancia_porcentaje >= CONFIG['ganancia_objetivo'] or 
                (precio_actual - op['maximo']) / op['maximo'] <= CONFIG['stop_loss']):
                await ejecutar_venta(op)
                break
                
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Error monitoreando {op['par']}: {e}")
            await asyncio.sleep(5)

async def ejecutar_venta(op):
    try:
        # CORRECCIÓN: Paréntesis cerrados correctamente
        orden = trade.create_market_order(
            symbol=op['par'],
            side='sell',
            size=str(op['cantidad'])
        )  # ← Este paréntesis estaba faltando
        
        ganancia = (op['maximo'] - op['entrada']) * op['cantidad']
        resultado = "GANANCIA" if ganancia > 0 else "PÉRDIDA"
        porcentaje = ((op['maximo'] - op['entrada']) / op['entrada']) * 100
        
        historial.append({
            'fecha': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'par': op['par'],
            'resultado': resultado,
            'ganancia': ganancia,
            'porcentaje': porcentaje
        })
        
        operaciones.remove(op)
        ultimos_pares[op['par']] = datetime.now()
        
        logger.info(f"🔴 VENTA: {op['par']} ({resultado}: {ganancia:.4f} USD)")
        await bot.send_message(
            TELEGRAM_CHAT_ID,
            f"🔴 VENTA: {op['par']}\n"
            f"Precio: {op['maximo']:.8f}\n"
            f"Ganancia: {ganancia:.4f} USD ({resultado})\n"
            f"Rentabilidad: {porcentaje:.2f}%"
        )
        
    except Exception as e:
        logger.error(f"Error en venta: {e}")
        await bot.send_message(TELEGRAM_CHAT_ID, f"Error en venta {op['par']}:\n{str(e)}")

# ------------------------- LÓGICA PRINCIPAL -------------------------
async def ejecutar_ciclo_trading():
    logger.info("🚀 Iniciando ciclo de trading")
    while bot_activo:
        try:
            async with lock:
                if len(operaciones) >= CONFIG['max_operaciones']:
                    await asyncio.sleep(10)
                    continue
                
                saldo = await obtener_saldo_disponible()
                monto_por_operacion = (saldo * CONFIG['uso_saldo']) / CONFIG['max_operaciones']
                
                if monto_por_operacion < CONFIG['orden_minima']:
                    await asyncio.sleep(30)
                    continue
                
                for par in PARES_ACTIVOS:
                    if not bot_activo:
                        break
                    
                    if any(op['par'] == par for op in operaciones):
                        continue
                        
                    if par in ultimos_pares and (datetime.now() - ultimos_pares[par]).seconds < CONFIG['espera_reentrada']:
                        continue
                    
                    señal = await analizar_par(par)
                    if señal['valido'] and monto_por_operacion >= CONFIG['min_order_usd'].get(par, 15):
                        await ejecutar_compra(par, señal['precio'], monto_por_operacion)
                        await asyncio.sleep(5)
                        break
            
            await asyncio.sleep(3)
            
        except Exception as e:
            logger.error(f"Error en ciclo principal: {e}")
            await asyncio.sleep(10)

# ------------------------- HANDLERS DE TELEGRAM -------------------------
@dp.message(Command("start"))
async def comando_inicio(message: types.Message):
    await message.answer("🤖 Bot de Trading Activo", reply_markup=crear_teclado())

@dp.message()
async def manejar_comandos(message: types.Message):
    global bot_activo
    
    if message.text == "🚀 Encender Bot" and not bot_activo:
        bot_activo = True
        asyncio.create_task(ejecutar_ciclo_trading())
        await message.answer("✅ Bot activado - Escaneando mercados...")
    elif message.text == "⛔ Apagar Bot":
        bot_activo = False
        await message.answer("🔴 Bot detenido")
    elif message.text == "💰 Saldo":
        saldo = await obtener_saldo_disponible()
        await message.answer(f"💵 Saldo disponible: {saldo:.2f} USDT")
    elif message.text == "📊 Estado":
        estado = "🟢 ACTIVO" if bot_activo else "🔴 INACTIVO"
        await message.answer(f"Estado: {estado}\nOperaciones activas: {len(operaciones)}/{CONFIG['max_operaciones']}")
    elif message.text == "📈 Operaciones":
        await mostrar_operaciones_activas(message)
    elif message.text == "🧾 Historial":
        await mostrar_historial(message)

async def mostrar_operaciones_activas(message: types.Message):
    if not operaciones:
        await message.answer("No hay operaciones activas")
        return
    
    mensaje = "📊 Operaciones Activas:\n\n"
    for op in operaciones:
        ticker = market.get_ticker(op['par'])
        precio_actual = float(ticker['price'])
        ganancia = (precio_actual - op['entrada']) * op['cantidad']
        porcentaje = (precio_actual - op['entrada']) / op['entrada'] * 100
        
        mensaje += (
            f"🔹 {op['par']}\n"
            f"Entrada: {op['entrada']:.8f}\n"
            f"Actual: {precio_actual:.8f}\n"
            f"Cantidad: {op['cantidad']:.2f}\n"
            f"Ganancia: {ganancia:.4f} USD ({porcentaje:.2f}%)\n\n"
        )
    await message.answer(mensaje)

async def mostrar_historial(message: types.Message):
    if not historial:
        await message.answer("Historial vacío")
        return
    
    mensaje = "📜 Últimas 10 operaciones:\n\n"
    for op in historial[-10:]:
        mensaje += (
            f"⏰ {op['fecha']}\n"
            f"🔹 {op['par']}\n"
            f"📊 {op['resultado']}: {op['ganancia']:.4f} USD\n"
            f"📈 {op['porcentaje']:.2f}%\n"
            f"────────────────────\n"
        )
    await message.answer(mensaje)

# ------------------------- INICIO DEL BOT -------------------------
async def iniciar_bot():
    from keep_alive import mantener_activo
    mantener_activo()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        logger.info("🚀 Iniciando ZafroBot Scalper V1")
        asyncio.run(iniciar_bot())
    except KeyboardInterrupt:
        logger.info("👋 Bot detenido manualmente")
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")