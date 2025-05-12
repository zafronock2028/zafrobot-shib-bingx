import os
import logging
import asyncio
import json
import traceback
import decimal
from datetime import datetime, timedelta
from typing import Dict, List
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from kucoin.client import Trade, Market, User
from dotenv import load_dotenv

load_dotenv()

# =================================================================
# VALIDACIÓN DE ENTORNO
# =================================================================
REQUIRED_ENV_VARS = ["TELEGRAM_TOKEN", "CHAT_ID", "API_KEY", "SECRET_KEY", "API_PASSPHRASE"]
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Variables faltantes: {', '.join(missing_vars)}")

# =================================================================
# CONFIGURACIÓN DE LOGGING
# =================================================================
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trading_bot.log')
    ]
)
logger = logging.getLogger("KuCoinProTrader")

# =================================================================
# CONFIGURACIÓN PRINCIPAL (Optimizada para bajos saldos)
# =================================================================
CONFIG = {
    "uso_saldo": 0.50,
    "max_operaciones": 2,
    "intervalo_analisis": 5,
    "saldo_minimo": 5.00,
    "proteccion_ganancia": 0.015,
    "lock_ganancia": 0.004,
    "max_duracion": 20,
    "hora_reseteo": "00:00",
    "seleccion": {
        "volumen_minimo": 150000,
        "precio_minimo": 0.01,
        "spread_maximo": 0.005,
        "max_pares": 8,
        "config_base": {
            "min": 2.00,
            "momentum_min": 0.0030,
            "cooldown": 8,
            "max_ops_dia": 8,
            "tp": 0.020,
            "sl": 0.012,
            "trailing_stop": True,
            "trailing_offset": 0.0035,
            "slippage": 0.0030
        }
    }
}

PARES_CONFIG = {}

# =================================================================
# SISTEMA DE ESTADO
# =================================================================
class EstadoTrading:
    def __init__(self):
        self.operaciones_activas = []
        self.historial = []
        self.cooldowns = set()
        self.activo = False
        self.lock = asyncio.Lock()
        self.ultima_conexion = None
        self.pares_en_analisis = set()
        self.contador_operaciones = {}
        self.ultimo_reseteo = self.obtener_hora_reseteo()
        
    def obtener_hora_reseteo(self):
        hoy = datetime.utcnow().date()
        hora, minuto = map(int, CONFIG["hora_reseteo"].split(':'))
        return datetime.combine(hoy, datetime.min.time()).replace(hour=hora, minute=minuto)

estado = EstadoTrading()

# =================================================================
# MÓDULO DE SELECCIÓN DE PARES
# =================================================================
async def obtener_pares_candidatos() -> List[Dict]:
    try:
        market = Market()
        todos_tickers = await asyncio.to_thread(market.get_all_tickers)
        pares_usdt = [ticker for ticker in todos_tickers['ticker'] if ticker['symbol'].endswith('USDT')]
        
        pares_filtrados = []
        for par in pares_usdt:
            symbol = par['symbol']
            try:
                stats = await asyncio.to_thread(market.get_24h_stats, symbol)
                vol_value = float(stats['volValue'])
                
                if vol_value < CONFIG["seleccion"]["volumen_minimo"]:
                    continue
                    
                ticker = await asyncio.to_thread(market.get_ticker, symbol)
                spread = (float(ticker['bestAsk']) - float(ticker['bestBid'])) / float(ticker['bestAsk'])
                
                if spread > CONFIG["seleccion"]["spread_maximo"]:
                    continue
                    
                pares_filtrados.append({
                    'symbol': symbol,
                    'volumen': vol_value,
                    'precio': float(ticker['price']),
                    'spread': spread
                })
                
                await asyncio.sleep(0.2)
                
            except Exception as e:
                logger.debug(f"Error analizando {symbol}: {str(e)}")
                continue
                
        return sorted(pares_filtrados, key=lambda x: x['volumen'], reverse=True)[:CONFIG["seleccion"]["max_pares"]]
    
    except Exception as e:
        logger.error(f"Error obteniendo pares: {str(e)}")
        return []

async def generar_nueva_configuracion(pares: List[Dict]) -> Dict:
    try:
        market = Market()
        todos_symbols = await asyncio.to_thread(market.get_symbol_list)
        
        nueva_config = {}
        for par in pares:
            symbol = par['symbol']
            symbol_info = next((s for s in todos_symbols if s['symbol'] == symbol), None)
            
            if not symbol_info:
                logger.error(f"Symbol {symbol} no encontrado")
                continue
                
            config = CONFIG["seleccion"]["config_base"].copy()
            config.update({
                'vol_min': par['volumen'] * 0.75,
                'minSize': float(symbol_info['baseMinSize'])
            })
            
            nueva_config[symbol] = config
        return nueva_config
    except Exception as e:
        logger.error(f"Error generando configuración: {str(e)}")
        return {}

# =================================================================
# CORE DEL TRADING (Versión Mejorada)
# =================================================================
async def verificar_conexion_kucoin():
    try:
        market = Market()
        await asyncio.to_thread(market.get_ticker, "BTC-USDT")
        estado.ultima_conexion = datetime.now()
        return True
    except Exception as e:
        logger.error(f"Error de conexión: {e}")
        return False

async def obtener_saldo_disponible():
    try:
        user_client = User(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE"),
            is_sandbox=False
        )
        cuentas = await asyncio.to_thread(user_client.get_account_list)
        return sum(float(acc['available']) for acc in cuentas if acc['currency'] == 'USDT' and acc['type'] in ['trade', 'main'])
    except Exception as e:
        logger.error(f"Error obteniendo saldo: {e}")
        return 0.0

async def calcular_posicion(par, saldo_disponible, precio_entrada):
    try:
        market = Market()
        symbol_info = await asyncio.to_thread(market.get_symbol_detail, par)
        
        incremento = float(symbol_info["baseIncrement"])
        min_size = float(symbol_info["baseMinSize"])
        min_notional = float(symbol_info["minFunds"])
        
        # Cálculo con protección de slippage
        saldo_asignado = saldo_disponible * CONFIG["uso_saldo"]
        cantidad = (saldo_asignado / precio_entrada) * (1 - CONFIG["seleccion"]["config_base"]["slippage"])
        
        # Redondeo preciso
        cantidad_redondeada = round(cantidad / incremento) * incremento
        cantidad_redondeada = max(cantidad_redondeada, min_size)
        valor_operacion = cantidad_redondeada * precio_entrada

        logger.debug(f"[CÁLCULO] {par}:")
        logger.debug(f"• Saldo asignado: {saldo_asignado:.6f}")
        logger.debug(f"• Cantidad cruda: {cantidad:.8f}")
        logger.debug(f"• Redondeado: {cantidad_redondeada:.8f}")
        logger.debug(f"• Valor operación: {valor_operacion:.6f}")
        logger.debug(f"• Mínimo requerido: {min_notional:.6f}")

        if valor_operacion < min_notional:
            raise ValueError(f"Valor insuficiente: {valor_operacion:.6f} < {min_notional:.6f}")

        # Formateo final seguro
        decimales = abs(decimal.Decimal(str(incremento)).as_tuple().exponent)
        size_str = "{:.{}f}".format(cantidad_redondeada, abs(decimales)).rstrip('0').rstrip('.')
        
        return size_str

    except Exception as e:
        logger.error(f"❌ Error cálculo en {par}: {str(e)}", exc_info=True)
        await notificar_error(f"Error cálculo {par}:\n{str(e)}")
        return None

async def detectar_oportunidad(par):
    try:
        if not await verificar_conexion_kucoin():
            return None

        market = Market(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE"),
            is_sandbox=False
        )

        stats = await asyncio.to_thread(market.get_24h_stats, par)
        vol_actual = float(stats["volValue"])
        if vol_actual < PARES_CONFIG[par]["vol_min"]:
            logger.info(f"DESCARTADO {par} - Volumen insuficiente")
            return None

        velas = await asyncio.to_thread(market.get_kline, par, "1min")
        if len(velas) < 3:
            logger.info(f"DESCARTADO {par} - Datos insuficientes")
            return None

        cierres = [float(v[2]) for v in velas[-3:]]
        if cierres[2] < cierres[1] or cierres[1] < cierres[0]:
            logger.info(f"DESCARTADO {par} - Tendencia negativa")
            return None

        momentum = (cierres[2] - cierres[0]) / cierres[0]
        if momentum < PARES_CONFIG[par]["momentum_min"]:
            logger.info(f"DESCARTADO {par} - Momentum bajo")
            return None

        ticker = await asyncio.to_thread(market.get_ticker, par)
        best_ask = float(ticker["bestAsk"])
        best_bid = float(ticker["bestBid"])
        spread = (best_ask - best_bid) / best_ask
        
        if spread > CONFIG["seleccion"]["spread_maximo"]:
            logger.info(f"DESCARTADO {par} - Spread alto")
            return None

        return {
            "par": par,
            "precio": cierres[2],
            "momentum": momentum,
            "take_profit": cierres[2] * (1 + PARES_CONFIG[par]["tp"]),
            "stop_loss": cierres[2] * (1 - PARES_CONFIG[par]["sl"])
        }
    except Exception as e:
        logger.error(f"Error analizando {par}: {e}")
        return None

async def ejecutar_operacion(señal):
    operacion = None
    try:
        logger.info(f"\n🔍 ANALIZANDO ORDEN: {señal['par']}")
        logger.info(f"📊 Precio señal: {señal['precio']:.8f}")

        saldo = await obtener_saldo_disponible()
        if saldo < CONFIG["saldo_minimo"]:
            logger.warning("❌ Saldo insuficiente")
            return None

        cantidad_str = await calcular_posicion(señal["par"], saldo, señal["precio"])
        if not cantidad_str:
            return None

        try:
            cantidad_float = float(cantidad_str)
        except ValueError:
            logger.error(f"🚨 Error en cantidad: {cantidad_str}")
            return None

        async with estado.lock:
            if len(estado.operaciones_activas) >= CONFIG["max_operaciones"]:
                logger.warning("⚠ Máximo operaciones")
                return None

            if estado.contador_operaciones.get(señal["par"], 0) >= PARES_CONFIG[señal["par"]]["max_ops_dia"]:
                logger.warning(f"⏳ Límite diario {señal['par']}")
                return None

        trade = Trade(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE"),
            is_sandbox=False
        )
        
        symbol_info = await asyncio.to_thread(trade.get_symbol_detail, señal["par"])
        min_notional = float(symbol_info["minFunds"])
        valor_operacion = cantidad_float * señal["precio"]

        if valor_operacion < min_notional:
            msg = f"⛔ {señal['par']}: {valor_operacion:.6f} < {min_notional:.6f}"
            logger.warning(msg)
            await notificar_error(msg)
            return None

        logger.info(f"⚡ INTENTANDO COMPRA: {cantidad_str} {señal['par']}")

        orden = await asyncio.wait_for(
            asyncio.to_thread(
                trade.create_market_order,
                symbol=señal["par"],
                side="buy",
                size=str(cantidad_str).replace(',', ''),
                client_oid=f"BOT_{datetime.now().timestamp()}"
            ),
            timeout=15
        )

        if 'orderId' not in orden:
            logger.error("❌ Orden fallida")
            logger.error(json.dumps(orden, indent=2))
            return None

        logger.info(f"✅ ORDEN EJECUTADA: {orden['orderId']}")

        operacion = {
            "par": señal["par"],
            "id_orden": orden["orderId"],
            "cantidad": cantidad_float,
            "precio_entrada": float(orden.get("price", señal["precio"])),
            "take_profit": señal["take_profit"],
            "stop_loss": señal["stop_loss"],
            "hora_entrada": datetime.now(),
            "fee_compra": float(orden.get("fee", 0))
        }

        async with estado.lock:
            estado.operaciones_activas.append(operacion)
            estado.contador_operaciones[señal["par"]] = estado.contador_operaciones.get(señal["par"], 0) + 1

        await notificar_operacion(operacion, "ENTRADA")
        return operacion

    except Exception as e:
        error_msg = f"🚨 Error en {señal['par']}:\n"
        if hasattr(e, 'response'):
            try:
                error_data = e.response.json()
                error_msg += f"Código: {error_data.get('code')}\nMensaje: {error_data.get('msg')}"
            except:
                error_msg += f"Respuesta cruda: {e.response.text}"
        else:
            error_msg += str(e)
        
        logger.error(error_msg)
        await notificar_error(error_msg)
        return None

async def cerrar_operacion(operacion, motivo):
    try:
        trade = Trade(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE"),
            is_sandbox=False
        )
        
        symbol_info = await asyncio.to_thread(trade.get_symbol_detail, operacion["par"])
        incremento = float(symbol_info["baseIncrement"])
        cantidad_redondeada = round(operacion["cantidad"] / incremento) * incremento
        
        decimales = abs(decimal.Decimal(str(incremento)).as_tuple().exponent)
        size_str = "{:.{}f}".format(cantidad_redondeada, abs(decimales)).rstrip('0').rstrip('.')
        
        orden_venta = await asyncio.wait_for(
            asyncio.to_thread(
                trade.create_market_order,
                symbol=operacion["par"],
                side="sell",
                size=size_str,
                client_oid=f"BOT_{datetime.now().timestamp()}"
            ),
            timeout=15
        )
        
        precio_salida = float(orden_venta.get("price", 0))
        fee_venta = float(orden_venta.get("fee", 0))
        ganancia_neto = (precio_salida * cantidad_redondeada) - (operacion["precio_entrada"] * cantidad_redondeada) - operacion["fee_compra"] - fee_venta
        
        operacion.update({
            "precio_salida": precio_salida,
            "hora_salida": datetime.now(),
            "motivo_salida": motivo,
            "fee_venta": fee_venta,
            "ganancia_neto": ganancia_neto
        })
        
        await notificar_operacion(operacion, "SALIDA")
        
        async with estado.lock:
            estado.historial.append(operacion)
            estado.operaciones_activas.remove(operacion)
            estado.cooldowns.add(operacion["par"])
            
        await guardar_historial()
    except Exception as e:
        logger.error(f"Error cerrando {operacion['par']}: {e}")
        await notificar_error(f"Error cierre {operacion['par']}:\n{str(e)}")

async def gestionar_operaciones_activas():
    async with estado.lock:
        for op in estado.operaciones_activas[:]:
            try:
                market = Market(
                    key=os.getenv("API_KEY"),
                    secret=os.getenv("SECRET_KEY"),
                    passphrase=os.getenv("API_PASSPHRASE"),
                    is_sandbox=False
                )
                ticker = await asyncio.to_thread(market.get_ticker, op["par"])
                precio_actual = float(ticker["price"])
                
                op["max_precio"] = max(op["max_precio"], precio_actual)
                max_ganancia = (op["max_precio"] - op["precio_entrada"]) / op["precio_entrada"]
                
                if PARES_CONFIG[op["par"]]["trailing_stop"] and max_ganancia > CONFIG["proteccion_ganancia"]:
                    nuevo_sl = op["precio_entrada"] * (1 + max_ganancia - PARES_CONFIG[op["par"]]["trailing_offset"])
                    op["stop_loss"] = max(op["stop_loss"], nuevo_sl)
                
                motivo = None
                if precio_actual >= op["take_profit"]: motivo = "TP"
                elif precio_actual <= op["stop_loss"]: motivo = "SL"
                elif (datetime.now() - op["hora_entrada"]).seconds > CONFIG["max_duracion"] * 60: motivo = "TIEMPO"
                
                if motivo: 
                    logger.info(f"Cerrando {op['par']} - {motivo}")
                    await cerrar_operacion(op, motivo)
            except Exception as e:
                logger.error(f"Error gestionando {op['par']}: {e}")

async def verificar_cooldown(par):
    ahora = datetime.utcnow()
    if ahora > estado.ultimo_reseteo + timedelta(days=1):
        estado.contador_operaciones = {}
        estado.ultimo_reseteo = estado.obtener_hora_reseteo()
    
    if estado.contador_operaciones.get(par, 0) >= PARES_CONFIG[par]["max_ops_dia"]:
        logger.info(f"Cooldown diario en {par}")
        return True
    
    if par in estado.cooldowns:
        ultima_op = next((op for op in estado.historial if op["par"] == par), None)
        if ultima_op and (ahora - ultima_op["hora_entrada"]).seconds < PARES_CONFIG[par]["cooldown"] * 60:
            logger.info(f"Cooldown activo en {par}")
            return True
    
    return False

async def guardar_historial():
    try:
        async with estado.lock:
            with open('historial_operaciones.json', 'w') as f:
                json.dump(estado.historial, f, indent=4, default=str)
    except Exception as e:
        logger.error(f"Error guardando historial: {e}")

# =================================================================
# INTERFAZ DE TELEGRAM
# =================================================================
async def notificar_operacion(operacion, tipo):
    try:
        if tipo == "ENTRADA":
            mensaje = (
                f"🚀 ENTRADA {operacion['par']}\n"
                f"📊 Cantidad: {operacion['cantidad']:.8f}\n"
                f"💰 Precio: {operacion['precio_entrada']:.8f}\n"
                f"🎯 TP: {operacion['take_profit']:.8f}\n"
                f"🛑 SL: {operacion['stop_loss']:.8f}"
            )
        else:
            ganancia_pct = ((operacion["precio_salida"] - operacion["precio_entrada"]) / operacion["precio_entrada"]) * 100
            mensaje = (
                f"{'🟢' if operacion['ganancia_neto'] >= 0 else '🔴'} SALIDA {operacion['par']}\n"
                f"📌 Motivo: {operacion['motivo_salida']}\n"
                f"💵 Entrada: {operacion['precio_entrada']:.8f}\n"
                f"💰 Salida: {operacion['precio_salida']:.8f}\n"
                f"📈 Ganancia: {ganancia_pct:.2f}%\n"
                f"⏱ Duración: {(operacion['hora_salida'] - operacion['hora_entrada']).seconds // 60} min"
            )
        
        await bot.send_message(os.getenv("CHAT_ID"), mensaje)
    except Exception as e:
        logger.error(f"Error notificación: {e}")

async def notificar_error(mensaje):
    try:
        await bot.send_message(os.getenv("CHAT_ID"), f"🚨 ERROR CRÍTICO 🚨\n{mensaje}")
    except Exception as e:
        logger.error(f"Error notificando error: {e}")

async def crear_menu_principal():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Iniciar Bot", callback_data="iniciar_bot"),
            InlineKeyboardButton(text="🛑 Detener Bot", callback_data="detener_bot")
        ],
        [
            InlineKeyboardButton(text="💰 Balance", callback_data="ver_balance"),
            InlineKeyboardButton(text="📊 Operaciones", callback_data="ver_operaciones")
        ],
        [
            InlineKeyboardButton(text="📜 Historial", callback_data="ver_historial")
        ]
    ])

async def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def comando_inicio(message: types.Message):
        try:
            if not await verificar_conexion_kucoin():
                await message.answer("⚠ Error de conexión")
                return
                
            await message.answer(
                "🤖 KuCoin Pro Bot - Listo",
                reply_markup=await crear_menu_principal()
            )
        except Exception as e:
            logger.error(f"Error inicio: {e}")

    @dp.message(Command("stop"))
    async def comando_stop(message: types.Message):
        estado.activo = False
        await message.answer("🛑 Bot detenido")

    @dp.callback_query(lambda c: c.data == "iniciar_bot")
    async def iniciar_bot(callback: types.CallbackQuery):
        try:
            if estado.activo:
                await callback.answer("⚠ Ya activo")
                return

            if not await verificar_conexion_kucoin():
                await callback.answer("⚠ Error conexión")
                return

            estado.activo = True
            asyncio.create_task(ciclo_trading())

            await callback.message.edit_text(
                "🚀 Bot ACTIVADO\n"
                f"🔹 Pares activos: {len(PARES_CONFIG)}\n"
                f"🔹 Saldo mínimo: {CONFIG['saldo_minimo']} USDT",
                reply_markup=await crear_menu_principal()
            )
        except Exception as e:
            logger.error(f"Error inicio: {e}")

    @dp.callback_query(lambda c: c.data == "detener_bot")
    async def detener_bot(callback: types.CallbackQuery):
        try:
            estado.activo = False
            mensaje = "🛑 Bot detenido"
            
            if callback.message.text != mensaje:
                await callback.message.edit_text(
                    mensaje,
                    reply_markup=await crear_menu_principal()
                )
            await callback.answer()
        except Exception as e:
            logger.error(f"Error deteniendo: {e}")

    @dp.callback_query(lambda c: c.data == "ver_historial")
    async def mostrar_historial(callback: types.CallbackQuery):
        try:
            if not estado.historial:
                await callback.answer("Historial vacío")
                return

            historial_reverso = estado.historial[-5:][::-1]
            mensaje = "📜 Últimas operaciones:\n\n"
            for op in historial_reverso:
                ganancia = ((op["precio_salida"] - op["precio_entrada"]) / op["precio_entrada"]) * 100
                duracion = (op["hora_salida"] - op["hora_entrada"]).seconds // 60
                mensaje += (
                    f"🔹 {op['par']} ({op['motivo_salida']})\n"
                    f"📈 {ganancia:.2f}% | ⏱ {duracion} min\n"
                    f"🕒 {op['hora_entrada'].strftime('%H:%M')} - {op['hora_salida'].strftime('%H:%M')}\n\n"
                )

            await callback.message.edit_text(mensaje, reply_markup=await crear_menu_principal())
            await callback.answer()
        except Exception as e:
            logger.error(f"Error historial: {e}")

    @dp.callback_query(lambda c: c.data == "ver_balance")
    async def mostrar_balance(callback: types.CallbackQuery):
        try:
            saldo = await obtener_saldo_disponible()
            mensaje = f"💰 Balance disponible: {saldo:.2f} USDT"
            await callback.message.edit_text(mensaje, reply_markup=await crear_menu_principal())
            await callback.answer()
        except Exception as e:
            logger.error(f"Error balance: {e}")
            await callback.answer("⚠ Error balance", show_alert=True)

    @dp.callback_query(lambda c: c.data == "ver_operaciones")
    async def mostrar_operaciones(callback: types.CallbackQuery):
        try:
            if not estado.operaciones_activas:
                await callback.answer("No hay operaciones activas")
                return
                
            mensaje = "📊 Operaciones activas:\n\n"
            market = Market()
            for op in estado.operaciones_activas:
                ticker = await asyncio.to_thread(market.get_ticker, op["par"])
                precio_actual = float(ticker["price"])
                ganancia_pct = ((precio_actual - op["precio_entrada"]) / op["precio_entrada"]) * 100
                mensaje += (
                    f"🔹 {op['par']}\n"
                    f"• Entrada: {op['precio_entrada']:.8f}\n"
                    f"• Actual: {precio_actual:.8f}\n"
                    f"• Ganancia: {ganancia_pct:.2f}%\n"
                    f"• Hora entrada: {op['hora_entrada'].strftime('%H:%M:%S')}\n\n"
                )
            
            await callback.message.edit_text(mensaje, reply_markup=await crear_menu_principal())
            await callback.answer()
        except Exception as e:
            logger.error(f"Error operaciones: {e}")

# =================================================================
# CICLO PRINCIPAL
# =================================================================
async def ciclo_trading():
    logger.info("Iniciando ciclo de trading...")
    
    while estado.activo:
        try:
            if not await verificar_conexion_kucoin():
                await asyncio.sleep(30)
                continue
                
            await gestionar_operaciones_activas()
            
            async with estado.lock:
                if len(estado.operaciones_activas) < CONFIG["max_operaciones"]:
                    logger.info("Buscando oportunidades...")
                    
                    for par in PARES_CONFIG:
                        if par in estado.pares_en_analisis:
                            continue
                            
                        estado.pares_en_analisis.add(par)
                        try:
                            if await verificar_cooldown(par):
                                continue
                                
                            señal = await detectar_oportunidad(par)
                            if señal:
                                operacion = await ejecutar_operacion(señal)
                                if operacion:
                                    await asyncio.sleep(2)
                        finally:
                            estado.pares_en_analisis.discard(par)
            
            await asyncio.sleep(CONFIG["intervalo_analisis"])
        except Exception as e:
            logger.error(f"Error ciclo: {e}")

# =================================================================
# EJECUCIÓN PRINCIPAL
# =================================================================
async def ejecutar_bot():
    logger.info("=== INICIANDO BOT ===")
    global bot
    bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
    dp = Dispatcher()

    try:
        await register_handlers(dp)

        pares_iniciales = await obtener_pares_candidatos()
        nueva_config = await generar_nueva_configuracion(pares_iniciales)

        if nueva_config:
            global PARES_CONFIG
            PARES_CONFIG.update(nueva_config)
            logger.info(f"Pares configurados: {list(PARES_CONFIG.keys())}")

        asyncio.create_task(actualizar_configuracion_diaria())

        if os.path.exists('historial_operaciones.json'):
            with open('historial_operaciones.json', 'r') as f:
                estado.historial = json.load(f)

        await dp.start_polling(bot)

    except Exception as e:
        logger.critical(f"Error fatal: {e}")
    finally:
        estado.activo = False
        await guardar_historial()
        await bot.close()
        logger.info("Bot detenido")

if __name__ == "__main__":
    try:
        asyncio.run(ejecutar_bot())
    except KeyboardInterrupt:
        logger.info("Detenido manualmente")
    except Exception as e:
        logger.critical(f"Error crítico: {e}")