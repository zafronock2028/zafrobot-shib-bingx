import requests
import time
import hashlib
import hmac

# TUS CLAVES API de BINGX
API_KEY = "LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA"
SECRET_KEY = "Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg"

# Configuración
PAR = "SHIB-USDT"
TAKE_PROFIT = 0.02    # +2% de ganancia
STOP_LOSS = -0.02     # -2% de stop loss
RETROCESO_COMPRA = -0.003  # Espera retroceso de -0.3% para entrar
PORCENTAJE_OPERAR = 0.80   # Usa el 80% del saldo disponible
INTERVALO_VERIFICACION = 10  # Segundos entre revisiones

saldo_total_ganado = 0
numero_operaciones = 0

def firmar(query_string):
    return hmac.new(SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def obtener_precio_actual():
    try:
        url = f"https://open-api.bingx.com/openApi/spot/v1/market/trades?symbol={PAR}&limit=1"
        response = requests.get(url)
        data = response.json()
        return float(data['data'][0]['price'])
    except Exception as e:
        print(f"Error al obtener precio: {e}")
        return None

def obtener_saldo_usdt():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/balance"
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = firmar(query_string)
    headers = {"X-BX-APIKEY": API_KEY}
    full_url = f"{url}?{query_string}&signature={signature}"
    response = requests.get(full_url, headers=headers)
    balances = response.json()['data']['balances']
    for asset in balances:
        if asset['asset'] == 'USDT':
            return float(asset['free'])
    return 0

def comprar_shib(cantidad, precio_compra):
    url = "https://open-api.bingx.com/openApi/spot/v1/trade/order"
    timestamp = str(int(time.time() * 1000))
    params = {
        "symbol": PAR,
        "side": "BUY",
        "type": "LIMIT",
        "price": f"{precio_compra:.8f}",
        "quantity": f"{cantidad:.0f}",
        "timestamp": timestamp
    }
    query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    signature = firmar(query_string)
    params['signature'] = signature
    headers = {"X-BX-APIKEY": API_KEY, "Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(url, headers=headers, data=params)
    return response.json()

def vender_shib(cantidad, precio_venta):
    url = "https://open-api.bingx.com/openApi/spot/v1/trade/order"
    timestamp = str(int(time.time() * 1000))
    params = {
        "symbol": PAR,
        "side": "SELL",
        "type": "LIMIT",
        "price": f"{precio_venta:.8f}",
        "quantity": f"{cantidad:.0f}",
        "timestamp": timestamp
    }
    query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    signature = firmar(query_string)
    params['signature'] = signature
    headers = {"X-BX-APIKEY": API_KEY, "Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(url, headers=headers, data=params)
    return response.json()

def zafrobot_dinamico():
    global saldo_total_ganado, numero_operaciones

    print("\\n=== ZafroBot Dinámico Iniciado ===\\n")

    while True:
        precio_inicio = obtener_precio_actual()
        if precio_inicio is None:
            print("No se pudo obtener el precio inicial. Reintentando...")
            time.sleep(INTERVALO_VERIFICACION)
            continue

        saldo_disponible = obtener_saldo_usdt()
        if saldo_disponible < 1:
            print("Saldo insuficiente. Bot detenido.")
            break

        cantidad_usdt = saldo_disponible * PORCENTAJE_OPERAR
        print(f"Saldo disponible: ${saldo_disponible:.2f} | Operando con: ${cantidad_usdt:.2f}")

        while True:
            precio_actual = obtener_precio_actual()
            if precio_actual is None:
                print("Error de precio. Reintentando...")
                time.sleep(INTERVALO_VERIFICACION)
                continue

            variacion = (precio_actual - precio_inicio) / precio_inicio
            print(f"Esperando retroceso... Variación actual: {variacion * 100:.2f}%")

            if variacion <= RETROCESO_COMPRA:
                cantidad_shib = (cantidad_usdt / precio_actual)
                print(f"Comprando {cantidad_shib:.0f} SHIB a {precio_actual:.8f} USDT...")
                comprar_shib(cantidad_shib, precio_actual)

                precio_objetivo_ganancia = precio_actual * (1 + TAKE_PROFIT)
                precio_objetivo_stop = precio_actual * (1 + STOP_LOSS)

                while True:
                    time.sleep(INTERVALO_VERIFICACION)
                    precio_nuevo = obtener_precio_actual()
                    if precio_nuevo is None:
                        continue

                    if precio_nuevo >= precio_objetivo_ganancia:
                        vender_shib(cantidad_shib, precio_nuevo)
                        ganancia = cantidad_usdt * TAKE_PROFIT
                        saldo_total_ganado += ganancia
                        numero_operaciones += 1
                        print(f"GANANCIA lograda: +${ganancia:.2f}")
                        break

                    if precio_nuevo <= precio_objetivo_stop:
                        vender_shib(cantidad_shib, precio_nuevo)
                        ganancia = cantidad_usdt * STOP_LOSS
                        saldo_total_ganado += ganancia
                        numero_operaciones += 1
                        print(f"STOP LOSS activado: -${abs(ganancia):.2f}")
                        break
                break
            else:
                time.sleep(INTERVALO_VERIFICACION)

    print("\\n=== RESUMEN FINAL ===")
    print(f"Operaciones realizadas: {numero_operaciones}")
    print(f"Ganancia total acumulada: ${saldo_total_ganado:.2f}")
    print("========================\\n")

zafrobot_dinamico()