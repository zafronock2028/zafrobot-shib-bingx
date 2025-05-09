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

# Configuración de logging
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
        await message.answer("✅ Bot activado - Ciclo de trading iniciado")
    elif message.text == "⛔ Apagar Bot":
        bot_activo = False
        await message.answer("🔴 Bot detenido")
    elif message.text == "💰 Saldo":
        saldo = await obtener_saldo_disponible()
        await message.answer(f"💵 Saldo disponible: {saldo:.2f} USDT")
    elif message.text == "📊 Estado":
        estado = "🟢 ACTIVO" if bot_activo else "🔴 INACTIVO"
        await message.answer(f"Estado del bot: {estado}")
    elif message.text == "📈 Operaciones":
        await mostrar_operaciones_activas(message)
    elif message.text == "🧾 Historial":
        await mostrar_historial(message)

# ------------------------- LÓGICA DE TRADING MEJORADA -------------------------
async def ejecutar_ciclo_trading():
    logger.info("🚀 Iniciando ciclo de trading principal")
    while bot_activo:
        try:
            # Verificar si podemos realizar más operaciones
            async with lock:
                if len(operaciones) >= CONFIG['max_operaciones']:
                    logger.info(f"Máximo de operaciones alcanzado ({CONFIG['max_operaciones']})")
                    await asyncio.sleep(10)
                    continue

                # Obtener saldo disponible
                saldo = await obtener_saldo_disponible()
                if saldo < CONFIG['orden_minima']:
                    logger.warning(f"Saldo insuficiente: {saldo:.2f} USDT")
                    await asyncio.sleep(30)
                    continue

                monto_por_operacion = (saldo * CONFIG['uso_saldo']) / CONFIG['max_operaciones']
                logger.info(f"Saldo disponible: {saldo:.2f} USDT | Monto por operación: {monto_por_operacion:.2f} USDT")

                # Analizar cada par
                for par in PARES_ACTIVOS:
                    if not bot_activo:
                        break

                    # Verificar si ya estamos en este par
                    if any(op['par'] == par for op in operaciones):
                        continue
                        
                    # Verificar tiempo de espera para reentrada
                    if par in ultimos_pares:
                        tiempo_espera = (datetime.now() - ultimos_pares[par]).total_seconds()
                        if tiempo_espera < CONFIG['espera_reentrada']:
                            continue

                    # Analizar el par
                    señal = await analizar_par(par)
                    if señal['valido']:
                        min_order = CONFIG['min_order_usd'].get(par, CONFIG['orden_minima'])
                        if monto_por_operacion >= min_order:
                            logger.info(f"🔔 Señal válida encontrada para {par}")
                            await ejecutar_compra(par, señal['precio'], monto_por_operacion)
                            await asyncio.sleep(5)  # Espera entre operaciones
                            break
                        else:
                            logger.info(f"Saldo insuficiente para {par}. Se necesitan ${min_order:.2f}")
                    else:
                        logger.debug(f"No hay señal válida para {par}")

            await asyncio.sleep(5)  # Intervalo entre ciclos de análisis
            
        except Exception as e:
            logger.error(f"Error en ciclo principal de trading: {str(e)}", exc_info=True)
            await asyncio.sleep(10)

async def analizar_par(par):
    try:
        # Obtener datos del mercado
        velas = market.get_kline(symbol=par, kline_type="1min", limit=10)  # Aumentamos a 10 velas para mejor análisis
        if not velas:
            return {'par': par, 'valido': False}

        precios = [float(v[2]) for v in velas]  # Precios de cierre
        ultimo = precios[-1]
        media = sum(precios) / len(precios)
        desviacion = abs(ultimo - media) / media
        
        # Obtener estadísticas de 24h
        stats = market.get_24h_stats(symbol=par)
        volumen = float(stats['volValue'])
        cambio = (precios[-1] - precios[-3]) / precios[-3]  # Cambio porcentual en 3 velas
        
        # Condiciones para entrada
        condicion_volumen = volumen > 1000000  # 1 millón USDT de volumen
        condicion_tendencia = cambio > 0.002  # 0.2% de aumento
        condicion_volatilidad = desviacion < 0.015  # 1.5% de desviación
        
        if condicion_volumen and condicion_tendencia and condicion_volatilidad:
            logger.info(f"✅ Señal COMPRA para {par} | Precio: {ultimo:.8f} | Volumen: {volumen:,.2f}")
            return {'par': par, 'precio': ultimo, 'valido': True}
            
    except Exception as e:
        logger.error(f"Error analizando {par}: {str(e)}", exc_info=True)
    
    return {'par': par, 'valido': False}

# ... (las funciones ejecutar_compra, monitorear_operacion, ejecutar_venta, 
# mostrar_operaciones_activas y mostrar_historial se mantienen igual que en la versión anterior) ...

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
        logger.error(f"❌ Error fatal al iniciar el bot: {str(e)}", exc_info=True)