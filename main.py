import os
import asyncio
import hmac
import hashlib
import base64
import time
import aiohttp
from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Variables de entorno (de Render)
KUCOIN_API_KEY = os.getenv("API_KEY")
KUCOIN_API_SECRET = os.getenv("SECRET_KEY")
KUCOIN_API_PASSPHRASE = os.getenv("PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Inicializar KuCoin Client y Bot de Telegram
client = Client(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Variables de control
bot_encendido = False

# Crear botones
botones_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🚀 Encender Bot", callback_data="encender")],
    [InlineKeyboardButton(text="🛑 Apagar Bot", callback_data="apagar")],
    [InlineKeyboardButton(text="📊 Estado del Bot", callback_data="estado")],
    [InlineKeyboardButton(text="💰 Actualizar Saldo", callback_data="saldo")]
])

# Función para consultar saldo
async def obtener_saldo_usdt():
    try:
        cuentas = client.get_accounts()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                saldo = float(cuenta['available'])
                return saldo
    except Exception as e:
        print(f"Error obteniendo saldo: {e}")
    return 0.0

# Función de trading simulada (análisis + compra + venta)
async def iniciar_trading():
    global bot_encendido
    while bot_encendido:
        saldo = await obtener_saldo_usdt()
        if saldo > 1:  # mínimo para operar
            await bot.send_message(CHAT_ID, "📈 Escaneando oportunidades de trading...")

            # Simulación de detección de oportunidad
            await asyncio.sleep(2)  # tiempo de escaneo
            await bot.send_message(CHAT_ID, "🚀 ¡Oportunidad detectada en SEI/USDT!\n🎯 Buscando +3% de ganancia...\n🛡️ Stop Loss: -1.5%\n\n✅ Ejecutando compra en Market...")

            await asyncio.sleep(2)  # simulando compra
            precio_entrada = 0.2384  # ejemplo
            monto_usado = saldo * 0.98  # usa el 98% del saldo disponible

            await bot.send_message(CHAT_ID, f"✅ Compra realizada:\n\n🔹 Par: SEI/USDT\n🔹 Entrada: {precio_entrada} USDT\n🔹 Monto: {monto_usado:.2f} USDT\n\n🧠 Monitoreando el mercado...")

            await asyncio.sleep(5)  # simulando monitoreo y ganancia

            precio_salida = precio_entrada * 1.03
            ganancia = monto_usado * 0.03
            nuevo_saldo = saldo + ganancia

            await bot.send_message(CHAT_ID, f"🏁 ¡Objetivo alcanzado!\n\n💵 SEI/USDT\n🔹 Entrada: {precio_entrada}\n🔹 Salida: {precio_salida:.4f}\n📈 Ganancia: +3.00%\n💰 Beneficio: +{ganancia:.2f} USDT\n\nNuevo saldo estimado: {nuevo_saldo:.2f} USDT 🔥")

        else:
            await bot.send_message(CHAT_ID, "⚠️ Saldo insuficiente para operar.")
        
        await asyncio.sleep(15)  # espera antes de buscar nueva oportunidad

# Inicio del bot con /start
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "✅ ZafroBot Scalper PRO ha iniciado correctamente.\n\nSelecciona una opción:",
        reply_markup=botones_menu
    )

# Manejador de botones
@dp.callback_query()
async def botones_menu_handler(callback: types.CallbackQuery):
    global bot_encendido

    if callback.data == "encender":
        if not bot_encendido:
            bot_encendido = True
            await callback.message.answer("🚀 Bot encendido. Escaneando mercado y preparando operaciones.")
            asyncio.create_task(iniciar_trading())
        else:
            await callback.message.answer("⚡ El bot ya está encendido.")
    elif callback.data == "apagar":
        if bot_encendido:
            bot_encendido = False
            await callback.message.answer("🛑 Bot apagado correctamente.")
        else:
            await callback.message.answer("✅ El bot ya estaba apagado.")
    elif callback.data == "estado":
        estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
        await callback.message.answer(f"📊 Estado actual del bot: {estado}")
    elif callback.data == "saldo":
        saldo = await obtener_saldo_usdt()
        await callback.message.answer(f"💰 Saldo disponible en KuCoin Trading: {saldo:.2f} USDT")
    
    await callback.answer()

# Main de ejecución
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())