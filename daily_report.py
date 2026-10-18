#!/usr/bin/env python3
"""
DOT Whale Daily Report — формирует ежедневный email-отчёт в виде таблицы
с историей за прошлые дни. Последние данные — в первой строке таблицы.
"""

import json
import logging
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from config import (
    EMAIL_CONFIG,
    PENDING_FILE,
    HISTORY_FILE,
    DOT_SYMBOL,
    LOG_LEVEL,
)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------- Файлы ----------
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


def load_history() -> list:
    if Path(HISTORY_FILE).exists():
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return []
    return []


def save_history(history: list) -> None:
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


# ---------- Email ----------
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


# ---------- Формирование отчёта ----------
def build_today_summary(transfers: list) -> dict:
    """Сводка за сегодня: дата, количество переводов, суммарный объём."""
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    total_amount = sum(t['amount_dot'] for t in transfers) if transfers else 0.0
    return {
        'date': today,
        'count': len(transfers),
        'total_amount': round(total_amount, 2),
    }


def format_table(history: list) -> str:
    """
    Формирует текстовую таблицу из истории.
    Первая строка — последние данные (history[0]).
    """
    if not history:
        return "(нет данных)"

    # Заголовок таблицы
    header = f"{'Дата':<12} | {'Переводов':>10} | {'Суммарный объём (DOT)':>22}"
    sep = "-" * len(header)

    lines = [header, sep]

    for row in history:
        date_str = row.get('date', '—')
        count = row.get('count', 0)
        total = row.get('total_amount', 0.0)
        lines.append(f"{date_str:<12} | {count:>10} | {total:>22,.2f}")

    return "\n".join(lines)


def format_report(transfers: list, history: list) -> str:
    """Формирует полный текст письма с таблицей и списком переводов за сегодня."""
    now = datetime.now(timezone.utc)
    today = now.strftime('%Y-%m-%d')

    lines = []
    lines.append(f"Ежедневный отчёт по крупным переводам {DOT_SYMBOL}")
    lines.append(f"Дата отчёта: {today} {now.strftime('%H:%M UTC')}")
    lines.append("=" * 70)
    lines.append("")
    lines.append("ДИНАМИКА ПО ДНЯМ (последние данные — сверху):")
    lines.append("")
    lines.append(format_table(history))
    lines.append("")
    lines.append("=" * 70)
    lines.append("")

    if not transfers:
        lines.append(f"За сегодня ({today}) крупных переводов не обнаружено.")
        return "\n".join(lines)

    # Сортировка сегодняшних переводов по убыванию суммы
    transfers_sorted = sorted(transfers, key=lambda x: x['amount_dot'], reverse=True)

    lines.append(f"ПЕРЕВОДЫ ЗА СЕГОДНЯ ({today}):")
    lines.append(f"Всего: {len(transfers_sorted)}, "
                 f"суммарный объём: {sum(t['amount_dot'] for t in transfers_sorted):,.2f} {DOT_SYMBOL}")
    lines.append("-" * 70)
    lines.append("")

    for i, t in enumerate(transfers_sorted, 1):
        lines.append(f"{i}. {t['amount_dot']:,.2f} {DOT_SYMBOL}")
        lines.append(f"   От:   {t['from']}")
        lines.append(f"   Кому: {t['to']}")
        lines.append(f"   Блок: {t['block']}")
        lines.append(f"   Транзакция: https://polkadot.subscan.io/extrinsic/{t['extrinsic_hash']}")
        lines.append("")

    return "\n".join(lines)


# ---------- Main ----------
def main():
    logger.info("Формирование ежедневного отчёта...")

    # 1. Загружаем накопленные переводы
    transfers = load_pending()
    logger.info(f"Переводов в очереди: {len(transfers)}")

    # 2. Загружаем историю прошлых отчётов
    history = load_history()
    logger.info(f"Записей в истории: {len(history)}")

    # 3. Считаем сводку за сегодня
    today_summary = build_today_summary(transfers)
    logger.info(f"Сводка за сегодня: {today_summary}")

    # 4. Обновляем историю: новые данные — в начало
    #    Если запись за сегодня уже есть (повторный запуск) — заменяем её
    history = [h for h in history if h.get('date') != today_summary['date']]
    history.insert(0, today_summary)

    # 5. Ограничиваем историю, например, последними 30 днями
    history = history[:30]

    # 6. Формируем письмо
    subject = f"[DOT Whale] Ежедневный отчёт за {today_summary['date']}"
    body = format_report(transfers, history)

    # 7. Отправляем
    send_email(subject, body)
    logger.info("Отчёт отправлен.")

    # 8. Сохраняем историю и очищаем очередь
    save_history(history)
    save_pending([])
    logger.info("История обновлена, очередь очищена. Готово.")


if __name__ == "__main__":
    main()
