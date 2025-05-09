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
    'orden_minima': 5,  # Mínimo 5 USDT
    'min_order_sizes': {
        "PEPE-USDT": 1000,
        "SHIB-USDT": 50000,
        "DOGE-USDT": 10,
        "TRUMP-USDT": 1,
        "BONK-USDT": 10000,
        "WIF-USDT": 0.1
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
            logging.info(f"Señal válida en {par} | Precio: {ultimo:.8f}")
            return {'par': par, 'precio': ultimo, 'valido': True}
            
    except Exception as e:
        logging.error(f"Error analizando {par}: {e}")
    
    return {'par': par, 'valido': False}

async def ejecutar_compra(par, precio, monto):
    try:
        # Obtener información del símbolo
        symbol_info = market.get_symbol_list()
        current_symbol = next((s for s in symbol_info if s['symbol'] == par), None)
        
        if not current_symbol:
            raise ValueError(f"No se encontró información para el par {par}")
        
        # Obtener parámetros de la orden
        base_increment = float(current_symbol['baseIncrement'])
        min_order_size = float(current_symbol['baseMinSize'])
        min_order_usd = CONFIG['min_order_sizes'].get(par, 0) * precio
        
        # Calcular cantidad
        cantidad = Decimal(str(monto)) / Decimal(str(precio))
        step = Decimal(str(base_increment))
        cantidad_corr = (cantidad // step) * step
        
        # Verificar mínimos
        if cantidad_corr < Decimal(str(min_order_size)):
            raise ValueError(f"Cantidad muy pequeña. Mínimo {min_order_size} {par.split('-')[0]}")
            
        if monto < min_order_usd:
            raise ValueError(f"Monto muy pequeño. Mínimo ${min_order_usd:.2f} USD")
        
        # Ejecutar orden
        orden = trade.create_market_order(
            symbol=par,
            side='buy',
            size=str(float(cantidad_corr))  # Convertir a float para evitar notación científica
        )
        
        nueva_operacion = {
            'par': par,
            'entrada': float(precio),
            'cantidad': float(cantidad_corr),
            'maximo': float(precio),
            'ganancia': 0.0
        }
        
        operaciones.append(nueva_operacion)
        logging.info(f"Compra ejecutada: {par} {float(cantidad_corr):.8f} @ {precio:.8f}")
        await bot.send_message(
            TELEGRAM_CHAT_ID,
            f"🟢 COMPRA: {par}\n"
            f"Precio: {precio:.8f}\n"
            f"Cantidad: {float(cantidad_corr):.8f}\n"
            f"Inversión: ${monto:.2f} USD"
        )
        
        asyncio.create_task(monitorear_operacion(nueva_operacion))
        
    except Exception as e:
        logging.error(f"Error en compra {par}: {str(e)}")
        await bot.send_message(
            TELEGRAM_CHAT_ID,
            f"❌ Error en compra {par}:\n{str(e)}"
        )

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
        resultado = "GANANCIA" if ganancia > 0 else "PÉRDIDA"
        
        historial.append({
            'fecha': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'par': op['par'],
            'resultado': resultado,
            'ganancia': ganancia,
            'porcentaje': ((op['maximo'] - op['entrada']) / op['entrada']) * 100
        })
        
        operaciones.remove(op)
        ultimos_pares[op['par']] = datetime.now()
        
        logging.info(f"Venta ejecutada: {op['par']} Ganancia: {ganancia:.4f}")
        await bot.send_message(
            TELEGRAM_CHAT_ID,
            f"🔴 VENTA: {op['par']}\n"
            f"Precio: {op['maximo']:.8f}\n"
            f"Ganancia: {ganancia:.4f} USD ({resultado})\n"
            f"Rentabilidad: {((op['maximo'] - op['entrada']) / op['entrada'] * 100):.2f}%"
        )
        
    except Exception as e:
        logging.error(f"Error en venta {op['par']}: {e}")
        await bot.send_message(
            TELEGRAM_CHAT_ID,
            f"❌ Error en venta {op['par']}:\n{str(e)}"
        )

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
        current_price = float(market.get_ticker(op['par'])['price'])
        profit = (current_price - op['entrada']) * op['cantidad']
        profit_percent = (current_price - op['entrada']) / op['entrada'] * 100
        
        mensaje += (
            f"🔹 {op['par']}\n"
            f"Entrada: {op['entrada']:.8f}\n"
            f"Actual: {current_price:.8f}\n"
            f"Cantidad: {op['cantidad']:.2f}\n"
            f"Ganancia: {profit:.4f} USD ({profit_percent:.2f}%)\n\n"
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

# ------------------------- INICIO DE LA APLICACIÓN -------------------------
async def iniciar_bot():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(iniciar_bot())