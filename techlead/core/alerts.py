"""Gerenciamento de deduplicação de alertas."""

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from techlead.core.config import TECHLEAD_DIR

_ALERTS_FILE = TECHLEAD_DIR / "alerts-sent.json"


def _load_sent() -> dict:
    """Carrega o registro de alertas já enviados."""
    if not _ALERTS_FILE.exists():
        return {}
    try:
        return json.loads(_ALERTS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_sent(sent: dict) -> None:
    """Persiste o registro de alertas enviados."""
    TECHLEAD_DIR.mkdir(parents=True, exist_ok=True)
    _ALERTS_FILE.write_text(json.dumps(sent, indent=2))


def _alert_key(alert: str) -> str:
    """Gera chave única para um alerta baseada no conteúdo."""
    return hashlib.md5(alert.encode()).hexdigest()[:12]


def filter_new(alerts: list[str]) -> list[str]:
    """
    Filtra alertas já enviados hoje.

    Retorna apenas alertas que ainda não foram enviados no dia atual.
    """
    today = date.today().isoformat()
    sent = _load_sent()
    new_alerts = []

    for alert in alerts:
        key = _alert_key(alert)
        if sent.get(key, {}).get("date") != today:
            new_alerts.append(alert)

    return new_alerts


def mark_sent(alerts: list[str]) -> None:
    """Registra alertas como enviados hoje."""
    today = date.today().isoformat()
    sent = _load_sent()

    for alert in alerts:
        key = _alert_key(alert)
        sent[key] = {"date": today, "alert": alert[:80]}

    # Remove entradas antigas (mais de 7 dias) para não crescer indefinidamente
    cutoff = date.fromisoformat(today).toordinal() - 7
    sent = {
        k: v for k, v in sent.items()
        if date.fromisoformat(v["date"]).toordinal() >= cutoff
    }

    _save_sent(sent)
