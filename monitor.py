#!/usr/bin/env python3
"""
DOT Whale Monitor — сканирование блоков и накопление крупных переводов.
Email НЕ отправляется. Данные пишутся в pending_transfers.json.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from substrateinterface import SubstrateInterface
from substrateinterface.exceptions import SubstrateRequestException

from config import (
    POLKADOT_RPC_URL,
    DOT_DECIMALS,
    DOT_SYMBOL,
    MIN_AMOUNT_DOT,
    STATE_FILE,
    PENDING_FILE,
    LOG_LEVEL,
)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------- Состояние сканера ----------
def load_last_block() -> int:
    if Path(STATE_FILE).exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return int(json.load(f).get('last_block', 0))
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Не удалось прочитать {STATE_FILE}: {e}")
    return 0


def save_last_block(block_number: int) -> None:
    with open(STATE_FILE, 'w') as f:
        json.dump({'last_block': block_number}, f)


# ---------- Накопленные переводы ----------
def load_pending() -> list:
    if Path(PENDING_FILE).exists():
        try:
            with open(PENDING_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return []
    return []


def save_pending(transfers: list) -> None:
    with open(PENDING_FILE, 'w') as f:
        json.dump(transfers, f, indent=2)


# ---------- Подключение к Polkadot ----------
def connect_substrate() -> SubstrateInterface:
    logger.info(f"Подключение к {POLKADOT_RPC_URL}...")
    substrate = SubstrateInterface(
        url=POLKADOT_RPC_URL,
        ss58_format=0,
        type_registry_preset='polkadot',
        auto_discover=True,
    )
    logger.info("Подключение установлено.")
    return substrate


def get_latest_block(substrate: SubstrateInterface) -> int:
    return substrate.get_block_number(substrate.get_chain_head())


# ---------- Обработка блока ----------
def process_block(substrate: SubstrateInterface, block_number: int) -> list:
    """Возвращает список крупных переводов в блоке."""
    found = []

    try:
        block_hash = substrate.get_block_hash(block_number)
        if not block_hash:
            return found
        events = substrate.get_events(block_hash=block_hash)
    except SubstrateRequestException as e:
        logger.warning(f"Ошибка при получении блока {block_number}: {e}")
        return found

    for event in events:
        ev = event.value.get('event', {})
        if ev.get('module_id') != 'Balances' or ev.get('event_id') != 'Transfer':
            continue

        try:
            attrs = ev['attributes']
            from_addr = attrs[0]
            to_addr = attrs[1]
            amount_plancks = int(attrs[2])
        except (KeyError, IndexError, ValueError, TypeError) as e:
            logger.warning(f"Ошибка парсинга события: {e}")
            continue

        amount_dot = amount_plancks / (10 ** DOT_DECIMALS)
        if amount_dot < MIN_AMOUNT_DOT:
            continue

        found.append({
            'from': from_addr,
            'to': to_addr,
            'amount_dot': amount_dot,
            'block': block_number,
            'extrinsic_hash': event.extrinsic_hash,
            'detected_at': datetime.now(timezone.utc).isoformat(),
        })

    return found


# ---------- Main ----------
def main():
    logger.info("Запуск DOT Whale Monitor (режим накопления)...")

    last_block = load_last_block()
    logger.info(f"Последний обработанный блок: {last_block}")

    substrate = connect_substrate()
    latest_block = get_latest_block(substrate)
    logger.info(f"Последний блок в сети: {latest_block}")

    if last_block == 0:
        logger.info("Первый запуск, инициализация состояния...")
        save_last_block(latest_block)
        return

    if last_block >= latest_block:
        logger.info("Нет новых блоков для обработки.")
        return

    max_block_range = 300
    from_block = last_block + 1
    to_block = min(latest_block, last_block + max_block_range)

    logger.info(f"Сканирование блоков {from_block} – {to_block}")

    pending = load_pending()
    new_found = 0

    for block_number in range(from_block, to_block + 1):
        transfers = process_block(substrate, block_number)
        if transfers:
            pending.extend(transfers)
            new_found += len(transfers)
            for t in transfers:
                logger.info(
                    f"Найден перевод: {t['amount_dot']:,.2f} {DOT_SYMBOL} "
                    f"от {t['from']} → {t['to']} (блок {t['block']})"
                )
        save_last_block(block_number)

    save_pending(pending)
    logger.info(
        f"Готово. Обработано блоков: {to_block - from_block + 1}, "
        f"новых крупных переводов: {new_found}, "
        f"всего в очереди на отчёт: {len(pending)}"
    )


if __name__ == "__main__":
    main()
