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

# 2. Validación robusta de configuración
REQUIRED_ENV_VARS = [
    "TELEGRAM_TOKEN", "CHAT_ID",
    "API_KEY", "SECRET_KEY", "API_PASSPHRASE"
]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    error_msg = f"Error: Faltan variables de entorno: {', '.join(missing_vars)}"
    logger.critical(error_msg)
    raise EnvironmentError(error_msg)

# 3. Inicialización con manejo de errores
try:
    bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
    dp = Dispatcher()
    logger.info("Bot de Telegram inicializado correctamente")
except Exception as e:
    logger.critical(f"Error al inicializar el bot: {e}")
    raise

# 4. Configuración optimizada de trading
TRADING_CONFIG = {
    "SHIB-USDT": {
        "increment": 1000, "min_qty": 50000, "min_vol": 800000,
        "min_momentum": 0.008, "cooldown": 20, "daily_limit": 5,
        "tp": 0.02, "sl": 0.01
    },
    "PEPE-USDT": {
        "increment": 100, "min_qty": 5000, "min_vol": 600000,
        "min_momentum": 0.01, "cooldown": 25, "daily_limit": 6,
        "tp": 0.025, "sl": 0.012
    },
    # ... (otros pares)
}

GLOBAL_CONFIG = {
    "balance_usage": 0.9,
    "max_trades": 1,
    "analysis_interval": 15,
    "min_balance": 36.0,
    "min_profit": 0.02,
    "protection_level": -0.01,
    "max_duration": 30
}

# 5. Estado del bot con seguridad thread-safe
class TradingState:
    def __init__(self):
        self.active_trades = []
        self.trade_history = []
        self.recent_trades = {}
        self.cooldowns = set()
        self.is_active = False
        self.lock = asyncio.Lock()
        self.last_analysis = datetime.now()

state = TradingState()

# 6. Funciones auxiliares mejoradas
async def create_main_menu():
    """Crea el menú interactivo principal"""
    buttons = [
        [InlineKeyboardButton(text="🚀 Iniciar Trading", callback_data="start_trading"),
         InlineKeyboardButton(text="🛑 Detener Trading", callback_data="stop_trading")],
        [InlineKeyboardButton(text="💰 Balance", callback_data="show_balance"),
         InlineKeyboardButton(text="📊 Operaciones", callback_data="show_trades")],
        [InlineKeyboardButton(text="⚙ Configuración", callback_data="show_config")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_available_balance():
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
        logger.error(f"Error al obtener balance: {e}")
        return 0.0

# 7. Núcleo de trading optimizado
async def analyze_market():
    """Analiza el mercado en busca de oportunidades"""
    opportunities = []
    
    try:
        balance = await get_available_balance()
        if balance < GLOBAL_CONFIG["min_balance"]:
            logger.warning(f"Saldo insuficiente: {balance} USDT")
            return opportunities

        for pair, config in TRADING_CONFIG.items():
            if pair in state.cooldowns:
                continue
                
            signal = await detect_opportunity(pair, config)
            if signal:
                opportunities.append(signal)
                
    except Exception as e:
        logger.error(f"Error en análisis de mercado: {e}")
    
    return opportunities

async def trading_cycle():
    """Ciclo principal de trading"""
    logger.info("Iniciando ciclo de trading...")
    
    while state.is_active:
        try:
            async with state.lock:
                # 1. Análisis de mercado
                opportunities = await analyze_market()
                
                # 2. Ejecución de operaciones
                for opportunity in opportunities[:GLOBAL_CONFIG["max_trades"]]:
                    if len(state.active_trades) >= GLOBAL_CONFIG["max_trades"]:
                        break
                        
                    await execute_trade(opportunity)
                    await asyncio.sleep(5)
                
                # 3. Gestión de operaciones
                await manage_active_trades()
                
            await asyncio.sleep(GLOBAL_CONFIG["analysis_interval"])
            
        except Exception as e:
            logger.error(f"Error en ciclo de trading: {e}")
            await asyncio.sleep(30)

# 8. Handlers de Telegram mejorados
@dp.message(Command("start", "menu"))
async def start_command(message: types.Message):
    """Maneja el comando de inicio"""
    await message.answer(
        "🤖 KuCoin Pro Bot - Listo\n"
        "Selecciona una opción:",
        reply_markup=await create_main_menu()
    )

@dp.callback_query(lambda c: c.data == "start_trading")
async def start_trading(callback: types.CallbackQuery):
    """Inicia el trading automático"""
    if not state.is_active:
        state.is_active = True
        asyncio.create_task(trading_cycle())
        
        await callback.message.edit_text(
            "🚀 Trading automático ACTIVADO\n"
            "⚡ Analizando oportunidades de mercado...",
            reply_markup=await create_main_menu()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "show_balance")
async def show_balance(callback: types.CallbackQuery):
    """Muestra el balance actual"""
    balance = await get_available_balance()
    message = (
        f"💰 Balance Actual:\n"
        f"• Saldo disponible: {balance:.2f} USDT\n"
        f"• Mínimo requerido: {GLOBAL_CONFIG['min_balance']:.2f} USDT"
    )
    
    await callback.message.edit_text(
        message,
        reply_markup=await create_main_menu()
    )
    await callback.answer()

# 9. Función principal robusta
async def run_bot():
    """Función principal con manejo de errores"""
    logger.info("=== INICIANDO KUCOIN PRO BOT ===")
    
    try:
        # Verificar conexiones
        await check_connections()
        
        # Iniciar el bot
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.critical(f"Error fatal: {e}")
    finally:
        await bot.session.close()
        logger.info("Bot detenido correctamente")

async def check_connections():
    """Verifica todas las conexiones externas"""
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

# 10. Punto de entrada
if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.critical(f"Error no manejado: {e}")