import gzip  # <--- Asegúrate de tener este import arriba

# WebSocket privado para actualizar saldo en vivo
async def websocket_saldo_bingx():
    global saldo_actual_spot
    url = "wss://open-api-swap.bingx.com/swap-market"
    while True:
        try:
            async with websockets.connect(url) as websocket:
                timestamp = str(int(time.time() * 1000))
                sign = create_signature(secret_key, timestamp)
                
                auth_payload = {
                    "id": "auth",
                    "reqType": "subscribe",
                    "data": {
                        "apiKey": api_key,
                        "timestamp": timestamp,
                        "signature": sign
                    }
                }
                
                await websocket.send(json.dumps(auth_payload))
                logging.info("Autenticado al WebSocket de BingX.")

                # Subscribirse al canal de balance
                subscribe_payload = {
                    "id": "balance_subscribe",
                    "reqType": "subscribe",
                    "data": {
                        "channel": "balance"
                    }
                }
                
                await websocket.send(json.dumps(subscribe_payload))
                logging.info("Suscripto al canal de balance.")
                
                while True:
                    response = await websocket.recv()
                    
                    # Descomprimir la respuesta si está comprimida
                    try:
                        decompressed_data = gzip.decompress(response).decode('utf-8')
                        data = json.loads(decompressed_data)
                    except:
                        # Si no está comprimido, leer como texto normal
                        data = json.loads(response)
                    
                    if "data" in data and "balances" in data["data"]:
                        balances = data["data"]["balances"]
                        for asset in balances:
                            if asset['asset'] == 'USDT':
                                saldo_actual_spot = float(asset['availableMargin'])  # saldo disponible actualizado
                                logging.info(f"Nuevo saldo Spot detectado: {saldo_actual_spot} USDT")
        except Exception as e:
            logging.error(f"Error en WebSocket: {e}")
            await asyncio.sleep(5)  # Reintentar si falla