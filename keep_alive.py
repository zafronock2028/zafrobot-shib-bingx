from flask import Flask
from threading import Thread
import logging

app = Flask(__name__)

@app.route('/')
def verificar_estado():
    return "🟢 Bot en funcionamiento", 200

def ejecutar_servidor():
    app.run(host='0.0.0.0', port=10000)

def mantener_activo():
    logging.info("Iniciando servidor keep-alive...")
    servidor = Thread(target=ejecutar_servidor)
    servidor.daemon = True
    servidor.start()