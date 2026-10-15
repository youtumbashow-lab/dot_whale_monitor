#!/usr/bin/env python3
"""
DOT Whale Daily Report — формирует и отправляет ежедневный email-отчёт
по накопленным крупным переводам, затем очищает pending_transfers.json.
"""

import json
import logging
import smtplib
import sys
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from config import (
    EMAIL_CONFIG,
    PENDING_FILE,
    DOT_SYMBOL,
    LOG_LEVEL,
)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


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


def send_email(subject: str, body: str) -> None:
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
        raise


def format_report(transfers: list) -> str:
    """Формирует текст ежедневного отчёта."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=1)

    lines = []
    lines.append(f"Ежедневный отчёт по крупным переводам {DOT_SYMBOL}")
    lines.append(f"Период: {since.strftime('%Y-%m-%d %H:%M UTC')} — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 60)
    lines.append("")

    if not transfers:
        lines.append("Крупных переводов за период не обнаружено.")
        return "\n".join(lines)

    # Сортировка по убыванию суммы
    transfers_sorted = sorted(transfers, key=lambda x: x['amount_dot'], reverse=True)

    total_amount = sum(t['amount_dot'] for t in transfers_sorted)
    lines.append(f"Всего переводов: {len(transfers_sorted)}")
    lines.append(f"Суммарный объём: {total_amount:,.2f} {DOT_SYMBOL}")
    lines.append("")
    lines.append("-" * 60)
    lines.append("")

    for i, t in enumerate(transfers_sorted, 1):
        lines.append(
            f"{i}. {t['amount_dot']:,.2f} {DOT_SYMBOL}"
        )
        lines.append(f"   От:   {t['from']}")
        lines.append(f"   Кому: {t['to']}")
        lines.append(f"   Блок: {t['block']}")
        lines.append(f"   Транзакция: https://polkadot.subscan.io/extrinsic/{t['extrinsic_hash']}")
        lines.append("")

    return "\n".join(lines)


def main():
    logger.info("Формирование ежедневного отчёта...")

    transfers = load_pending()
    logger.info(f"Переводов в очереди: {len(transfers)}")

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    subject = f"[DOT Whale] Ежедневный отчёт за {today}"

    body = format_report(transfers)

    send_email(subject, body)
    logger.info("Отчёт отправлен. Очищаю очередь...")

    save_pending([])
    logger.info("Очередь очищена. Готово.")


if __name__ == "__main__":
    main()
