import asyncio
from aiogram import Bot, Dispatcher, types
import aiohttp
from aiohttp import ClientSession

# Tus datos ya integrados:
API_KEY = "RA2cfzSaJKWxDrVEXitoiLZK1dpfEQLaCe8TIdG77Nl2GJEiImL7eXRRWIJDdjwYpakLIa37EQIpI6jpQ"
SECRET_KEY = "VlwOFCk2hsJxth98TQLZoHf7HLDxDCNHuGmIKyhHgh9UoturNTon3rkiLwtbsr1zxqZcOvVyWNCILFDzVVLg"
TELEGRAM_TOKEN = "8100886306:AAFRDnn32wMKXhZGfkThifFFGPhL0p6KFjw"
CHAT_ID = "1130366010"

# Inicializar bot y dispatcher
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

async def consultar_saldo():
    url = "https://open-api.bingx.com/openApi/wallet/sumAssets"
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    async with ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                result = await response.json()
                if result.get("code") == 0:
                    balances = result.get("data", [])
                    for asset in balances:
                        if asset.get("asset") == "USDT":
                            saldo = asset.get("balance", "0")
                            return saldo
                    return "0"
                else:
                    return None
        except Exception as e:
            print(f"Error consultando saldo: {e}")
            return None

@dp.message(commands=["start"])
async def start(message: types.Message):
    await message.answer("🤖 ¡Hola! Soy ZafroBot Dinámico Pro.\n\nEstoy listo para ayudarte a consultar tu saldo de USDT en BingX.\n\nUsa el comando /saldo para ver tu saldo actual.")

@dp.message(commands=["saldo"])
async def saldo(message: types.Message):
    saldo = await consultar_saldo()
    if saldo is not None:
        await message.answer(f"💵 Tu saldo actual de USDT en BingX es: **{saldo} USDT**")
    else:
        await message.answer("⚠️ No se pudo obtener el saldo. Revisa tus credenciales o intenta más tarde.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())