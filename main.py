from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
import asyncio

# Token de tu bot de Telegram
TOKEN = "7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM"

# Crear instancia del bot
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Mantener vivo el servidor con Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot está funcionando correctamente."

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Manejador para el comando /start
@router.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ Bot activo y recibiendo mensajes correctamente.")

async def main():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())