#!/bin/bash
echo "Iniciando Zafrobot Dinámico Pro..."
python keep_alive.py &  # Inicia el keep-alive en segundo plano
python main.py