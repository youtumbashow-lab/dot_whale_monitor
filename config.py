#!/usr/bin/env python3
"""
Конфигурация DOT Whale Monitor
"""

import os

# ==================== Polkadot RPC ====================
# Бесплатные публичные RPC-эндпоинты Polkadot (WebSocket)
# Для мониторинга используется substrate-interface, который работает через WebSocket
POLKADOT_RPC_URL = os.getenv(
    "POLKADOT_RPC_URL",
    "wss://rpc.polkadot.io"  # Официальный публичный RPC
)

# Альтернативные публичные эндпоинты:
# POLKADOT_RPC_URL = "wss://polkadot.api.onfinality.io/public-ws"
# POLKADOT_RPC_URL = "wss://polkadot-rpc.dwellir.com"
# POLKADOT_RPC_URL = "wss://1rpc.io/dot"

# ==================== Параметры токена ====================
# В Polkadot нативный токен DOT, decimals = 10
DOT_DECIMALS = 10
DOT_SYMBOL = "DOT"

# ==================== Фильтр ====================
# Минимальная сумма для оповещения (в DOT, не в планках)
MIN_AMOUNT_DOT = 10_000  # Например, 10,000 DOT

# ==================== Email (SMTP) ====================
EMAIL_CONFIG = {
    # Для Gmail используйте пароль приложения, не основной пароль!
    # Настройка: https://myaccount.google.com/apppasswords
    "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
    "sender": os.getenv("SMTP_SENDER", "your_email@gmail.com"),
    "password": os.getenv("SMTP_PASSWORD", "your_app_password"),
    "recipient": os.getenv("ALERT_EMAIL", "recipient@example.com"),
}

# ==================== Состояние ====================
STATE_FILE = "last_block.json"

# ==================== Логирование ====================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
