import os
import asyncio
from aiohttp import web
from aiohttp.web_response import Response
from aiogram import Bot, Dispatcher, types

# Variables de entorno
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Crear bot
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Función de inicio simple
async def home(request):
    return Response(text="Bot funcionando correctamente.")

# Función principal para enviar mensajes
async def start_bot():
    try:
        saldo = obtener_saldo()
        if saldo is not None:
            await bot.send_message(chat_id=CHAT_ID, text=f'Saldo actual: {saldo}')
        else:
            await bot.send_message(chat_id=CHAT_ID, text='No se pudo obtener el saldo.')
    except Exception as e:
        await bot.send_message(chat_id=CHAT_ID, text=f'Error: {str(e)}')

# Función simulada para obtener saldo
def obtener_saldo():
    return None  # Aquí debes poner tu lógica real

# Arranque del servidor y bot
async def on_startup(app):
    asyncio.create_task(start_bot())

app = web.Application()
app.router.add_get('/', home)
app.on_startup.append(on_startup)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=5000)