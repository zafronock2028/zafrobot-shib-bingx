import os
import logging
import asyncio
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Trade, Market, User
from dotenv import load_dotenv

# Configuración inicial
load_dotenv()

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
    # ... (config similar para otros pares)
}

CONFIG = {
    "uso_saldo": 0.90,           # Usar 90% del saldo disponible
    "max_operaciones": 1,        # Solo 1 operación a la vez
    "puntaje_minimo": 3.0,
    "reanalisis_segundos": 15,
    "saldo_minimo": 20.00,
    "min_ganancia_objetivo": 0.02,  # TP mínimo 2%
    "nivel_proteccion": -0.01,
    "auto_optimizar": False,      # Desactivado para saldos pequeños
    "noticias": False
}

# =================================================================
# FUNCIONES PRINCIPALES (OPTIMIZADAS PARA LOW CAPITAL)
# =================================================================

async def calcular_cantidad_segura(par, saldo_disponible, precio):
    """
    Calcula la cantidad a comprar garantizando:
    - Suficiente para fees (3 transacciones)
    - Cumple mínimos del par
    - No excede el saldo disponible
    """
    config_par = PARES_CONFIG[par]
    
    # 1. Calcular máximo teórico considerando fees (0.3% total)
    monto_max = saldo_disponible * 0.997  # Ajuste por fees
    cantidad_teorica = (monto_max / precio) // config_par["inc"] * config_par["inc"]
    
    # 2. Verificar mínimos
    if cantidad_teorica < config_par["min"]:
        return None
        
    # 3. Verificar mínimo en USDT
    valor_operacion = cantidad_teorica * precio
    if valor_operacion < MINIMO_USDT[par]:
        return None
        
    return cantidad_teorica

async def ejecutar_compra_segura(operacion):
    """Versión segura para saldos pequeños"""
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
        order = trade.create_market_order(operacion["par"], "buy", cantidad)
        fee = float(order["fee"])
        
        # Configurar operación SIN TP PARCIAL (para saldos < $50)
        operacion.update({
            "id_orden": order["orderId"],
            "cantidad": cantidad,
            "precio_entrada": float(order["price"]),
            "hora_entrada": datetime.utcnow(),
            "take_profit": float(order["price"]) * (1 + CONFIG["min_ganancia_objetivo"]),
            "stop_loss": float(order["price"]) * (1 + CONFIG["nivel_proteccion"]),
            "max_precio": float(order["price"]),
            "fee_compra": fee,
            "saldo_restante": saldo - (cantidad * operacion["precio"]) - fee,
            "fase_tp": True  # Forzar TP completo
        })
        
        # Notificación detallada
        await bot.send_message(
            CHAT_ID,
            f"🚀 ENTRADA SEGURA {operacion['par']}\n"
            f"💵 Precio: {operacion['precio_entrada']:.8f}\n"
            f"📈 Objetivo: {operacion['take_profit']:.8f} (+{CONFIG['min_ganancia_objetivo']*100:.2f}%)\n"
            f"🛑 Stop: {operacion['stop_loss']:.8f}\n"
            f"💸 Fee: {fee:.6f} USDT\n"
            f"💰 Saldo restante: {operacion['saldo_restante']:.2f} USDT"
        )
        
        operaciones_activas.append(operacion)
        operaciones_recientes[operacion["par"]] = datetime.utcnow()
        return operacion
        
    except Exception as e:
        logger.error(f"Error en compra segura: {e}")
        return None

async def gestionar_operacion_low_capital(operacion):
    """Versión simplificada del trailing stop para saldos pequeños"""
    try:
        ticker = market.get_ticker(operacion["par"])
        precio_actual = float(ticker["price"])
        operacion["max_precio"] = max(operacion["max_precio"], precio_actual)
        
        # 1. Take Profit completo (no hay parcial)
        if precio_actual >= operacion["take_profit"]:
            await ejecutar_venta_completa(operacion, "take_profit")
            return True
            
        # 2. Stop Loss dinámico
        ganancia = (operacion["max_precio"] - operacion["precio_entrada"]) / operacion["precio_entrada"]
        
        if ganancia > 0.015:  # Si lleva +1.5%
            nuevo_sl = operacion["precio_entrada"] * 1.005  # Lock 0.5% de ganancia
        else:
            nuevo_sl = operacion["stop_loss"]
            
        operacion["stop_loss"] = max(operacion["stop_loss"], nuevo_sl)
        
        # 3. Verificar salida
        if precio_actual <= operacion["stop_loss"]:
            await ejecutar_venta_completa(operacion, "stop_loss")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error en gestión low capital: {e}")
        return False

async def ejecutar_venta_completa(operacion, motivo):
    """Vende el 100% de la posición"""
    try:
        order = trade.create_market_order(operacion["par"], "sell", operacion["cantidad"])
        fee = float(order["fee"])
        ganancia = ((float(order["price"]) - operacion["precio_entrada"]) / operacion["precio_entrada"]) * 100
        
        operacion.update({
            "precio_salida": float(order["price"]),
            "hora_salida": datetime.utcnow(),
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
            CHAT_ID,
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
        logger.error(f"Error en venta completa: {e}")
        return False

# =================================================================
# CICLO PRINCIPAL OPTIMIZADO
# =================================================================

async def ciclo_trading_low_capital():
    """Versión optimizada para saldos desde $36"""
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
                    PARES,
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
                
                # 4. Gestionar operación activa (si existe)
                for op in operaciones_activas[:]:
                    if (datetime.utcnow() - op["hora_entrada"]).seconds > 1800:  # 30 min máximo
                        await ejecutar_venta_completa(op, "tiempo_excedido")
                    else:
                        await gestionar_operacion_low_capital(op)
                        
            await asyncio.sleep(CONFIG["reanalisis_segundos"])
            
        except Exception as e:
            logger.error(f"Error en ciclo low capital: {e}")
            await asyncio.sleep(30)

# =================================================================
# COMANDOS DE TELEGRAM (ACTUALIZADOS)
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
            f"- Máx. operaciones: {CONFIG['max_operaciones']}"
        )
    else:
        await message.answer("⚠ El bot ya está activo")

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    saldo = await obtener_saldo_disponible()
    await message.answer(
        f"💰 Balance Actual\n"
        f"Saldo disponible: {saldo:.2f} USDT\n"
        f"Mínimo requerido: {CONFIG['saldo_minimo']:.2f} USDT\n"
        f"Pares viables: {', '.join(p for p in PARES if MINIMO_USDT[p] <= saldo*0.9)}"
    )

# =================================================================
# EJECUCIÓN PRINCIPAL
# =================================================================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())