import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiohttp import web

# Variables de entorno
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Crear bot y dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Función que envía el mensaje de prueba
async def enviar_mensaje_test():
    while True:
        try:
            await bot.send_message(chat_id=CHAT_ID, text="✅ Test funcionando correctamente.")
        except Exception as e:
            print(f"Error enviando mensaje: {e}")
        await asyncio.sleep(60)  # Espera 60 segundos antes de enviar otro

# Ruta raíz para comprobar que el bot está vivo
async def handle(request):
    return web.Response(text="Bot funcionando correctamente.")

# Función principal para arrancar todo
async def start_bot():
    asyncio.create_task(enviar_mensaje_test())  # Crea tarea de enviar mensaje cada minuto

# Configurar servidor web
app = web.Application()
app.router.add_get('/', handle)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    web.run_app(app, host='0.0.0.0', port=5000)