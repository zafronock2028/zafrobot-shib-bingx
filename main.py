import os
import logging
import asyncio
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from kucoin.client import Trade, Market, User
from dotenv import load_dotenv

# Configuración inicial
load_dotenv()

# Inicialización crítica que faltaba
bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

# Logger profesional
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("KuCoinLowCapScalper")

# =================================================================
# CONFIGURACIÓN OPTIMIZADA PARA SALDOS PEQUEÑOS ($36+)
# =================================================================

# Fees de KuCoin
FEES = {
    "maker": 0.001,  # 0.1%
    "taker": 0.001   # 0.1%
}

# Mínimos operativos por par (en USDT)
MINIMO_USDT = {
    "SHIB-USDT": 10.00,
    "PEPE-USDT": 8.00,
    "FLOKI-USDT": 7.00,
    "DOGE-USDT": 15.00,
    "SUI-USDT": 12.00,
    "TURBO-USDT": 6.00,
    "BONK-USDT": 6.50,
    "WIF-USDT": 9.00
}

PARES_CONFIG = {
    "SHIB-USDT": {
        "inc": 1000,
        "min": 50000,
        "vol_min": 800000,
        "momentum_min": 0.008,
        "cooldown": 20,
        "max_ops_dia": 5
    },
    "PEPE-USDT": {
        "inc": 100,
        "min": 5000,
        "vol_min": 600000,
        "momentum_min": 0.010,
        "cooldown": 25,
        "max_ops_dia": 6
    },
    "FLOKI-USDT": {
        "inc": 100,
        "min": 5000,
        "vol_min": 700000,
        "momentum_min": 0.009,
        "cooldown": 30,
        "max_ops_dia": 5
    },
    "DOGE-USDT": {
        "inc": 1,
        "min": 5,
        "vol_min": 2000000,
        "momentum_min": 0.005,
        "cooldown": 15,
        "max_ops_dia": 3
    },
    "SUI-USDT": {
        "inc": 0.01,
        "min": 0.05,
        "vol_min": 1500000,
        "momentum_min": 0.004,
        "cooldown": 20,
        "max_ops_dia": 4
    },
    "TURBO-USDT": {
        "inc": 100,
        "min": 5000,
        "vol_min": 500000,
        "momentum_min": 0.012,
        "cooldown": 35,
        "max_ops_dia": 3
    },
    "BONK-USDT": {
        "inc": 1000,
        "min": 50000,
        "vol_min": 600000,
        "momentum_min": 0.011,
        "cooldown": 40,
        "max_ops_dia": 3
    },
    "WIF-USDT": {
        "inc": 0.0001,
        "min": 0.01,
        "vol_min": 900000,
        "momentum_min": 0.007,
        "cooldown": 25,
        "max_ops_dia": 4
    }
}

CONFIG = {
    "uso_saldo": 0.90,           # Usar 90% del saldo disponible
    "max_operaciones": 1,        # Solo 1 operación a la vez
    "puntaje_minimo": 3.0,
    "reanalisis_segundos": 15,
    "saldo_minimo": 36.00,       # Ajustado para $36
    "min_ganancia_objetivo": 0.02,  # TP mínimo 2%
    "nivel_proteccion": -0.01,
    "max_duracion_minutos": 30,  # 30 minutos máximo por operación
    "auto_optimizar": False,
    "noticias": False
}

# =================================================================
# VARIABLES GLOBALES
# =================================================================
operaciones_activas = []
historial_operaciones = []
operaciones_recientes = {}
cooldown_activo = set()
bot_activo = False
lock = asyncio.Lock()

# =================================================================
# FUNCIONES AUXILIARES
# =================================================================
async def guardar_historial():
    try:
        with open('historial_operaciones.json', 'w') as f:
            json.dump(historial_operaciones, f, indent=4, default=str)
    except Exception as e:
        logger.error(f"Error guardando historial: {e}")

async def verificar_cooldown(par):
    if par in cooldown_activo:
        config = PARES_CONFIG.get(par, {})
        cooldown = config.get("cooldown", 30)
        ultima_op = operaciones_recientes.get(par)
        
        if ultima_op and (datetime.now() - ultima_op).seconds < cooldown * 60:
            return True
        else:
            cooldown_activo.discard(par)
    return False

async def obtener_saldo_disponible():
    try:
        accounts = User(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        ).get_account_list(currency="USDT", account_type="trade")
        if accounts:
            return float(accounts[0]['available'])
        return 0.0
    except Exception as e:
        logger.error(f"Error obteniendo saldo: {e}")
        return 0.0

# =================================================================
# FUNCIONES PRINCIPALES DE TRADING
# =================================================================
async def analizar_impulso(par):
    try:
        # Verificar volumen mínimo primero
        stats_24h = Market(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        ).get_24h_stats(par)
        
        volumen_usdt = float(stats_24h["volValue"])
        if volumen_usdt < PARES_CONFIG[par]["vol_min"]:
            return None
            
        # Obtener velas de 1 minuto
        velas = Market(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        ).get_kline(symbol=par, kline_type="1min", limit=3)
        
        if len(velas) < 3:
            return None
            
        # Extraer datos de las últimas 3 velas
        vela_actual = float(velas[-1][2])
        vela_anterior = float(velas[-2][2])
        vela_anterior2 = float(velas[-3][2])
        
        # Verificar 2 velas alcistas consecutivas
        if not (vela_actual > vela_anterior > vela_anterior2):
            return None
            
        # Verificar momentum mínimo
        momentum = (vela_actual - vela_anterior2) / vela_anterior2
        if momentum < PARES_CONFIG[par]["momentum_min"]:
            return None
            
        # Verificar spread
        ticker = Market(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        ).get_ticker(par)
        
        spread = (float(ticker["bestAsk"]) - float(ticker["bestBid"])) / float(ticker["bestAsk"])
        if spread > 0.0015:  # 0.15%
            return None
            
        return {
            "par": par,
            "precio": vela_actual,
            "take_profit": vela_actual * (1 + PARES_CONFIG[par]["tp"]),
            "stop_loss": vela_actual * (1 - PARES_CONFIG[par]["sl"]),
            "momentum": momentum
        }
    except Exception as e:
        logger.error(f"Error analizando {par}: {e}")
        return None

async def calcular_cantidad_segura(par, saldo_disponible, precio):
    config_par = PARES_CONFIG[par]
    
    # 1. Ajustar por fees (0.3% total estimado)
    monto_max = saldo_disponible * 0.997
    cantidad = (monto_max / precio) // config_par["inc"] * config_par["inc"]
    
    # 2. Verificar mínimos
    if cantidad < config_par["min"]:
        return None
        
    # 3. Verificar mínimo en USDT
    valor_operacion = cantidad * precio
    if valor_operacion < MINIMO_USDT[par]:
        return None
        
    return cantidad

async def ejecutar_compra_segura(operacion):
    try:
        saldo = await obtener_saldo_disponible()
        if saldo < CONFIG["saldo_minimo"]:
            return None
            
        # Calcular cantidad segura
        cantidad = await calcular_cantidad_segura(
            operacion["par"], 
            saldo * CONFIG["uso_saldo"], 
            operacion["precio"]
        )
        if not cantidad:
            return None
            
        # Ejecutar compra
        trade_client = Trade(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        
        order = trade_client.create_market_order(operacion["par"], "buy", cantidad)
        fee = float(order.get("fee", 0))
        
        operacion.update({
            "id_orden": order["orderId"],
            "cantidad": cantidad,
            "precio_entrada": float(order["price"]),
            "hora_entrada": datetime.now(),
            "take_profit": float(order["price"]) * (1 + CONFIG["min_ganancia_objetivo"]),
            "stop_loss": float(order["price"]) * (1 + CONFIG["nivel_proteccion"]),
            "max_precio": float(order["price"]),
            "fee_compra": fee,
            "saldo_restante": saldo - (cantidad * operacion["precio"]) - fee,
            "fase_tp": True  # TP completo para saldos pequeños
        })
        
        # Notificación detallada
        await bot.send_message(
            os.getenv("CHAT_ID"),
            f"🚀 ENTRADA SEGURA {operacion['par']}\n"
            f"💵 Precio: {operacion['precio_entrada']:.8f}\n"
            f"📈 Objetivo: {operacion['take_profit']:.8f} (+{CONFIG['min_ganancia_objetivo']*100:.2f}%)\n"
            f"🛑 Stop: {operacion['stop_loss']:.8f}\n"
            f"💸 Fee: {fee:.6f} USDT\n"
            f"💰 Saldo restante: {operacion['saldo_restante']:.2f} USDT"
        )
        
        operaciones_activas.append(operacion)
        operaciones_recientes[operacion["par"]] = datetime.now()
        cooldown_activo.add(operacion["par"])
        return operacion
        
    except Exception as e:
        logger.error(f"Error en compra segura: {e}")
        return None

async def gestionar_operacion_low_capital(operacion):
    try:
        ticker = Market(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        ).get_ticker(operacion["par"])
        
        precio_actual = float(ticker["price"])
        operacion["max_precio"] = max(operacion["max_precio"], precio_actual)
        
        # 1. Take Profit completo
        if precio_actual >= operacion["take_profit"]:
            await ejecutar_venta_completa(operacion, "take_profit")
            return True
            
        # 2. Stop Loss dinámico
        ganancia = (operacion["max_precio"] - operacion["precio_entrada"]) / operacion["precio_entrada"]
        
        if ganancia > 0.015:  # Si lleva +1.5%
            nuevo_sl = operacion["precio_entrada"] * 1.005  # Lock 0.5% de ganancia
            operacion["stop_loss"] = max(operacion["stop_loss"], nuevo_sl)
            
        if precio_actual <= operacion["stop_loss"]:
            await ejecutar_venta_completa(operacion, "stop_loss")
            return True
            
        # 3. Tiempo máximo
        if (datetime.now() - operacion["hora_entrada"]).seconds > CONFIG["max_duracion_minutos"] * 60:
            await ejecutar_venta_completa(operacion, "tiempo_excedido")
            return True
            
        return False
    except Exception as e:
        logger.error(f"Error gestionando operación: {e}")
        return False

async def ejecutar_venta_completa(operacion, motivo):
    try:
        trade_client = Trade(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        
        order = trade_client.create_market_order(operacion["par"], "sell", operacion["cantidad"])
        fee = float(order.get("fee", 0))
        ganancia = ((float(order["price"]) - operacion["precio_entrada"]) / operacion["precio_entrada"]) * 100
        
        operacion.update({
            "precio_salida": float(order["price"]),
            "hora_salida": datetime.now(),
            "ganancia": ganancia,
            "motivo_salida": motivo,
            "fee_venta": fee
        })
        
        # Calcular balance real
        balance_neto = (operacion["cantidad"] * operacion["precio_salida"]) - fee
        ganancia_neto = balance_neto - (operacion["cantidad"] * operacion["precio_entrada"] + operacion["fee_compra"])
        
        # Notificación transparente
        emoji = "🟢" if ganancia_neto >= 0 else "🔴"
        await bot.send_message(
            os.getenv("CHAT_ID"),
            f"{emoji} SALIDA COMPLETA {operacion['par']}\n"
            f"📌 Motivo: {motivo}\n"
            f"🔢 Entrada: {operacion['precio_entrada']:.8f}\n"
            f"💰 Salida: {operacion['precio_salida']:.8f}\n"
            f"📈 Ganancia Bruta: {ganancia:.2f}%\n"
            f"💸 Fee total: {operacion['fee_compra'] + fee:.6f} USDT\n"
            f"💵 Ganancia Neta: {ganancia_neto:.4f} USDT"
        )
        
        # Actualizar historial
        async with lock:
            operaciones_activas.remove(operacion)
            historial_operaciones.append(operacion)
            await guardar_historial()
            
        return True
    except Exception as e:
        logger.error(f"Error en venta: {e}")
        return False

# =================================================================
# CICLO PRINCIPAL DE TRADING
# =================================================================
async def ciclo_trading_low_capital():
    global bot_activo
    
    while bot_activo:
        try:
            async with lock:
                # 1. Verificar saldo mínimo
                saldo = await obtener_saldo_disponible()
                if saldo < CONFIG["saldo_minimo"]:
                    await asyncio.sleep(60)
                    continue
                    
                # 2. Priorizar pares con mejor relación riesgo/beneficio
                pares_priorizados = sorted(
                    PARES_CONFIG.keys(),
                    key=lambda p: (PARES_CONFIG[p]["momentum_min"] / MINIMO_USDT[p]),
                    reverse=True
                )
                
                # 3. Buscar oportunidades
                for par in pares_priorizados[:3]:  # Solo top 3 más eficientes
                    if await verificar_cooldown(par):
                        continue
                        
                    señal = await analizar_impulso(par)
                    if señal:
                        operacion = await ejecutar_compra_segura(señal)
                        if operacion:
                            await asyncio.sleep(5)  # Esperar antes de siguiente operación
                            break
                
                # 4. Gestionar operaciones activas
                for op in operaciones_activas[:]:
                    await gestionar_operacion_low_capital(op)
                    
            await asyncio.sleep(CONFIG["reanalisis_segundos"])
        except Exception as e:
            logger.error(f"Error en ciclo: {e}")
            await asyncio.sleep(30)

# =================================================================
# COMANDOS DE TELEGRAM
# =================================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    global bot_activo
    if not bot_activo:
        bot_activo = True
        asyncio.create_task(ciclo_trading_low_capital())
        await message.answer(
            "🚀 Bot Iniciado (Modo Low Capital)\n"
            "⚡ Configuración actual:\n"
            f"- Uso de saldo: {CONFIG['uso_saldo']*100:.0f}%\n"
            f"- TP mínimo: {CONFIG['min_ganancia_objetivo']*100:.2f}%\n"
            f"- Máx. operaciones: {CONFIG['max_operaciones']}\n"
            f"- Saldo mínimo: ${CONFIG['saldo_minimo']:.2f}"
        )
    else:
        await message.answer("⚠ El bot ya está activo")

@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    global bot_activo
    bot_activo = False
    await message.answer("🛑 Bot detenido")

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    saldo = await obtener_saldo_disponible()
    pares_viables = [p for p in PARES_CONFIG.keys() if MINIMO_USDT[p] <= saldo*0.9]
    
    await message.answer(
        f"💰 Balance Actual\n"
        f"Saldo disponible: {saldo:.2f} USDT\n"
        f"Mínimo requerido: {CONFIG['saldo_minimo']:.2f} USDT\n"
        f"Pares viables: {', '.join(pares_viables)}"
    )

@dp.message(Command("operaciones"))
async def cmd_operaciones(message: types.Message):
    if not operaciones_activas:
        await message.answer("No hay operaciones activas")
        return
        
    respuesta = "📈 Operaciones Activas:\n\n"
    for op in operaciones_activas:
        duracion = (datetime.now() - op["hora_entrada"]).seconds // 60
        ganancia_actual = ((op["max_precio"] - op["precio_entrada"]) / op["precio_entrada"]) * 100
        
        respuesta += (
            f"🔹 {op['par']}\n"
            f"Entrada: {op['precio_entrada']:.8f}\n"
            f"Actual: {op['max_precio']:.8f}\n"
            f"Ganancia: {ganancia_actual:.2f}%\n"
            f"Stop: {op['stop_loss']:.8f}\n"
            f"Duración: {duracion} min\n\n"
        )
    
    await message.answer(respuesta)

# =================================================================
# EJECUCIÓN PRINCIPAL
# =================================================================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())