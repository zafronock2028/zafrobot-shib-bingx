import os
import time
import requests
import hmac
import hashlib
import json

# Variables de entorno
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Parámetros
symbol = "SHIB-USDT"
base_url = "https://api.bingx.com"
telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
cantidad_porcentaje_compra = 0.80  # 80% del saldo disponible

# Funciones
def enviar_telegram(mensaje):
    requests.post(telegram_url, data={"chat_id": CHAT_ID, "text": mensaje})

def firmar(query_string, secret_key):
    return hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def obtener_saldo_usdt():
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = firmar(query_string, SECRET_KEY)
    headers = {"X-BX-APIKEY": API_KEY}
    url = f"{base_url}/openApi/user/balance?{query_string}&signature={signature}"
    respuesta = requests.get(url, headers=headers)
    saldo_data = respuesta.json()
    try:
        for asset in saldo_data['data']:
            if asset['asset'] == 'USDT':
                return float(asset['balance'])
    except Exception as e:
        print(f"Error al obtener saldo: {e}")
        return 0
    return 0

def obtener_datos_candlestick():
    url = f"{base_url}/openApi/market/getKline?symbol={symbol}&interval=1m&limit=20"
    respuesta = requests.get(url)
    datos = respuesta.json()
    if datos['code'] == 0:
        return datos['data']
    else:
        print("Error al obtener datos del mercado")
        return []

def detectar_oportunidad(candles):
    if len(candles) < 5:
        return False

    volumenes = [float(candle['volume']) for candle in candles]
    cierres = [float(candle['close']) for candle in candles]

    volumen_reciente = volumenes[-1]
    volumen_promedio = sum(volumenes[:-1]) / len(volumenes[:-1])

    # Condiciones:
    # 1. Volumen reciente 1.5 veces mayor que el promedio
    # 2. Última vela verde (subida de precio)
    # 3. Mínimos crecientes en últimas 3 velas
    if (volumen_reciente > 1.5 * volumen_promedio and
        cierres[-1] > cierres[-2] and
        cierres[-2] > cierres[-3] and
        cierres[-3] > cierres[-4]):
        return True
    return False

def comprar(cantidad_usdt):
    timestamp = str(int(time.time() * 1000))
    params = f"symbol={symbol}&side=BUY&type=MARKET&quoteOrderQty={cantidad_usdt}&timestamp={timestamp}"
    signature = firmar(params, SECRET_KEY)
    headers = {"X-BX-APIKEY": API_KEY}
    url = f"{base_url}/openApi/spot/v1/trade/order?{params}&signature={signature}"
    respuesta = requests.post(url, headers=headers)
    return respuesta.json()

def vender(cantidad_shib):
    timestamp = str(int(time.time() * 1000))
    params = f"symbol={symbol}&side=SELL&type=MARKET&quantity={cantidad_shib}&timestamp={timestamp}"
    signature = firmar(params, SECRET_KEY)
    headers = {"X-BX-APIKEY": API_KEY}
    url = f"{base_url}/openApi/spot/v1/trade/order?{params}&signature={signature}"
    respuesta = requests.post(url, headers=headers)
    return respuesta.json()

def obtener_precio_actual():
    url = f"{base_url}/openApi/market/getPrice?symbol={symbol}"
    respuesta = requests.get(url)
    datos = respuesta.json()
    if datos['code'] == 0:
        return float(datos['data']['price'])
    else:
        return None

# Inicio del Bot
print("=== ZafroBot Dinámico Pro Iniciado ===")

while True:
    saldo = obtener_saldo_usdt()
    if saldo < 5:
        print("Saldo insuficiente para operar.")
        time.sleep(60)
        continue

    candles = obtener_datos_candlestick()
    if detectar_oportunidad(candles):
        cantidad_a_usar = saldo * cantidad_porcentaje_compra
        precio_actual = obtener_precio_actual()
        if not precio_actual:
            time.sleep(60)
            continue
        
        respuesta_compra = comprar(cantidad_a_usar)
        print(f"Compra ejecutada: {respuesta_compra}")

        # Esperar subida de 1% o stop loss de -2%
        precio_compra = obtener_precio_actual()
        objetivo = precio_compra * 1.01
        stop_loss = precio_compra * 0.98

        while True:
            precio_actual = obtener_precio_actual()
            if precio_actual >= objetivo:
                cantidad_shib = cantidad_a_usar / precio_compra
                respuesta_venta = vender(cantidad_shib)
                enviar_telegram(f"¡Venta exitosa en ganancia! Precio: {precio_actual:.8f}")
                print(f"Venta exitosa: {respuesta_venta}")
                break
            elif precio_actual <= stop_loss:
                cantidad_shib = cantidad_a_usar / precio_compra
                respuesta_venta = vender(cantidad_shib)
                enviar_telegram(f"Venta por stop loss activado. Precio: {precio_actual:.8f}")
                print(f"Venta por stop loss: {respuesta_venta}")
                break
            time.sleep(5)
    else:
        print("No hay oportunidad segura. Analizando...")
    
    time.sleep(20)
