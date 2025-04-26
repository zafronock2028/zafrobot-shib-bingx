from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def index():
    return 'Zafrobot SHIB BingX activo y en espera...'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
