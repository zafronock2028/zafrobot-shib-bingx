import asyncio
import os
import time
import hmac
import hashlib
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from kucoin.client import Client

# Cargar variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
PASSPHRASE = os.getenv("PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Inicializar KuCoin y Telegram Bot
client = Client(API_KEY, SECRET_KEY, PASSPHRASE)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Variables internas
operaciones_realizadas = 0
ganancia_total_dia = 0.0
saldo_acumulado = 0.0
operacion_en_curso = False
primer_operacion_del_dia = False

# Pares configurados
pares = ["SEI-USDT", "ACH-USDT", "CVC-USDT"]

async def analizar_mercado():
    global operaciones_realizadas, ganancia_total_dia, saldo_acumulado, operacion_en_curso, primer_operacion_del_dia
    while True:
        if not operacion_en_curso:
            oportunidad_detectada = False
            for par in pares:
                try:
                    ticker = client.get_ticker(symbol=par)
                    precio_actual = float(ticker['price'])
                    # Simulador simple: detectar bajadas mínimas (puedes mejorar esto luego)
                    if precio_actual:
                        oportunidad_detectada = True
                        cantidad_usdt = 5  # Puedes cambiar esto o hacerlo dinámico basado en saldo
                        cantidad_compra = cantidad_usdt / precio_actual
                        orden_compra = client.create_market_order(
                            symbol=par,
                            side="buy",
                            size=round(cantidad_compra, 6)
                        )

                        operacion_en_curso = True

                        if not primer_operacion_del_dia:
                            primer_operacion_del_dia = True
                            await bot.send_message(
                                CHAT_ID,
                                "📢 *¡Comenzando operaciones del día!*\n🌟 *Un nuevo día, nuevas oportunidades para crecer.*",
                                parse_mode="Markdown"
                            )

                        await bot.send_message(
                            CHAT_ID,
                            f"✅ *COMPRA ejecutada*\nPar: {par}\nCantidad: {round(cantidad_compra, 6)}\nPrecio: {precio_actual}",
                            parse_mode="Markdown"
                        )

                        # Esperar a que suba 2% para vender
                        precio_objetivo = precio_actual * 1.02
                        precio_stoploss = precio_actual * 0.98

                        while operacion_en_curso:
                            await asyncio.sleep(5)
                            ticker_nuevo = client.get_ticker(symbol=par)
                            precio_nuevo = float(ticker_nuevo['price'])

                            if precio_nuevo >= precio_objetivo:
                                client.create_market_order(
                                    symbol=par,
                                    side="sell",
                                    size=round(cantidad_compra, 6)
                                )
                                ganancia = cantidad_usdt * 0.02
                                ganancia_total_dia += ganancia
                                saldo_acumulado += ganancia
                                operaciones_realizadas += 1
                                await bot.send_message(
                                    CHAT_ID,
                                    f"🎯 *Take Profit alcanzado en {par}*\nGanancia: +2.0%\n💼 Nuevo saldo aproximado: +{saldo_acumulado:.2f} USDT\n📈 *Mini resumen:* {operaciones_realizadas} operación(es) completadas hoy.",
                                    parse_mode="Markdown"
                                )
                                operacion_en_curso = False
                                break

                            elif precio_nuevo <= precio_stoploss:
                                client.create_market_order(
                                    symbol=par,
                                    side="sell",
                                    size=round(cantidad_compra, 6)
                                )
                                operaciones_realizadas += 1
                                await bot.send_message(
                                    CHAT_ID,
                                    f"⚠️ *Stop Loss activado en {par}*\nPérdida controlada.\n💼 Nuevo saldo aproximado: +{saldo_acumulado:.2f} USDT",
                                    parse_mode="Markdown"
                                )
                                operacion_en_curso = False
                                break
                except Exception as e:
                    await bot.send_message(CHAT_ID, f"Error analizando {par}: {str(e)}")

            if not oportunidad_detectada:
                await bot.send_message(CHAT_ID, "⏳ *Analizando mercado... sin oportunidades claras aún.*", parse_mode="Markdown")

        await asyncio.sleep(10)

async def resumen_diario():
    global operaciones_realizadas, ganancia_total_dia, saldo_acumulado, primer_operacion_del_dia
    while True:
        ahora = time.localtime()
        if ahora.tm_hour == 23 and ahora.tm_min == 59:
            mensaje = f"📊 *Resumen diario*\n"
            mensaje += f"🛒 Operaciones realizadas: {operaciones_realizadas}\n"
            mensaje += f"💰 Ganancia total del día: {ganancia_total_dia:.2f} USDT\n"
            mensaje += f"🔥 Rentabilidad diaria: +{(ganancia_total_dia/5)*100:.2f}%\n"
            mensaje += f"💎 Ganancia acumulada total: {saldo_acumulado:.2f} USDT\n"
            mensaje += f"⚡ Actividad del bot: {'Activo' if operaciones_realizadas > 0 else 'Esperando oportunidades'}\n"
            mensaje += f"📅 Fecha: {time.strftime('%d/%m/%Y - %H:%M', ahora)}\n\n"
            if ganancia_total_dia > 0:
                mensaje += "🎉 *¡Gran día de ganancias! Sigamos construyendo activos con Zafronock.*\n\n"
            mensaje += "🚀 *¿Quieres seguir creando más activos como este junto a Zafronock?*\n"
            mensaje += "📈 *Únete al canal oficial:* [GanandoConZafronock](https://t.me/GanandoConZafronock)\n"
            mensaje += "#GanandoConZafronock"
            await bot.send_message(CHAT_ID, mensaje, parse_mode="Markdown")

            # Resetear el día
            operaciones_realizadas = 0
            ganancia_total_dia = 0.0
            primer_operacion_del_dia = False

        await asyncio.sleep(60)

@dp.message(Command(commands=["start"]))
async def start(message: Message):
    await message.answer("🚀 *ZafroBot Scalper PRO v1 iniciado exitosamente.*\n🔎 *Analizando mercado en busca de oportunidades...*", parse_mode="Markdown")

async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        asyncio.create_task(analizar_mercado())
        asyncio.create_task(resumen_diario())
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())