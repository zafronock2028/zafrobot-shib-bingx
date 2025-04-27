import logging
import hmac
import hashlib
import time
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode

# TUS DATOS FIJOS INTEGRADOS
API_KEY = "LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA"
SECRET_KEY = "Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg"
TELEGRAM_BOT_TOKEN = "8100886306:AAFRDnn32wMKXhZGfKThiFFGPhL0p6KFjW"
CHAT_ID = "1130366010"

# Inicializar bot
bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Formato bonito de la tarjeta de saldo
def formatear_tarjeta(saldo):
    return (
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 <b>Saldo en Spot</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💵 <b>Moneda:</b> USDT\n"
        f"📈 <b>Disponible:</b> {saldo:.2f} USDT\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⏰ <i>Consulta en tiempo real</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━"
    )

# Obtener saldo de USDT en Spot
async def obtener_saldo_usdt():
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()

    headers = {
        "X-BX-APIKEY": API_KEY
    }

    url = f"https://open-api.bingx.com/openApi/user/spot/assets?{query_string}&signature={signature}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                balances = data.get("data", [])
                for balance in balances:
                    if balance.get("asset") == "USDT":
                        return float(balance.get("free", 0))
            return 0.0

# Comando /start
@dp.message(Command("start"))
async def start_command(message: types.Message):
    if str(message.from_user.id) != CHAT_ID:
        return
    await message.answer(
        "👋 ¡Bienvenido a <b>ZafroBot</b>!\n\nEnvía el comando <b>/saldo</b> para ver tu saldo actualizado.",
        parse_mode=ParseMode.HTML
    )

# Comando /saldo
@dp.message(Command("saldo"))
async def saldo_command(message: types.Message):
    if str(message.from_user.id) != CHAT_ID:
        return
    saldo = await obtener_saldo_usdt()
    tarjeta = formatear_tarjeta(saldo)
    await message.answer(tarjeta, parse_mode=ParseMode.HTML)

# Función principal
async def main():
    logging.basicConfig(level=logging.INFO)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())