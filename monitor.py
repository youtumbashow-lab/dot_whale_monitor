#!/usr/bin/env python3
"""
DOT Whale Monitor
Мониторинг крупных переводов DOT с отправкой email-уведомлений.
Использует substrate-interface для подключения к Polkadot через WebSocket.
"""

import json
import smtplib
import logging
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

from substrateinterface import SubstrateInterface
from substrateinterface.exceptions import SubstrateRequestException

from config import (
    POLKADOT_RPC_URL,
    DOT_DECIMALS,
    DOT_SYMBOL,
    MIN_AMOUNT_DOT,
    EMAIL_CONFIG,
    STATE_FILE,
    LOG_LEVEL,
)

# ==================== Логирование ====================
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


# ==================== Работа с состоянием ====================

def load_last_block() -> int:
    """Загрузка последнего обработанного блока."""
    if Path(STATE_FILE).exists():
        try:
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                return int(data.get('last_block', 0))
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Не удалось прочитать {STATE_FILE}: {e}")
    return 0


def save_last_block(block_number: int) -> None:
    """Сохранение последнего обработанного блока."""
    with open(STATE_FILE, 'w') as f:
        json.dump({'last_block': block_number}, f)


# ==================== Подключение к Polkadot ====================

def connect_substrate() -> SubstrateInterface:
    """Подключение к Polkadot через WebSocket."""
    logger.info(f"Подключение к {POLKADOT_RPC_URL}...")
    substrate = SubstrateInterface(
        url=POLKADOT_RPC_URL,
        ss58_format=0,          # Polkadot использует SS58 формат 0
        type_registry_preset='polkadot',
        auto_discover=True,
    )
    logger.info("Подключение установлено.")
    return substrate


def get_latest_block(substrate: SubstrateInterface) -> int:
    """Получение номера последнего блока."""
    return substrate.get_block_number(substrate.get_chain_head())


# ==================== Обработка событий Transfer ====================

def process_block(substrate: SubstrateInterface, block_number: int):
    """
    Обработка одного блока: поиск событий balances.Transfer
    с суммой >= MIN_AMOUNT_DOT.
    Возвращает список найденных крупных переводов.
    """
    alerts = []

    try:
        block_hash = substrate.get_block_hash(block_number)
        if not block_hash:
            logger.warning(f"Не удалось получить хеш блока {block_number}")
            return alerts

        events = substrate.get_events(block_hash=block_hash)
    except SubstrateRequestException as e:
        logger.warning(f"Ошибка при получении блока {block_number}: {e}")
        return alerts

    for event in events:
        # Интересуют только события модуля balances и метода Transfer
        if event.value.get('event', {}).get('module_id') != 'Balances':
            continue
        if event.value.get('event', {}).get('event_id') != 'Transfer':
            continue

        try:
            attributes = event.value['event']['attributes']
            # В Polkadot Transfer: [from, to, amount]
            from_addr = attributes[0]
            to_addr = attributes[1]
            amount_plancks = int(attributes[2])
        except (KeyError, IndexError, ValueError, TypeError) as e:
            logger.warning(f"Ошибка парсинга события: {e}")
            continue

        amount_dot = amount_plancks / (10 ** DOT_DECIMALS)

        if amount_dot >= MIN_AMOUNT_DOT:
            alerts.append({
                'from': from_addr,
                'to': to_addr,
                'amount_plancks': amount_plancks,
                'amount_dot': amount_dot,
                'block': block_number,
                'extrinsic_hash': event.extrinsic_hash,
            })

    return alerts


# ==================== Email ====================

def send_email(subject: str, body: str) -> None:
    """Отправка email-уведомления."""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_CONFIG['sender']
    msg['To'] = EMAIL_CONFIG['recipient']
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP(EMAIL_CONFIG['smtp_host'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['sender'], EMAIL_CONFIG['password'])
            server.send_message(msg)
        logger.info(f"Email отправлен: {subject}")
    except Exception as e:
        logger.error(f"Ошибка отправки email: {e}")


def format_alert_message(transfer: dict) -> str:
    """Форматирование текста уведомления."""
    return f"""
Обнаружен крупный перевод DOT!

Сумма: {transfer['amount_dot']:,.2f} {DOT_SYMBOL}
От: {transfer['from']}
Кому: {transfer['to']}

Блок: {transfer['block']}
Транзакция: https://polkadot.subscan.io/extrinsic/{transfer['extrinsic_hash']}

Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""".strip()


# ==================== Основная логика ====================

def main():
    logger.info("Запуск DOT Whale Monitor...")

    last_block = load_last_block()
    logger.info(f"Последний обработанный блок: {last_block}")

    substrate = connect_substrate()
    latest_block = get_latest_block(substrate)
    logger.info(f"Последний блок в сети: {latest_block}")

    # Первый запуск — инициализация
    if last_block == 0:
        logger.info("Первый запуск, инициализация состояния...")
        save_last_block(latest_block)
        return

    if last_block >= latest_block:
        logger.info("Нет новых блоков для обработки.")
        return

    # Ограничение глубины сканирования (Polkadot — блок каждые ~6 секунд)
    # 300 блоков ≈ 30 минут; при запуске раз в 5 минут это с запасом
    max_block_range = 300
    from_block = last_block + 1
    to_block = min(latest_block, last_block + max_block_range)

    logger.info(f"Сканирование блоков {from_block} – {to_block}")

    total_alerts = 0

    for block_number in range(from_block, to_block + 1):
        alerts = process_block(substrate, block_number)
        for transfer in alerts:
            logger.info(
                f"Крупный перевод: {transfer['amount_dot']:,.2f} DOT "
                f"от {transfer['from']} → {transfer['to']}"
            )
            subject = f"[DOT Whale] {transfer['amount_dot']:,.0f} DOT"
            body = format_alert_message(transfer)
            send_email(subject, body)
            total_alerts += 1

        # Сохраняем состояние после каждого блока — чтобы при сбое не терять прогресс
        save_last_block(block_number)

    logger.info(f"Готово. Обработано блоков: {to_block - from_block + 1}, "
                f"отправлено уведомлений: {total_alerts}")


if __name__ == "__main__":
    main()
