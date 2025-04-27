import asyncio
import time
import hmac
import hashlib
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# API Key de BingX
API_KEY = "LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA"

# Secret Key de BingX
SECRET_KEY = "Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg"

# Token del Bot de Telegram
TELEGRAM_BOT_TOKEN = "7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM"

# Chat ID de Telegram (no usado aún, pero preparado)
CHAT_ID = "1130366010"

# Inicialización del bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Función para obtener saldo en USDT en Spot
async def get_usdt_balance():
    timestamp = int(time.time() * 1000)
    params = {
        "apiKey": API_KEY,
        "timestamp": timestamp
    }
    query_string = "&".join(f"{key}={params[key]}" for key in sorted(params))
    signature = hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    params["sign"] = signature

    url = "https://api.bingx.com/openapi/spot/v1/account/assets"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    print(f"Error HTTP {resp.status}")
                    return None
                data = await resp.json()

                if data and "data" in data and isinstance(data["data"], list):
                    for asset_info in data["data"]:
                        if asset_info.get("asset") == "USDT":
                            return float(asset_info.get("available", 0.0))
                return None
        except Exception as e:
            print(f"Error en la conexión con BingX: {e}")
            return None

# Comando /start
@dp.message(Command(commands=["start"]))
async def start_command(message: Message):
    await message.answer(
        "👋 ¡Bienvenido a ZafroBot!\n\n"
        "Este bot te ayuda a consultar tu saldo disponible de *USDT* en tu cuenta Spot de *BingX* en tiempo real.\n\n"
        "Envía el comando /saldo para ver tu saldo actualizado.",
        parse_mode="Markdown"
    )

# Comando /saldo
@dp.message(Command(commands=["saldo"]))
async def saldo_command(message: Message):
    balance = await get_usdt_balance()
    if balance is not None:
        balance_text = f"{balance:,.6f}"

        texto = (
            "╔══════════════════════════╗\n"
            "║      💳 *Saldo en Spot*      ║\n"
            "╠══════════════════════════╣\n"
            f"║ 💵 *Moneda:* `USDT`          ║\n"
            f"║ 📈 *Disponible:* `{balance_text}` ║\n"
            "╠══════════════════════════╣\n"
            "║ 🕒 _Consulta en tiempo real_ ║\n"
            "╚══════════════════════════╝"
        )

        await message.answer(texto, parse_mode="Markdown")
    else:
        await message.answer("❌ No se pudo obtener el saldo de USDT. Intenta más tarde.")

# Función principal
async def main():
    print("ZafroBot iniciado... (Esperando comandos en Telegram)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())