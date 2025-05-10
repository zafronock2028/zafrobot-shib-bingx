import os
import logging
import asyncio
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from kucoin.client import Trade, Market, User
from dotenv import load_dotenv

# 1. Configuración inicial mejorada
load_dotenv()

# Validación robusta de variables de entorno
REQUIRED_ENV_VARS = ["TELEGRAM_TOKEN", "CHAT_ID", "API_KEY", "SECRET_KEY", "API_PASSPHRASE"]
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Faltan variables de entorno requeridas: {', '.join(missing_vars)}")

# Configuración avanzada de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trading_bot.log')
    ]
)
logger = logging.getLogger("KuCoinProTrader")

# 2. Inicialización con manejo de errores
try:
    bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
    dp = Dispatcher()
    logger.info("Bot de Telegram inicializado correctamente")
except Exception as e:
    logger.critical(f"Error al inicializar el bot: {e}")
    raise

# 3. Configuración optimizada de trading
PARES_CONFIG = {
    "SHIB-USDT": {
        "inc": 1000, "min": 50000, "vol_min": 800000,
        "momentum_min": 0.008, "cooldown": 20, "max_ops_dia": 5,
        "tp": 0.02, "sl": 0.01
    },
    "PEPE-USDT": {
        "inc": 100, "min": 5000, "vol_min": 600000,
        "momentum_min": 0.010, "cooldown": 25, "max_ops_dia": 6,
        "tp": 0.025, "sl": 0.012
    },
    # ... (otros pares con misma estructura)
}

CONFIG = {
    "uso_saldo": 0.90,
    "max_operaciones": 1,
    "reanalisis_segundos": 15,
    "saldo_minimo": 36.00,
    "min_ganancia_objetivo": 0.02,
    "nivel_proteccion": -0.01,
    "max_duracion_minutos": 30
}

# 4. Estado del bot con seguridad thread-safe
class EstadoTrading:
    def __init__(self):
        self.operaciones_activas = []
        self.historial_operaciones = []
        self.operaciones_recientes = {}
        self.cooldown_activo = set()
        self.bot_activo = False
        self.lock = asyncio.Lock()

estado = EstadoTrading()

# 5. Funciones auxiliares mejoradas
async def crear_menu_principal():
    """Crea el menú interactivo principal"""
    buttons = [
        [InlineKeyboardButton(text="🚀 Iniciar Bot", callback_data="start_bot"),
         InlineKeyboardButton(text="🛑 Detener Bot", callback_data="stop_bot")],
        [InlineKeyboardButton(text="💰 Balance", callback_data="balance"),
         InlineKeyboardButton(text="📈 Operaciones", callback_data="operaciones")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def obtener_saldo_disponible():
    """Obtiene el saldo disponible con manejo robusto de errores"""
    try:
        user_client = User(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        accounts = await asyncio.to_thread(
            user_client.get_account_list,
            currency="USDT",
            account_type="trade"
        )
        return float(accounts[0]['available']) if accounts else 0.0
    except Exception as e:
        logger.error(f"Error obteniendo saldo: {e}")
        return 0.0

# 6. Núcleo de trading optimizado
async def ciclo_trading_principal():
    """Ciclo principal de trading mejorado"""
    logger.info("Iniciando ciclo principal de trading...")
    
    while estado.bot_activo:
        try:
            async with estado.lock:
                # Verificar saldo mínimo
                saldo = await obtener_saldo_disponible()
                if saldo < CONFIG["saldo_minimo"]:
                    logger.warning(f"Saldo insuficiente: {saldo} USDT")
                    await asyncio.sleep(60)
                    continue
                
                # Buscar oportunidades de trading
                for par in list(PARES_CONFIG.keys())[:3]:  # Solo top 3 pares
                    if await verificar_cooldown(par):
                        continue
                        
                    señal = await analizar_impulso(par)
                    if señal and len(estado.operaciones_activas) < CONFIG["max_operaciones"]:
                        operacion = await ejecutar_compra_segura(señal)
                        if operacion:
                            await asyncio.sleep(5)  # Espera entre operaciones
                
                # Gestionar operaciones activas
                for op in estado.operaciones_activas[:]:
                    await gestionar_operacion(op)
                    
            await asyncio.sleep(CONFIG["reanalisis_segundos"])
            
        except Exception as e:
            logger.error(f"Error en ciclo de trading: {e}")
            await asyncio.sleep(30)

# 7. Handlers de Telegram mejorados
@dp.message(Command("start"))
async def comando_inicio(message: types.Message):
    """Maneja el comando de inicio con menú interactivo"""
    await message.answer(
        "🤖 KuCoin Trading Bot - Listo\n"
        "Selecciona una opción:",
        reply_markup=await crear_menu_principal()
    )

@dp.callback_query(lambda c: c.data == "start_bot")
async def iniciar_bot(callback: types.CallbackQuery):
    """Inicia el bot de trading"""
    if not estado.bot_activo:
        estado.bot_activo = True
        asyncio.create_task(ciclo_trading_principal())
        
        await callback.message.edit_text(
            "🚀 Bot de trading ACTIVADO\n"
            "⚡ Analizando oportunidades de mercado...",
            reply_markup=await crear_menu_principal()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "balance")
async def mostrar_balance(callback: types.CallbackQuery):
    """Muestra el balance actual"""
    saldo = await obtener_saldo_disponible()
    pares_viables = [p for p in PARES_CONFIG if PARES_CONFIG[p]["min"] * 0.001 <= saldo * 0.9]  # Aproximación
    
    await callback.message.edit_text(
        f"💰 Balance Actual:\n"
        f"• Saldo disponible: {saldo:.2f} USDT\n"
        f"• Mínimo requerido: {CONFIG['saldo_minimo']:.2f} USDT\n"
        f"• Pares viables: {', '.join(pares_viables[:5])}...",
        reply_markup=await crear_menu_principal()
    )
    await callback.answer()

# 8. Función principal robusta
async def ejecutar_bot():
    """Función principal con manejo de errores"""
    logger.info("=== INICIANDO KUCOIN TRADING BOT ===")
    
    try:
        # Verificar conexiones
        await verificar_conexiones()
        
        # Iniciar el bot
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.critical(f"Error fatal: {e}")
    finally:
        await bot.session.close()
        logger.info("Bot detenido correctamente")

async def verificar_conexiones():
    """Verifica todas las conexiones necesarias"""
    logger.info("Verificando conexiones...")
    
    # Verificar KuCoin
    try:
        market = Market()
        await asyncio.to_thread(market.get_ticker, "BTC-USDT")
        logger.info("Conexión a KuCoin: OK")
    except Exception as e:
        logger.error(f"Error conectando a KuCoin: {e}")
        raise
    
    # Verificar Telegram
    try:
        await bot.get_me()
        logger.info("Conexión a Telegram: OK")
    except Exception as e:
        logger.error(f"Error conectando a Telegram: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(ejecutar_bot())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.critical(f"Error no manejado: {e}")