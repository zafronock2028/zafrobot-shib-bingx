import os
import logging
import asyncio
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

# Configurar logs
logging.basicConfig(level=logging.INFO)

# Variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Crear bot y dispatcher
bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# Función para obtener saldo en Spot
def obtener_saldo():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/assets"
    headers = {
        "X-BX-APIKEY": API_KEY
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        if data['code'] == 0:
            for asset in data['data']:
                if asset['asset'] == 'USDT':
                    return float(asset['balance'])
        else:
            return None
    else:
        return None

# Comando /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    saldo = obtener_saldo()
    if saldo is not None:
        await message.answer(
            f"✅ ¡Bot vinculado correctamente!\n\n<b>Saldo disponible:</b> {saldo:.2f} USDT"
        )
    else:
        await message.answer(
            "⚠️ Bot vinculado, pero no se pudo obtener el saldo.\nVerifica tus API Keys."
        )

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())