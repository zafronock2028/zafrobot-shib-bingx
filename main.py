import os
from flask import Flask

app = Flask(__name__)

# Lee las claves desde las variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

@app.route('/')
def index():
    return f'Zafrobot SHIB BingX activo. API: {API_KEY[:4]}****'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
