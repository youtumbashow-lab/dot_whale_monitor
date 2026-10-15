#!/usr/bin/env python3
"""
Конфигурация DOT Whale Monitor (ежедневный отчёт)
"""

import os

# ==================== Polkadot RPC ====================
POLKADOT_RPC_URL = os.getenv(
    "POLKADOT_RPC_URL",
    "wss://rpc.polkadot.io"
)
# Альтернативы:
# POLKADOT_RPC_URL = "wss://polkadot.api.onfinality.io/public-ws"
# POLKADOT_RPC_URL = "wss://polkadot-rpc.dwellir.com"
# POLKADOT_RPC_URL = "wss://1rpc.io/dot"

# ==================== Параметры токена ====================
DOT_DECIMALS = 10
DOT_SYMBOL = "DOT"

# ==================== Фильтр ====================
# Минимальная сумма для попадания в отчёт (в DOT)
MIN_AMOUNT_DOT = 10_000

# ==================== Email (SMTP) ====================
EMAIL_CONFIG = {
    "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
    "sender": os.getenv("SMTP_SENDER", "your_email@gmail.com"),
    "password": os.getenv("SMTP_PASSWORD", "your_app_password"),
    "recipient": os.getenv("ALERT_EMAIL", "recipient@example.com"),
}

# ==================== Файлы состояния ====================
STATE_FILE = "last_block.json"
PENDING_FILE = "pending_transfers.json"

# ==================== Логирование ====================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
